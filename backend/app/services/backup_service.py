"""
سرویس پشتیبان‌گیری و بازیابی — فقط برای همین سرور (نه Clone روی سرور دیگر).

⚠️ بازطراحی کامل (v3): نسخه‌های قبلی برای «Clone به سرور دیگر» طراحی شده
بودند (--data-only + جابه‌جایی دستی کلیدهای رمزنگاری در .env) — این باعث
یک باگ واقعی شد: چون alembic_version عمداً از TRUNCATE قبل از بازیابی
مستثنی بود (تا ردیابی Migration خراب نشود)، ولی pg_dump --data-only آن را
مستثنی نمی‌کرد، هر بار یک بکاپ قدیمی‌تر بازیابی می‌شد، یک ردیف اضافه در
alembic_version می‌ماند (نه Conflict، چون مقدارش با ردیف موجود فرق داشت) —
یعنی خرابی به‌مرور در دیتابیس دنبال بکاپ‌ها می‌گشت.

طراحی جدید بسیار ساده‌تر است: یک Dump کامل (Schema + Data، نه فقط Data) از
همین سرور گرفته می‌شود؛ بازیابی هم با pg_restore --clean --if-exists انجام
می‌شود (خودش هر Object از جمله alembic_version را قبل از بازسازی درست حذف
می‌کند — نه یک TRUNCATE دستی با استثنا). چون بازیابی همیشه روی همین سرور
است، نیازی به بکاپ‌گرفتن/جابه‌جایی .env یا کلیدهای رمزنگاری نیست — همان
کلیدهای فعلی سرور معتبر می‌مانند. بعد از بازیابی، alembic upgrade head یک
بار دیگر اجرا می‌شود تا اگر بکاپ از نسخه قدیمی‌تر کد بود، Schema به آخرین
Migration های موجود برسد (بدون از‌دست‌رفتن داده‌های تازه بازیابی‌شده،
چون Migration ها تصادفاً هرگز داده حذف نمی‌کنند).
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from app.core.config import get_settings


class BackupError(Exception):
    pass


def _to_libpq_url(database_url: str) -> str:
    """postgresql+asyncpg://... یا postgresql+psycopg2://... را به فرمتی که
    ابزارهای خط‌فرمان pg_dump/pg_restore می‌فهمند (postgresql://...) تبدیل می‌کند."""
    return database_url.replace("+asyncpg", "").replace("+psycopg2", "")


def _find_pg_binary(name: str) -> str:
    """
    مسیر کامل ابزار pg_dump/pg_restore را پیدا می‌کند — نه فقط با تکیه بر
    متغیر محیطی PATH فرآیند (که مثلاً وقتی بک‌اند به‌عنوان یک سرویس Systemd
    اجرا می‌شود، ممکن است عمداً محدود به پوشه venv باشد و /usr/bin را نداشته
    باشد)، بلکه با جست‌وجوی مسیرهای رایج نصب PostgreSQL هم.
    """
    found = shutil.which(name)
    if found:
        return found
    candidate_dirs = ["/usr/bin", "/usr/local/bin", "/usr/lib/postgresql"]
    for d in candidate_dirs:
        base = Path(d)
        if not base.exists():
            continue
        for candidate in sorted(base.glob(f"**/{name}"), reverse=True):
            if candidate.is_file():
                return str(candidate)
    return name


def _find_alembic_binary() -> str:
    """alembic همیشه در همان venv کنار خودِ Python در حال اجراست."""
    venv_bin = Path(sys.executable).resolve().parent
    candidate = venv_bin / "alembic"
    if candidate.exists():
        return str(candidate)
    found = shutil.which("alembic")
    return found or "alembic"


async def create_backup_archive() -> bytes:
    """
    یک Dump کامل (Schema + Data) از دیتابیس همین سرور می‌گیرد — نه فقط
    داده. چون این بکاپ فقط برای بازیابی روی همین سرور طراحی شده (نه Clone
    به سرور دیگر)، نیازی به کلیدهای رمزنگاری/secrets.json جداگانه نیست.
    """
    settings = get_settings()
    libpq_url = _to_libpq_url(settings.DATABASE_URL)
    pg_dump_path = _find_pg_binary("pg_dump")

    with tempfile.TemporaryDirectory() as tmp_dir:
        dump_path = Path(tmp_dir) / "database.dump"

        try:
            proc = await asyncio.create_subprocess_exec(
                pg_dump_path,
                "--format=custom",
                "--no-owner",
                "--no-privileges",
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
            "format": "faipco-portal-backup-v3-fullsnapshot",
            "note": "این بکاپ فقط برای بازیابی روی همین سرور (از پنل) طراحی شده — Clone به سرور دیگر پشتیبانی نمی‌شود.",
        }

        zip_path = Path(tmp_dir) / "backup.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(dump_path, "database.dump")
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        return zip_path.read_bytes()


# مقداری که کاربر باید عیناً تایپ کند تا Restore واقعاً اجرا شود — یک لایه
# محافظتی اضافه، مستقل از تأیید سمت فرانت‌اند (چون فرانت‌اند قابل‌دورزدن است).
RESTORE_CONFIRMATION_PHRASE = "RESTORE"
_RESTORE_STAGING_DIR = Path("/tmp/faipco-restore-staging")
_RESTORE_LOG_PATH = Path("/tmp/faipco-restore.log")


def validate_and_stage_archive(archive_bytes: bytes, confirm_phrase: str) -> Path:
    """
    فقط اعتبارسنجی + آماده‌سازی — کاری با دیتابیس ندارد، پس همین‌جا (داخل
    درخواست HTTP فعلی) به‌سرعت قابل‌انجام است و خطاهای واضح (فایل خراب،
    عبارت تأیید اشتباه) فوراً به کاربر نشان داده می‌شود؛ خودِ Restore واقعی
    (که نیاز به توقف سرویس دارد) جدا انجام می‌شود — نگاه کنید به
    schedule_restore().
    """
    if confirm_phrase != RESTORE_CONFIRMATION_PHRASE:
        raise BackupError(f'برای تأیید، باید دقیقاً عبارت «{RESTORE_CONFIRMATION_PHRASE}» ارسال شود.')

    if _RESTORE_STAGING_DIR.exists():
        shutil.rmtree(_RESTORE_STAGING_DIR)
    _RESTORE_STAGING_DIR.mkdir(parents=True)

    try:
        with zipfile.ZipFile(BytesIO(archive_bytes)) as zf:
            zf.extractall(_RESTORE_STAGING_DIR)
    except zipfile.BadZipFile as e:
        raise BackupError("فایل بکاپ معتبر نیست (فرمت Zip قابل‌خواندن نیست).") from e

    dump_path = _RESTORE_STAGING_DIR / "database.dump"
    if not dump_path.exists():
        raise BackupError(
            "فایل بکاپ نامعتبر است — database.dump داخلش نیست "
            "(اگر این یک بکاپ خیلی قدیمی‌تر است، دوباره یک بکاپ تازه از همین صفحه بگیرید)."
        )
    return dump_path


def schedule_restore(dump_path: Path) -> None:
    """
    برخلاف نسخه قبلی (که pg_restore را همان لحظه، داخل همین درخواست HTTP و
    درحالی‌که خودِ سرویس هنوز کاملاً روشن بود اجرا می‌کرد)، اینجا کل کار
    واقعی به یک اسکریپت کاملاً جدا و مستقل (setsid) واگذار می‌شود که:
      ۱. اول خودِ سرویس بک‌اند را کامل متوقف می‌کند
      ۲. بعد pg_restore را اجرا می‌کند
      ۳. Migration های آخرین کد را اجرا می‌کند
      ۴. سرویس را دوباره بالا می‌آورد

    چرا این تغییر لازم بود: نسخه قبلی، سرویس را روشن نگه می‌داشت — یعنی
    همان لحظه که pg_restore سعی می‌کرد جدول‌ها را Drop/بازسازی کند، خودِ
    سرویس (با Connection Pool زنده‌اش) هنوز به همان جدول‌ها وصل بود و رویشان
    قفل داشت؛ pg_restore برای گرفتن قفل انحصاری بی‌نهایت منتظر می‌ماند —
    دقیقاً همان چیزی که باعث گیرکردن یک Restore واقعی شد. چون همین درخواست
    HTTP از داخل خودِ سرویسی می‌آید که قرار است متوقف شود، توقف سرویس باید
    از یک فرآیند کاملاً مستقل (نه از داخل همین درخواست) انجام شود — وگرنه
    خودِ این درخواست هم قبل از تمام‌شدن کشته می‌شد.
    """
    settings = get_settings()
    libpq_url = _to_libpq_url(settings.DATABASE_URL)
    pg_restore_path = _find_pg_binary("pg_restore")
    alembic_path = _find_alembic_binary()
    backend_dir = Path(__file__).resolve().parent.parent.parent

    script = f"""
set +e
exec >> {_RESTORE_LOG_PATH} 2>&1
echo "=== Restore started: $(date -Iseconds) ==="

echo "Stopping faipco-backend..."
sudo -n /usr/bin/systemctl stop faipco-backend
sleep 2

echo "Running pg_restore..."
{pg_restore_path} --clean --if-exists --single-transaction --no-owner --no-privileges \
  --dbname={libpq_url} {dump_path}
restore_exit=$?

if [ "$restore_exit" -eq 0 ]; then
  echo "Running alembic upgrade head..."
  cd {backend_dir}
  {alembic_path} upgrade head
  migrate_exit=$?
else
  echo "pg_restore failed with exit code $restore_exit — skipping migrations (--single-transaction means the database was rolled back to exactly its pre-restore state)."
  migrate_exit=1
fi

echo "Starting faipco-backend..."
sudo -n /usr/bin/systemctl start faipco-backend

rm -rf {_RESTORE_STAGING_DIR}

if [ "$restore_exit" -eq 0 ] && [ "$migrate_exit" -eq 0 ]; then
  echo "=== Restore finished successfully: $(date -Iseconds) ==="
else
  echo "=== Restore FAILED: $(date -Iseconds) — check the output above. The service was restarted regardless, on the original pre-restore data. ==="
fi
"""
    script_path = Path("/tmp/faipco-restore-run.sh")
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(0o700)

    subprocess.Popen(
        ["setsid", "sh", str(script_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
