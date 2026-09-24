"""
سرویس آپلود بکاپ به سرور راه‌دور (SMB/FTP) + اعمال Retention روی همان سرور.

SMB: از ابزار خط‌فرمان smbclient (بخش samba-client، باید در install.sh نصب
شود) استفاده می‌شود - بدون نیاز به mount/دسترسی root، برخلاف mount.cifs که
نیاز به root دارد.

FTP: از ftplib استاندارد پایتون استفاده می‌شود؛ اگر use_tls=True باشد، از
FTP_TLS (یعنی FTPS - رمزنگاری‌شده) استفاده می‌شود، نه FTP خام (که رمز عبور
را واضح روی شبکه می‌فرستد).

Retention: به‌جای تکیه به تاریخ فایل که سرورهای SMB/FTP مختلف آن را با
فرمت‌های متفاوت گزارش می‌دهند (پردازش غیرقابل‌اعتماد)، از خودِ نام فایل
(که همیشه faipco-backup-YYYYMMDD-HHMMSS.zip است - همان قالب endpoints/backup.py)
تاریخ استخراج می‌شود؛ مرتب‌سازی بر همین اساس انجام می‌شود.
"""
from __future__ import annotations

import ftplib
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

# الگوی نام فایل بکاپ؛ گروه ۱ زمان ساخت (UTC) است
BACKUP_FILENAME_PATTERN = re.compile(r"faipco-backup-(\d{8}-\d{6})\.zip")


class RemoteBackupError(Exception):
    """خطای اتصال/آپلود/حذف روی مقصد SMB یا FTP با پیام قابل‌نمایش."""
    pass


def _parse_backup_timestamp(filename: str) -> datetime | None:
    """ورودی: نام فایل. خروجی: زمان ساخت بکاپ (UTC) از روی نام، یا None اگر با الگو نخواند."""
    match = BACKUP_FILENAME_PATTERN.search(filename)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _files_to_delete_for_retention(
    filenames: list[str], *, mode: str, retention_count: int, retention_days: int
) -> list[str]:
    """
    از بین filenames، فقط آن‌هایی که با الگوی بکاپ خودمان مطابقت دارند در
    نظر گرفته می‌شوند (فایل‌های دیگرِ همان پوشه/Share دست‌نخورده می‌مانند).
    خروجی: نام فایل‌هایی که طبق mode (count/days) باید حذف شوند.
    """
    dated = [(name, ts) for name in filenames if (ts := _parse_backup_timestamp(name)) is not None]
    dated.sort(key=lambda pair: pair[1], reverse=True)  # جدیدترین اول

    # حالت count: همه به‌جز N مورد جدیدتر حذف می‌شوند
    if mode == "count":
        return [name for name, _ in dated[retention_count:]]

    # حالت days: بکاپ‌های قدیمی‌تر از N روز حذف می‌شوند
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    return [name for name, ts in dated if ts < cutoff]


# ==================== SMB ====================


def _find_smbclient_binary() -> str:
    """مسیر اجرایی smbclient را از PATH یا مسیر پیش‌فرض برمی‌گرداند."""
    found = shutil.which("smbclient")
    return found or "/usr/bin/smbclient"


def _smb_auth_string(username: str, password: str, domain: str | None) -> str:
    """رشته احراز هویت smbclient را از نام کاربری، رمز و دامنه اختیاری می‌سازد."""
    auth = f"{username}%{password}"  # قالب -U در smbclient: user%pass یا DOMAIN\user%pass
    return f"{domain}\\{auth}" if domain else auth


def _run_smbclient(target: str, auth: str, command: str, *, timeout: int = 60) -> str:
    """
    یک فرمان smbclient روی target اجرا می‌کند و stdout+stderr را برمی‌گرداند.
    خطا: RemoteBackupError اگر ابزار نصب نباشد یا Timeout شود.
    """
    smbclient = _find_smbclient_binary()
    try:
        result = subprocess.run(
            [smbclient, target, "-U", auth, "-c", command],
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise RemoteBackupError(
            "ابزار smbclient روی این سرور پیدا نشد — بسته samba-client باید نصب باشد."
        ) from e
    except subprocess.TimeoutExpired as e:
        raise RemoteBackupError("اتصال به سرور SMB بیش‌ازحد طول کشید (Timeout).") from e
    return result.stdout.decode(errors="ignore") + result.stderr.decode(errors="ignore")


def test_smb_connection(
    *, host: str, share: str, path: str | None, username: str, password: str, domain: str | None
) -> None:
    """اتصال به Share (و ورود به مسیر اختیاری) را با ls تست می‌کند. خطا: RemoteBackupError."""
    target = f"//{host}/{share}"
    auth = _smb_auth_string(username, password, domain)
    cmd = f'cd "{path.strip("/")}"; ls' if path else "ls"
    output = _run_smbclient(target, auth, cmd)
    # smbclient خطاها را با کدهای NT_STATUS_* در خروجی گزارش می‌دهد
    if "NT_STATUS" in output and "NT_STATUS_OK" not in output:
        raise RemoteBackupError(f"اتصال به SMB ناموفق بود: {output.strip()[:500]}")


def upload_to_smb(
    file_path: Path,
    remote_filename: str,
    *,
    host: str,
    share: str,
    path: str | None,
    username: str,
    password: str,
    domain: str | None,
) -> None:
    """
    فایل محلی را با نام remote_filename در Share/مسیر آپلود می‌کند و پوشه‌های لازم را می‌سازد.
    خطا: RemoteBackupError اگر پیام موفقیت در خروجی نباشد.
    """
    target = f"//{host}/{share}"
    auth = _smb_auth_string(username, password, domain)

    commands = []
    if path:
        # هر پوشه تو در تو را جدا mkdir می‌کنیم - smbclient یک mkdir تو در
        # تو یک‌جا نمی‌سازد. خطای «از قبل هست» بی‌ضرر است و نادیده گرفته می‌شود.
        accumulated = ""
        for part in [p for p in path.strip("/").split("/") if p]:
            accumulated = f"{accumulated}/{part}" if accumulated else part
            commands.append(f'mkdir "{accumulated}"')
        commands.append(f'cd "{path.strip("/")}"')
    commands.append(f'put "{file_path}" "{remote_filename}"')

    # اجرای همه فرمان‌ها در یک نشست smbclient
    output = _run_smbclient(target, auth, "; ".join(commands), timeout=300)
    if "putting file" not in output.lower():  # پیام موفقیت put در smbclient
        raise RemoteBackupError(f"آپلود به SMB ناموفق بود: {output.strip()[:800]}")


def list_smb_backup_filenames(
    *, host: str, share: str, path: str | None, username: str, password: str, domain: str | None
) -> list[str]:
    """خروجی: نام فایل‌های بکاپ پرتال موجود در مسیر SMB."""
    target = f"//{host}/{share}"
    auth = _smb_auth_string(username, password, domain)
    cmd = f'cd "{path.strip("/")}"; ls' if path else "ls"
    output = _run_smbclient(target, auth, cmd)
    return [m.group(0) for m in re.finditer(r"faipco-backup-\d{8}-\d{6}\.zip", output)]  # فقط فایل‌های بکاپ از خروجی ls


def delete_smb_file(
    filename: str, *, host: str, share: str, path: str | None, username: str, password: str, domain: str | None
) -> None:
    """یک فایل را از مسیر SMB حذف می‌کند (خروجی smbclient بررسی نمی‌شود)."""
    target = f"//{host}/{share}"
    auth = _smb_auth_string(username, password, domain)
    cmd = f'cd "{path.strip("/")}"; del "{filename}"' if path else f'del "{filename}"'
    _run_smbclient(target, auth, cmd)


def apply_smb_retention(
    *,
    host: str,
    share: str,
    path: str | None,
    username: str,
    password: str,
    domain: str | None,
    mode: str,
    retention_count: int,
    retention_days: int,
) -> int:
    """بکاپ‌های اضافی/قدیمی روی SMB را طبق سیاست نگهداری حذف می‌کند. خروجی: تعداد حذف‌شده."""
    filenames = list_smb_backup_filenames(
        host=host, share=share, path=path, username=username, password=password, domain=domain
    )
    to_delete = _files_to_delete_for_retention(
        filenames, mode=mode, retention_count=retention_count, retention_days=retention_days
    )
    for name in to_delete:
        delete_smb_file(name, host=host, share=share, path=path, username=username, password=password, domain=domain)
    return len(to_delete)


# ==================== FTP ====================


def _connect_ftp(host: str, port: int, username: str, password: str, use_tls: bool) -> ftplib.FTP:
    """به سرور FTP (یا FTPS اگر use_tls) وصل و وارد می‌شود. خروجی: شیء FTP. خطا: RemoteBackupError."""
    try:
        if use_tls:
            ftp = ftplib.FTP_TLS()
            ftp.connect(host, port, timeout=30)
            ftp.login(username, password)
            ftp.prot_p()  # کانال داده هم رمزنگاری‌شده شود، نه فقط کانال فرمان
        else:
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=30)
            ftp.login(username, password)
        return ftp
    except (ftplib.all_errors, OSError) as e:
        raise RemoteBackupError(f"اتصال به سرور FTP ناموفق بود: {e}") from e


def _ftp_ensure_path(ftp: ftplib.FTP, path: str | None) -> None:
    """پوشه کاری را به path تغییر می‌دهد و پوشه‌های ناموجود را می‌سازد."""
    if not path:
        return
    # برای هر بخش مسیر: ورود به پوشه، و در صورت نبود ساخت آن
    for part in [p for p in path.strip("/").split("/") if p]:
        try:
            ftp.cwd(part)
        except ftplib.error_perm:
            ftp.mkd(part)
            ftp.cwd(part)


def test_ftp_connection(
    *, host: str, port: int, username: str, password: str, path: str | None, use_tls: bool
) -> None:
    """اتصال، ورود و دسترسی به مسیر FTP را تست می‌کند. خطا: RemoteBackupError."""
    ftp = _connect_ftp(host, port, username, password, use_tls)
    try:
        _ftp_ensure_path(ftp, path)
        ftp.nlst()
    except ftplib.all_errors as e:
        raise RemoteBackupError(f"اتصال FTP برقرار شد ولی بررسی مسیر ناموفق بود: {e}") from e
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001
            ftp.close()


def upload_to_ftp(
    file_path: Path,
    remote_filename: str,
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    path: str | None,
    use_tls: bool,
) -> None:
    """فایل محلی را با نام remote_filename در مسیر FTP آپلود (STOR) می‌کند. خطا: RemoteBackupError."""
    ftp = _connect_ftp(host, port, username, password, use_tls)
    try:
        _ftp_ensure_path(ftp, path)
        with file_path.open("rb") as f:
            ftp.storbinary(f"STOR {remote_filename}", f)
    except ftplib.all_errors as e:
        raise RemoteBackupError(f"آپلود به FTP ناموفق بود: {e}") from e
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001
            ftp.close()


def list_ftp_backup_filenames(
    *, host: str, port: int, username: str, password: str, path: str | None, use_tls: bool
) -> list[str]:
    """خروجی: نام فایل‌های بکاپ پرتال موجود در مسیر FTP."""
    ftp = _connect_ftp(host, port, username, password, use_tls)
    try:
        _ftp_ensure_path(ftp, path)
        names = ftp.nlst()
    except ftplib.all_errors as e:
        raise RemoteBackupError(f"دریافت فهرست فایل‌های FTP ناموفق بود: {e}") from e
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001
            ftp.close()
    # nlst ممکن است مسیر کامل یا فقط نام برگرداند - فقط بخش نام فایل را نگه می‌داریم
    return [Path(n).name for n in names if BACKUP_FILENAME_PATTERN.search(n)]


def delete_ftp_file(
    filename: str, *, host: str, port: int, username: str, password: str, path: str | None, use_tls: bool
) -> None:
    """یک فایل را از مسیر FTP حذف می‌کند. خطا: RemoteBackupError."""
    ftp = _connect_ftp(host, port, username, password, use_tls)
    try:
        _ftp_ensure_path(ftp, path)
        ftp.delete(filename)
    except ftplib.all_errors as e:
        raise RemoteBackupError(f"حذف فایل FTP ناموفق بود: {e}") from e
    finally:
        try:
            ftp.quit()
        except Exception:  # noqa: BLE001
            ftp.close()


def apply_ftp_retention(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    path: str | None,
    use_tls: bool,
    mode: str,
    retention_count: int,
    retention_days: int,
) -> int:
    """بکاپ‌های اضافی/قدیمی روی FTP را طبق سیاست نگهداری حذف می‌کند. خروجی: تعداد حذف‌شده."""
    filenames = list_ftp_backup_filenames(
        host=host, port=port, username=username, password=password, path=path, use_tls=use_tls
    )
    to_delete = _files_to_delete_for_retention(
        filenames, mode=mode, retention_count=retention_count, retention_days=retention_days
    )
    for name in to_delete:
        delete_ftp_file(name, host=host, port=port, username=username, password=password, path=path, use_tls=use_tls)
    return len(to_delete)
