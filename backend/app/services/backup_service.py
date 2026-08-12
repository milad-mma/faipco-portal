"""
سرویس پشتیبان‌گیری کامل — طوری طراحی شده که بازیابی روی یک سرور کاملاً
تازه (نصب تمیز همین پروژه + `install.sh --restore-backup backup.zip`)
دقیقاً همان اطلاعات را برگرداند؛ انگار پروژه Clone شده باشد.

بکاپ شامل دو بخش حیاتی است:
1. database.sql — فقط داده (نه Schema)، با pg_dump --data-only گرفته
   می‌شود؛ چون Schema همیشه از روی Migration های خودِ کد در سرور جدید ساخته
   می‌شود (نه از روی بکاپ) — این یعنی حتی اگر کد از زمان گرفتن بکاپ تغییر
   کرده باشد (Migration های جدید)، بازیابی همچنان با آخرین نسخه کد سازگار
   می‌ماند.
2. secrets.json — کلیدهای رمزنگاری حیاتی، مخصوصاً DB_CREDENTIALS_ENCRYPTION_KEY.
   بدون این کلید دقیق، رمز عبور اتصال دیتابیس سایت‌ها (که در همان
   database.sql رمزنگاری‌شده ذخیره شده) روی سرور جدید برای همیشه
   غیرقابل‌رمزگشایی می‌شود — یعنی دیگر یک Clone واقعی نیست.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings


class BackupError(Exception):
    pass


def _to_libpq_url(database_url: str) -> str:
    """postgresql+asyncpg://... یا postgresql+psycopg2://... را به فرمتی که
    ابزارهای خط‌فرمان pg_dump/psql می‌فهمند (postgresql://...) تبدیل می‌کند."""
    return database_url.replace("+asyncpg", "").replace("+psycopg2", "")


async def create_backup_archive() -> bytes:
    settings = get_settings()
    libpq_url = _to_libpq_url(settings.DATABASE_URL)

    with tempfile.TemporaryDirectory() as tmp_dir:
        dump_path = Path(tmp_dir) / "database.sql"

        try:
            proc = await asyncio.create_subprocess_exec(
                "pg_dump",
                "--data-only",
                "--disable-triggers",
                "--no-owner",
                "--no-privileges",
                "--format=plain",
                f"--file={dump_path}",
                libpq_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise BackupError(f"pg_dump ناموفق بود: {stderr.decode(errors='ignore')[:500]}")
        except FileNotFoundError as e:
            raise BackupError(
                "ابزار pg_dump روی این سرور پیدا نشد — بسته postgresql-client باید نصب باشد."
            ) from e

        manifest = {
            "app_name": settings.APP_NAME,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "format": "faipco-portal-backup-v1",
            "restore_instructions": (
                "روی سرور جدید (نصب کاملاً تازه): "
                "sudo bash install.sh --restore-backup /path/to/this-file.zip [سایر گزینه‌های معمول نصب]"
            ),
        }
        # این کلیدها باید عیناً روی سرور جدید بازیابی شوند، وگرنه رمز عبور
        # اتصال دیتابیس سایت‌ها (که داخل database.sql رمزنگاری‌شده) دیگر
        # قابل‌رمزگشایی نخواهد بود.
        secrets = {
            "DB_CREDENTIALS_ENCRYPTION_KEY": settings.DB_CREDENTIALS_ENCRYPTION_KEY,
            "SECRET_KEY": settings.SECRET_KEY,
            "VAPID_PUBLIC_KEY": settings.VAPID_PUBLIC_KEY,
            "VAPID_PRIVATE_KEY": settings.VAPID_PRIVATE_KEY,
        }

        zip_path = Path(tmp_dir) / "backup.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(dump_path, "database.sql")
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            zf.writestr("secrets.json", json.dumps(secrets, ensure_ascii=False, indent=2))

        return zip_path.read_bytes()
