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
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from app.core.config import get_settings

# فایل .env همیشه دقیقاً کنار خودِ پوشه app/ است (backend/.env)
_ENV_FILE_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class BackupError(Exception):
    pass


def _to_libpq_url(database_url: str) -> str:
    """postgresql+asyncpg://... یا postgresql+psycopg2://... را به فرمتی که
    ابزارهای خط‌فرمان pg_dump/psql می‌فهمند (postgresql://...) تبدیل می‌کند."""
    return database_url.replace("+asyncpg", "").replace("+psycopg2", "")


def _find_pg_binary(name: str) -> str:
    """
    مسیر کامل ابزار pg_dump/psql را پیدا می‌کند — نه فقط با تکیه بر متغیر
    محیطی PATH فرآیند (که مثلاً وقتی بک‌اند به‌عنوان یک سرویس Systemd اجرا
    می‌شود، ممکن است عمداً محدود به پوشه venv باشد و /usr/bin را نداشته
    باشد — دقیقاً همان چیزی که باعث شکست این قابلیت شد)، بلکه با جست‌وجوی
    مسیرهای رایج نصب PostgreSQL هم، تا مستقل از تنظیمات محیطی سرویس همیشه کار کند.
    """
    found = shutil.which(name)
    if found:
        return found
    candidate_dirs = ["/usr/bin", "/usr/local/bin", "/usr/lib/postgresql"]
    for d in candidate_dirs:
        base = Path(d)
        if not base.exists():
            continue
        # /usr/lib/postgresql/<version>/bin/pg_dump — جدیدترین نسخه نصب‌شده اولویت دارد
        for candidate in sorted(base.glob(f"**/{name}"), reverse=True):
            if candidate.is_file():
                return str(candidate)
    return name  # آخرین راه‌حل: به همان نام خام تکیه می‌کنیم


def _find_alembic_binary() -> str:
    """
    alembic همیشه در همان venv کنار خودِ Python در حال اجراست — پس ساده‌ترین
    و مطمئن‌ترین راه، استفاده از sys.executable (نه تکیه بر PATH) است؛ دقیقاً
    همان درسی که از باگ PATH محدودِ pg_dump گرفتیم.
    """
    venv_bin = Path(sys.executable).resolve().parent
    candidate = venv_bin / "alembic"
    if candidate.exists():
        return str(candidate)
    found = shutil.which("alembic")
    return found or "alembic"


async def create_backup_archive() -> bytes:
    settings = get_settings()
    libpq_url = _to_libpq_url(settings.DATABASE_URL)
    pg_dump_path = _find_pg_binary("pg_dump")

    with tempfile.TemporaryDirectory() as tmp_dir:
        dump_path = Path(tmp_dir) / "database.sql"

        try:
            proc = await asyncio.create_subprocess_exec(
                pg_dump_path,
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
                raise BackupError(f"pg_dump ناموفق بود (کد {proc.returncode}): {stderr.decode(errors='ignore')[:800]}")
        except FileNotFoundError as e:
            raise BackupError(
                f"ابزار pg_dump روی این سرور پیدا نشد (مسیر بررسی‌شده: {pg_dump_path}) — "
                "بسته postgresql-client باید نصب باشد."
            ) from e
        except OSError as e:
            raise BackupError(f"اجرای pg_dump ناموفق بود: {e}") from e

        manifest = {
            "app_name": settings.APP_NAME,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "format": "faipco-portal-backup-v1",
            "restore_instructions": (
                "برای بازیابی روی همین سرور (جایگزینی داده فعلی): "
                "sudo bash install.sh --restore-in-place /path/to/this-file.zip | "
                "برای نصب تازه روی سرور دیگر (Clone): "
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


# مقداری که کاربر باید عیناً تایپ کند تا Restore واقعاً اجرا شود — یک لایه
# محافظتی اضافه، مستقل از تأیید سمت فرانت‌اند (چون فرانت‌اند قابل‌دورزدن است).
RESTORE_CONFIRMATION_PHRASE = "RESTORE"


async def restore_from_archive(archive_bytes: bytes, confirm_phrase: str) -> None:
    """
    بازیابی کامل از یک بکاپ — از داخل خودِ پنل وب. مراحل به‌ترتیب:
      1. اعتبارسنجی عبارت تأیید (لایه محافظتی سمت سرور)
      2. باز کردن Zip و اعتبارسنجی وجود database.sql/secrets.json
      3. اجرای Migration های آخرین کد (alembic upgrade head) — تا Schema
         حتی اگر بکاپ از نسخه قدیمی‌تر کد باشد، به‌روز باشد
      4. پاک‌کردن کامل داده فعلی + بارگذاری داده بکاپ، هر دو در یک
         Transaction واحد (BEGIN...COMMIT) — یعنی اگر هر خطایی وسط بارگذاری
         پیش بیاید، کل عملیات Rollback می‌شود و داده فعلی دست‌نخورده می‌ماند؛
         هرگز در یک حالت نیمه‌خراب رها نمی‌شود.
      5. جایگزینی کلیدهای رمزنگاری حیاتی در .env با کلیدهای همان بکاپ —
         وگرنه رمز عبور اتصال دیتابیس سایت‌های بازیابی‌شده دیگر قابل‌رمزگشایی
         نیست.
    ری‌استارت خودِ سرویس (تا کلیدهای جدید .env واقعاً بارگذاری شوند) مسئولیت
    فراخوان این تابع است — چون باید بعد از پاسخ HTTP انجام شود.
    """
    if confirm_phrase != RESTORE_CONFIRMATION_PHRASE:
        raise BackupError(f'برای تأیید، باید دقیقاً عبارت «{RESTORE_CONFIRMATION_PHRASE}» ارسال شود.')

    settings = get_settings()
    libpq_url = _to_libpq_url(settings.DATABASE_URL)
    psql_path = _find_pg_binary("psql")
    alembic_path = _find_alembic_binary()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        try:
            with zipfile.ZipFile(BytesIO(archive_bytes)) as zf:
                zf.extractall(tmp_path)
        except zipfile.BadZipFile as e:
            raise BackupError("فایل بکاپ معتبر نیست (فرمت Zip قابل‌خواندن نیست).") from e

        dump_path = tmp_path / "database.sql"
        secrets_path = tmp_path / "secrets.json"
        if not dump_path.exists() or not secrets_path.exists():
            raise BackupError("فایل بکاپ نامعتبر است — database.sql یا secrets.json داخلش نیست.")

        try:
            backup_secrets = json.loads(secrets_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise BackupError("فایل secrets.json داخل بکاپ قابل‌خواندن نیست.") from e

        required_keys = {"DB_CREDENTIALS_ENCRYPTION_KEY", "SECRET_KEY", "VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY"}
        if not required_keys.issubset(backup_secrets.keys()):
            raise BackupError("فایل secrets.json داخل بکاپ ناقص است.")

        # ---------- مرحله ۱: Migration های آخرین کد ----------
        try:
            proc = await asyncio.create_subprocess_exec(
                alembic_path,
                "upgrade",
                "head",
                cwd=str(Path(__file__).resolve().parent.parent.parent),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise BackupError(f"اجرای Migration ها ناموفق بود: {stderr.decode(errors='ignore')[:800]}")
        except FileNotFoundError as e:
            raise BackupError(f"ابزار alembic پیدا نشد (مسیر بررسی‌شده: {alembic_path}).") from e

        # ---------- مرحله ۲: پاک‌کردن + بارگذاری، در یک Transaction واحد ----------
        combined_sql_path = tmp_path / "combined_restore.sql"
        truncate_block = """
BEGIN;

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename != 'alembic_version')
    LOOP
        EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' RESTART IDENTITY CASCADE';
    END LOOP;
END $$;

"""
        with open(combined_sql_path, "w", encoding="utf-8") as out_f:
            out_f.write(truncate_block)
            out_f.write(dump_path.read_text(encoding="utf-8"))
            out_f.write("\nCOMMIT;\n")

        try:
            proc = await asyncio.create_subprocess_exec(
                psql_path,
                libpq_url,
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                str(combined_sql_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise BackupError(
                    f"بازیابی دیتابیس ناموفق بود — هیچ تغییری اعمال نشد (Transaction کامل Rollback شد): "
                    f"{stderr.decode(errors='ignore')[:800]}"
                )
        except FileNotFoundError as e:
            raise BackupError(f"ابزار psql پیدا نشد (مسیر بررسی‌شده: {psql_path}).") from e

        # ---------- مرحله ۳: جایگزینی کلیدهای رمزنگاری در .env ----------
        _update_env_secrets(backup_secrets)


def _update_env_secrets(secrets: dict[str, str]) -> None:
    """فقط همان چند خط کلید رمزنگاری را در backend/.env جایگزین می‌کند —
    بقیه تنظیمات (DATABASE_URL، DOMAIN و...) دست‌نخورده می‌مانند."""
    if not _ENV_FILE_PATH.exists():
        raise BackupError(f"فایل .env پیدا نشد: {_ENV_FILE_PATH}")

    keys_to_replace = {
        "DB_CREDENTIALS_ENCRYPTION_KEY": secrets["DB_CREDENTIALS_ENCRYPTION_KEY"],
        "SECRET_KEY": secrets["SECRET_KEY"],
        "VAPID_PUBLIC_KEY": secrets["VAPID_PUBLIC_KEY"],
        "VAPID_PRIVATE_KEY": secrets["VAPID_PRIVATE_KEY"],
    }

    lines = _ENV_FILE_PATH.read_text(encoding="utf-8").splitlines()
    replaced_keys = set()
    new_lines = []
    for line in lines:
        matched = False
        for key, value in keys_to_replace.items():
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={value}")
                replaced_keys.add(key)
                matched = True
                break
        if not matched:
            new_lines.append(line)

    # کلیدهایی که توی .env فعلی اصلاً وجود نداشتند (بعید، ولی برای اطمینان) اضافه می‌شوند
    for key, value in keys_to_replace.items():
        if key not in replaced_keys:
            new_lines.append(f"{key}={value}")

    _ENV_FILE_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
