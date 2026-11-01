"""
مقصدهای بکاپ (docs/backup.md بخش «مقصدها»): ارسال یک فایل ZIP به هر مقصد، بررسی سالم رسیدن، Retention و تست اتصال.

- local: پوشه یا دیسک متصل به همین سرور (مثلاً /mnt/backup). کپی با نام موقت، بعد هش دوباره و تغییر نام.
- sftp: با paramiko؛ کلید سرور بار اول (دکمه‌ی تست) ذخیره و از آن به بعد مقایسه می‌شود (جلوی جعل سرور).
- s3: هر سرویس سازگار با S3 (AWS، MinIO، ابر آروان و...) با httpx و امضای SigV4؛ هش بدنه امضا می‌شود و سرور S3 فایلِ
  ناقص یا خراب را رد می‌کند؛ بعد HEAD حجم را بررسی می‌کند.
- smb/ftp: services/remote_backup_service.py ؛ email: services/email_service.py.

همه‌ی توابع همگام‌اند (فراخواننده با asyncio.to_thread صدا می‌زند) و خطای قابل نمایش را با RemoteBackupError می‌دهند.
"""
from __future__ import annotations

import base64
import hashlib
import os
import shutil
import socket
import xml.etree.ElementTree as ET
from pathlib import Path

from app.core import backup_dest_rules as R
from app.services.remote_backup_service import (
    BACKUP_FILENAME_PATTERN,
    RemoteBackupError,
    _files_to_delete_for_retention,
)

CHUNK = 1 << 20


# ==================== پوشه‌ی محلی / دیسک متصل ====================


def _local_dir(raw: str | None, *, create: bool) -> Path:
    try:
        path = Path(R.check_local_path(raw))
    except ValueError as e:
        raise RemoteBackupError(str(e)) from None
    if create:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise RemoteBackupError(
                f"ساخت پوشه‌ی {path} ممکن نشد ({e.strerror}). پوشه را خودتان بسازید و به کاربر www-data اجازه‌ی نوشتن بدهید: "
                f"sudo mkdir -p {path} && sudo chown www-data:www-data {path}"
            ) from None
    if not path.is_dir():
        raise RemoteBackupError(f"پوشه‌ی {path} وجود ندارد")
    return path


def test_local(path: str | None) -> str:
    """نوشتن و پاک کردن یک فایل آزمایشی؛ خروجی: پیام شامل فضای آزاد و این‌که روی همان دیسک سیستم است یا نه."""
    folder = _local_dir(path, create=True)
    probe = folder / ".faipco-write-test"
    try:
        probe.write_bytes(b"ok")
        probe.unlink()
    except OSError as e:
        raise RemoteBackupError(
            f"پرتال اجازه‌ی نوشتن در {folder} را ندارد ({e.strerror}). روی سرور: sudo chown www-data:www-data {folder}"
        ) from None
    usage = shutil.disk_usage(folder)
    same_disk = os.stat(folder).st_dev == os.stat("/").st_dev
    msg = f"نوشتن در پوشه موفق بود. فضای آزاد: {usage.free / 1024**3:.1f} گیگابایت."
    if same_disk:
        msg += " توجه: این پوشه روی همان دیسک سیستم است؛ اگر دیسک سرور خراب شود بکاپ هم از دست می‌رود — بهتر است دیسک جدا باشد."
    return msg


def upload_local(file_path: Path, filename: str, sha256: str, *, path: str | None) -> None:
    folder = _local_dir(path, create=True)
    size = file_path.stat().st_size
    if shutil.disk_usage(folder).free < size + 50 * 1024**2:
        raise RemoteBackupError(f"فضای آزاد پوشه‌ی {folder} برای این بکاپ ({size / 1024**2:.0f} مگابایت) کافی نیست")
    tmp = folder / f".{filename}.part"
    try:
        with file_path.open("rb") as src, tmp.open("wb") as dst:
            shutil.copyfileobj(src, dst, CHUNK)
            dst.flush()
            os.fsync(dst.fileno())
        # بررسی سالم رسیدن: هش فایل نوشته‌شده (همیشه کامل، چون محلی و ارزان است)
        if R.sha256_file(tmp) != sha256:
            raise RemoteBackupError("هش فایل کپی‌شده با فایل اصلی نمی‌خواند — فایل سالم نوشته نشد")
        os.replace(tmp, folder / filename)
    except OSError as e:
        raise RemoteBackupError(f"کپی بکاپ در {folder} ناموفق بود: {e.strerror or e}") from None
    finally:
        tmp.unlink(missing_ok=True)


def retention_local(*, path: str | None, mode: str, retention_count: int, retention_days: int) -> int:
    folder = _local_dir(path, create=False)
    names = [n for n in os.listdir(folder) if BACKUP_FILENAME_PATTERN.fullmatch(n)]
    victims = _files_to_delete_for_retention(names, mode=mode, retention_count=retention_count,
                                             retention_days=retention_days)
    for name in victims:
        (folder / name).unlink(missing_ok=True)
    return len(victims)


# ==================== SFTP ====================


def _paramiko():
    try:
        import paramiko
    except ImportError:
        raise RemoteBackupError("کتابخانه‌ی paramiko روی سرور نصب نیست (requirements.txt) — یک بار آپدیت/نصب را اجرا کنید") from None
    return paramiko


def _key_text(key) -> str:
    return f"{key.get_name()} {key.get_base64()}"


def key_fingerprint(key_text: str) -> str:
    """اثر انگشت SHA256 کلید سرور (همان قالب ssh-keygen -l)."""
    try:
        kind, b64 = key_text.split(" ", 1)
        digest = hashlib.sha256(base64.b64decode(b64)).digest()
    except (ValueError, TypeError):
        return "?"
    return f"{kind} SHA256:{base64.b64encode(digest).decode().rstrip('=')}"


def _sftp_connect(host: str, port: int, username: str, password: str, host_key: str | None, *, accept_new: bool):
    """اتصال SFTP. خروجی: (transport, sftp, server_key_text). کلید متفاوت با host_key → خطا (مگر accept_new)."""
    paramiko = _paramiko()
    try:
        sock = socket.create_connection((host, int(port or 22)), timeout=30)
    except OSError as e:
        raise RemoteBackupError(f"اتصال به سرور SFTP ({host}:{port}) برقرار نشد: {e}") from None
    transport = paramiko.Transport(sock)
    try:
        transport.banner_timeout = 30
        transport.start_client(timeout=30)
        server_key = _key_text(transport.get_remote_server_key())
        if host_key and server_key != host_key.strip() and not accept_new:
            raise RemoteBackupError(
                "کلید امنیتی سرور SFTP با کلید ذخیره‌شده فرق دارد (ممکن است سرور عوض شده باشد یا اتصال جعلی باشد). "
                f"کلید جدید: {key_fingerprint(server_key)}. اگر مطمئنید سرور را عوض کرده‌اید، در تنظیمات «پذیرش کلید جدید» را بزنید."
            )
        if not host_key and not accept_new:
            raise RemoteBackupError("کلید سرور SFTP هنوز تأیید نشده؛ یک بار «تست اتصال SFTP» را بزنید و تنظیمات را ذخیره کنید")
        try:
            transport.auth_password(username, password)
        except paramiko.AuthenticationException:
            raise RemoteBackupError("نام کاربری یا رمز SFTP اشتباه است") from None
        sftp = paramiko.SFTPClient.from_transport(transport)
        sftp.get_channel().settimeout(120)
        return transport, sftp, server_key
    except RemoteBackupError:
        transport.close()
        raise
    except (paramiko.SSHException, OSError, EOFError) as e:
        transport.close()
        raise RemoteBackupError(f"اتصال SFTP ناموفق بود: {e}") from None


def _sftp_cd(sftp, path: str | None, *, create: bool) -> None:
    parts = [p for p in (path or "").replace("\\", "/").split("/") if p and p != "."]
    if (path or "").startswith("/"):
        sftp.chdir("/")
    for part in parts:
        if part == "..":
            raise RemoteBackupError("مسیر SFTP نباید «..» داشته باشد")
        try:
            sftp.chdir(part)
        except OSError:
            if not create:
                raise RemoteBackupError(f"پوشه‌ی «{part}» روی سرور SFTP نیست") from None
            sftp.mkdir(part)
            sftp.chdir(part)


def test_sftp(*, host, port, username, password, path, host_key, accept_new: bool) -> dict:
    """خروجی: {"message", "host_key", "fingerprint"} — کلید سرور برای ذخیره در تنظیمات."""
    transport, sftp, server_key = _sftp_connect(host, port, username, password, host_key,
                                                accept_new=accept_new or not host_key)
    try:
        _sftp_cd(sftp, path, create=True)
        sftp.listdir(".")
    except OSError as e:
        raise RemoteBackupError(f"اتصال SFTP برقرار شد ولی دسترسی به مسیر ناموفق بود: {e}") from None
    finally:
        transport.close()
    fp = key_fingerprint(server_key)
    msg = "اتصال به SFTP موفق بود."
    if server_key != (host_key or "").strip():
        msg += f" کلید سرور: {fp} — برای ثبت آن «ذخیره تنظیمات» را بزنید."
    return {"message": msg, "host_key": server_key, "fingerprint": fp}


def upload_sftp(file_path: Path, filename: str, sha256: str, *, host, port, username, password, path, host_key,
                verify_full: bool) -> None:
    transport, sftp, _ = _sftp_connect(host, port, username, password, host_key, accept_new=False)
    try:
        _sftp_cd(sftp, path, create=True)
        part = f".{filename}.part"
        size = file_path.stat().st_size
        sftp.put(str(file_path), part, confirm=True)  # confirm: بعد از آپلود stat و مقایسه‌ی حجم
        if sftp.stat(part).st_size != size:
            raise RemoteBackupError("حجم فایل روی SFTP با فایل اصلی برابر نیست")
        if verify_full:
            h = hashlib.sha256()
            with sftp.open(part, "rb") as f:
                f.prefetch()
                for block in iter(lambda: f.read(CHUNK), b""):
                    h.update(block)
            if h.hexdigest() != sha256:
                raise RemoteBackupError("هش فایل خوانده‌شده از SFTP با فایل اصلی نمی‌خواند — فایل سالم نرسیده است")
        try:
            sftp.remove(filename)
        except OSError:
            pass
        sftp.rename(part, filename)
    except OSError as e:
        raise RemoteBackupError(f"آپلود به SFTP ناموفق بود: {e}") from None
    finally:
        transport.close()


def retention_sftp(*, host, port, username, password, path, host_key, mode, retention_count, retention_days) -> int:
    transport, sftp, _ = _sftp_connect(host, port, username, password, host_key, accept_new=False)
    try:
        _sftp_cd(sftp, path, create=False)
        names = [n for n in sftp.listdir(".") if BACKUP_FILENAME_PATTERN.fullmatch(n)]
        victims = _files_to_delete_for_retention(names, mode=mode, retention_count=retention_count,
                                                 retention_days=retention_days)
        for name in victims:
            sftp.remove(name)
        return len(victims)
    except OSError as e:
        raise RemoteBackupError(f"پاک‌سازی بکاپ‌های قدیمی SFTP ناموفق بود: {e}") from None
    finally:
        transport.close()


# ==================== S3 ====================


class _S3:
    def __init__(self, *, endpoint, region, bucket, access_key, secret_key, path_style: bool):
        if not (endpoint and bucket and access_key and secret_key):
            raise RemoteBackupError("برای S3، آدرس سرویس، نام Bucket، Access Key و Secret Key لازم است")
        self.endpoint, self.bucket, self.path_style = endpoint, bucket, path_style
        self.region = (region or "").strip() or "us-east-1"
        self.access_key, self.secret_key = access_key.strip(), secret_key

    def request(self, method: str, key: str, *, query=None, headers=None, body=None, payload_sha256=R.EMPTY_SHA256,
                timeout=60.0):
        import httpx

        url, host, canonical = R.s3_object_url(self.endpoint, self.bucket, key, path_style=self.path_style)
        signed = R.sigv4_headers(method=method, host=host, canonical_uri=canonical, query=query, headers=headers,
                                 payload_sha256=payload_sha256, access_key=self.access_key,
                                 secret_key=self.secret_key, region=self.region)
        if query:
            url += "?" + R._canonical_query(query)
        try:
            with httpx.Client(timeout=httpx.Timeout(timeout, connect=20.0)) as client:
                return client.request(method, url, headers=signed, content=body)
        except httpx.HTTPError as e:
            raise RemoteBackupError(f"اتصال به S3 ناموفق بود: {e}") from None


def _s3_error(resp, action: str) -> RemoteBackupError:
    code = msg = ""
    try:
        root = ET.fromstring(resp.content)
        code = root.findtext("Code") or ""
        msg = root.findtext("Message") or ""
    except ET.ParseError:
        pass
    hints = {
        "SignatureDoesNotMatch": "Secret Key یا Region اشتباه است",
        "InvalidAccessKeyId": "Access Key اشتباه است",
        "NoSuchBucket": "این Bucket وجود ندارد",
        "AccessDenied": "این کلید اجازه‌ی این کار را روی Bucket ندارد",
        "XAmzContentSHA256Mismatch": "فایل در مسیر خراب شد (هش نخواند)",
        "BadDigest": "فایل در مسیر خراب شد (هش نخواند)",
    }
    detail = hints.get(code) or msg or resp.text[:200]
    return RemoteBackupError(f"{action} در S3 ناموفق بود (HTTP {resp.status_code} {code}): {detail}")


def _s3_list(s3: _S3, prefix: str) -> list[str]:
    keys, token = [], None
    while True:
        query = {"list-type": "2", "prefix": prefix}
        if token:
            query["continuation-token"] = token
        resp = s3.request("GET", "", query=query)
        if resp.status_code != 200:
            raise _s3_error(resp, "دریافت فهرست فایل‌ها")
        root = ET.fromstring(resp.content)
        ns = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
        keys += [c.findtext(f"{ns}Key") or "" for c in root.findall(f"{ns}Contents")]
        if (root.findtext(f"{ns}IsTruncated") or "").lower() != "true":
            return keys
        token = root.findtext(f"{ns}NextContinuationToken")
        if not token:
            return keys


def _list_prefix(prefix: str | None) -> str:
    p = (prefix or "").strip().strip("/")
    return f"{p}/" if p else ""


def test_s3(*, endpoint, region, bucket, prefix, access_key, secret_key, path_style) -> str:
    s3 = _S3(endpoint=endpoint, region=region, bucket=bucket, access_key=access_key, secret_key=secret_key,
             path_style=path_style)
    _s3_list(s3, _list_prefix(prefix))
    # نوشتن و پاک کردن یک شیء کوچک تا اجازه‌ی نوشتن هم بررسی شود
    key = R.s3_key(prefix, ".faipco-write-test")
    body = b"ok"
    resp = s3.request("PUT", key, headers={"content-length": str(len(body))}, body=body,
                      payload_sha256=hashlib.sha256(body).hexdigest())
    if resp.status_code not in (200, 201):
        raise _s3_error(resp, "نوشتن فایل آزمایشی")
    s3.request("DELETE", key)
    return "اتصال به S3 و نوشتن در Bucket موفق بود."


def upload_s3(file_path: Path, filename: str, sha256: str, *, endpoint, region, bucket, prefix, access_key, secret_key,
              path_style) -> None:
    size = file_path.stat().st_size
    if size > R.S3_SINGLE_PUT_MAX:
        raise RemoteBackupError("حجم بکاپ بیش از ۵ گیگابایت است؛ آپلود یک‌تکه به S3 ممکن نیست")
    s3 = _S3(endpoint=endpoint, region=region, bucket=bucket, access_key=access_key, secret_key=secret_key,
             path_style=path_style)
    key = R.s3_key(prefix, filename)
    with file_path.open("rb") as f:
        # هش کل فایل امضا می‌شود؛ سرور S3 اگر بایت‌های رسیده با آن نخواند آپلود را رد می‌کند
        resp = s3.request("PUT", key, headers={"content-length": str(size), "content-type": "application/zip"},
                          body=iter(lambda: f.read(CHUNK), b""), payload_sha256=sha256, timeout=600.0)
    if resp.status_code not in (200, 201):
        raise _s3_error(resp, "آپلود")
    head = s3.request("HEAD", key)
    if head.status_code != 200:
        raise RemoteBackupError(f"فایل بعد از آپلود در S3 پیدا نشد (HTTP {head.status_code})")
    if int(head.headers.get("content-length", -1)) != size:
        raise RemoteBackupError("حجم فایل در S3 با فایل اصلی برابر نیست")


def retention_s3(*, endpoint, region, bucket, prefix, access_key, secret_key, path_style, mode, retention_count,
                 retention_days) -> int:
    s3 = _S3(endpoint=endpoint, region=region, bucket=bucket, access_key=access_key, secret_key=secret_key,
             path_style=path_style)
    lp = _list_prefix(prefix)
    names = [k[len(lp):] for k in _s3_list(s3, lp)]
    names = [n for n in names if "/" not in n and BACKUP_FILENAME_PATTERN.fullmatch(n)]
    victims = _files_to_delete_for_retention(names, mode=mode, retention_count=retention_count,
                                             retention_days=retention_days)
    for name in victims:
        resp = s3.request("DELETE", R.s3_key(prefix, name))
        if resp.status_code not in (200, 204):
            raise _s3_error(resp, "حذف بکاپ قدیمی")
    return len(victims)
