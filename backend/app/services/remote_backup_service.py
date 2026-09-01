"""
سرویس آپلود بکاپ به سرور راه‌دور (SMB/FTP) + اعمال Retention روی همان سرور.

SMB: از ابزار خط‌فرمان smbclient (بخش samba-client، باید در install.sh نصب
شود) استفاده می‌شود - بدون نیاز به mount/دسترسی root، برخلاف mount.cifs که
راه‌حل Restore همین پروژه (backup_service.py) هم عمداً از آن اجتناب کرد.

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

BACKUP_FILENAME_PATTERN = re.compile(r"faipco-backup-(\d{8}-\d{6})\.zip")


class RemoteBackupError(Exception):
    pass


def _parse_backup_timestamp(filename: str) -> datetime | None:
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
    """
    dated = [(name, ts) for name in filenames if (ts := _parse_backup_timestamp(name)) is not None]
    dated.sort(key=lambda pair: pair[1], reverse=True)  # جدیدترین اول

    if mode == "count":
        return [name for name, _ in dated[retention_count:]]

    # mode == "days"
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    return [name for name, ts in dated if ts < cutoff]


# ==================== SMB ====================


def _find_smbclient_binary() -> str:
    found = shutil.which("smbclient")
    return found or "/usr/bin/smbclient"


def _smb_auth_string(username: str, password: str, domain: str | None) -> str:
    auth = f"{username}%{password}"
    return f"{domain}\\{auth}" if domain else auth


def _run_smbclient(target: str, auth: str, command: str, *, timeout: int = 60) -> str:
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
    target = f"//{host}/{share}"
    auth = _smb_auth_string(username, password, domain)
    cmd = f'cd "{path.strip("/")}"; ls' if path else "ls"
    output = _run_smbclient(target, auth, cmd)
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

    output = _run_smbclient(target, auth, "; ".join(commands), timeout=300)
    if "putting file" not in output.lower():
        raise RemoteBackupError(f"آپلود به SMB ناموفق بود: {output.strip()[:800]}")


def list_smb_backup_filenames(
    *, host: str, share: str, path: str | None, username: str, password: str, domain: str | None
) -> list[str]:
    target = f"//{host}/{share}"
    auth = _smb_auth_string(username, password, domain)
    cmd = f'cd "{path.strip("/")}"; ls' if path else "ls"
    output = _run_smbclient(target, auth, cmd)
    return [m.group(0) for m in re.finditer(r"faipco-backup-\d{8}-\d{6}\.zip", output)]


def delete_smb_file(
    filename: str, *, host: str, share: str, path: str | None, username: str, password: str, domain: str | None
) -> None:
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
    if not path:
        return
    for part in [p for p in path.strip("/").split("/") if p]:
        try:
            ftp.cwd(part)
        except ftplib.error_perm:
            ftp.mkd(part)
            ftp.cwd(part)


def test_ftp_connection(
    *, host: str, port: int, username: str, password: str, path: str | None, use_tls: bool
) -> None:
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
    filenames = list_ftp_backup_filenames(
        host=host, port=port, username=username, password=password, path=path, use_tls=use_tls
    )
    to_delete = _files_to_delete_for_retention(
        filenames, mode=mode, retention_count=retention_count, retention_days=retention_days
    )
    for name in to_delete:
        delete_ftp_file(name, host=host, port=port, username=username, password=password, path=path, use_tls=use_tls)
    return len(to_delete)
