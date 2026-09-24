"""
سرویس پشتیبان‌گیری و بازیابی — فقط برای همین سرور (نه Clone روی سرور دیگر).

- create_backup_archive: یک Dump کامل (Schema + Data) با pg_dump --format=custom
  می‌گیرد و همراه manifest.json در یک ZIP برمی‌گرداند.
- validate_and_stage_archive: عبارت تأیید و فایل ZIP را بررسی و database.dump را
  در پوشه موقت آماده می‌کند.
- schedule_restore: یک اسکریپت shell مستقل (با systemd-run به‌عنوان root) اجرا
  می‌کند که سرویس را متوقف، Schema فعلی را کنار گذاشته، pg_restore و
  alembic upgrade head را اجرا و سرویس را دوباره روشن می‌کند؛ در صورت شکست
  داده قبلی برگردانده می‌شود.
- get_restore_status: وضعیت بازیابی را از فایل لاگ و systemctl می‌خواند.

چون بازیابی همیشه روی همین سرور است، نیازی به جابه‌جایی .env یا کلیدهای
رمزنگاری نیست. اجرای alembic upgrade head بعد از بازیابی Schema بکاپ‌های
قدیمی‌تر را به آخرین Migration می‌رساند.
"""
from __future__ import annotations

import asyncio
import json
import re
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
    """خطای قابل‌نمایش به کاربر در ساخت/اعتبارسنجی/راه‌اندازی بکاپ یا بازیابی."""
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
    # جست‌وجوی بازگشتی در مسیرهای رایج؛ sorted معکوس نسخه جدیدتر را اول می‌آورد
    candidate_dirs = ["/usr/bin", "/usr/local/bin", "/usr/lib/postgresql"]
    for d in candidate_dirs:
        base = Path(d)
        if not base.exists():
            continue
        for candidate in sorted(base.glob(f"**/{name}"), reverse=True):
            if candidate.is_file():
                return str(candidate)
    return name  # اگر پیدا نشد، همان نام خام (اجرا با FileNotFoundError شکست می‌خورد)


def _find_alembic_binary() -> str:
    """مسیر اجرایی alembic را برمی‌گرداند؛ اول کنار Python در حال اجرا (venv)، بعد در PATH."""
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
    خروجی: بایت‌های فایل ZIP شامل database.dump و manifest.json. خطا: BackupError.
    """
    settings = get_settings()
    libpq_url = _to_libpq_url(settings.DATABASE_URL)
    pg_dump_path = _find_pg_binary("pg_dump")

    with tempfile.TemporaryDirectory() as tmp_dir:
        dump_path = Path(tmp_dir) / "database.dump"

        # اجرای pg_dump با فرمت custom (قابل استفاده با pg_restore)، بدون مالک و مجوزها
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

        # اطلاعات توصیفی بکاپ که کنار dump در ZIP قرار می‌گیرد
        manifest = {
            "app_name": settings.APP_NAME,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "format": "faipco-portal-backup-v3-fullsnapshot",
            "note": "این بکاپ فقط برای بازیابی روی همین سرور (از پنل) طراحی شده — Clone به سرور دیگر پشتیبانی نمی‌شود.",
        }

        # بسته‌بندی dump و manifest در یک ZIP
        zip_path = Path(tmp_dir) / "backup.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(dump_path, "database.dump")
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        return zip_path.read_bytes()


# مقداری که کاربر باید عیناً تایپ کند تا Restore واقعاً اجرا شود — یک لایه
# محافظتی اضافه، مستقل از تأیید سمت فرانت‌اند (چون فرانت‌اند قابل‌دورزدن است).
RESTORE_CONFIRMATION_PHRASE = "RESTORE"
_RESTORE_STAGING_DIR = Path("/tmp/faipco-restore-staging")  # محل استخراج فایل بکاپ قبل از بازیابی
_RESTORE_LOG_PATH = Path("/tmp/faipco-restore.log")  # خروجی اسکریپت بازیابی


def get_restore_status() -> dict:
    """
    وضعیت فعلی آخرین Restore را برمی‌گرداند — با خواندن لاگ + پرسیدن از
    خودِ systemd آیا Unit موقت هنوز در حال اجراست. توجه: در همان چند ثانیه‌ای
    که خودِ سرویس بک‌اند دارد Stop/Start می‌شود، این Endpoint هم موقتاً در
    دسترس نیست (چون بخشی از همان سرویس است) — فرانت‌اند باید این حالت را با
    Retry کردن مدیریت کند، نه خطا نشان دادن.
    خروجی: dict با کلیدهای log، is_running، is_finished، is_failed.
    """
    log_content = ""
    if _RESTORE_LOG_PATH.exists():
        log_content = _RESTORE_LOG_PATH.read_text(encoding="utf-8", errors="ignore")

    # پرسیدن از systemd درباره فعال بودن Unit موقت faipco-restore
    is_unit_active = False
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "faipco-restore"],
            capture_output=True,
            timeout=5,
        )
        is_unit_active = result.stdout.decode().strip() == "active"
    except Exception:
        pass

    return {
        "log": log_content,
        # در حال اجرا: Unit فعال است، یا لاگ شروع شده ولی هنوز پیام پایان (موفق/ناموفق) ندارد
        "is_running": is_unit_active or (bool(log_content) and "===" in log_content and "FAILED" not in log_content and "finished successfully" not in log_content),
        "is_finished": "Restore finished successfully" in log_content,
        "is_failed": "Restore FAILED" in log_content,
    }


def validate_and_stage_archive(archive_bytes: bytes, confirm_phrase: str) -> Path:
    """
    فقط اعتبارسنجی + آماده‌سازی — کاری با دیتابیس ندارد، پس همین‌جا (داخل
    درخواست HTTP فعلی) به‌سرعت قابل‌انجام است و خطاهای واضح (فایل خراب،
    عبارت تأیید اشتباه) فوراً به کاربر نشان داده می‌شود؛ خودِ Restore واقعی
    (که نیاز به توقف سرویس دارد) جدا انجام می‌شود — نگاه کنید به
    schedule_restore().
    خروجی: مسیر database.dump استخراج‌شده. خطا: BackupError.
    """
    if confirm_phrase != RESTORE_CONFIRMATION_PHRASE:
        raise BackupError(f'برای تأیید، باید دقیقاً عبارت «{RESTORE_CONFIRMATION_PHRASE}» ارسال شود.')

    # پوشه موقت از نو ساخته می‌شود تا فایل‌های تلاش قبلی باقی نمانند
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


# محل نگهداری موقت داده فعلی حین بازیابی (برای برگشت در صورت شکست)
_PRERESTORE_SCHEMA = "public_prerestore"


def schedule_restore(dump_path: Path) -> None:
    """
    ورودی: مسیر database.dump آماده‌شده. یک اسکریپت shell می‌سازد و آن را در یک
    Scope مستقل systemd (systemd-run، به‌عنوان root) اجرا می‌کند که:
      ۱. سرویس faipco-backend را متوقف می‌کند
      ۲. Schema فعلی public را به public_prerestore تغییر نام داده و public خالی می‌سازد
      ۳. pg_restore را روی Schema خالی اجرا می‌کند
      ۴. alembic upgrade head را اجرا می‌کند
      ۵. در موفقیت public_prerestore را حذف، در شکست آن را به public برمی‌گرداند
      ۶. سرویس را دوباره روشن می‌کند

    systemd-run لازم است چون فرآیندی که داخل Cgroup سرویس بک‌اند باشد هنگام
    توقف سرویس همراه آن کشته می‌شود؛ Scope جدا از این Cgroup مستقل است.
    به‌جای pg_restore --clean از بازسازی کامل Schema استفاده می‌شود، چون --clean
    هنگام Drop تک‌تک Objectها (بدون CASCADE) روی وابستگی‌ها شکست می‌خورد.
    اگر برگشت داده هم شکست بخورد، داده قبلی در public_prerestore باقی می‌ماند و در لاگ ذکر می‌شود.
    خطا: BackupError اگر راه‌اندازی systemd-run ناموفق باشد (دیتابیس دست‌نخورده می‌ماند).
    """
    settings = get_settings()
    libpq_url = _to_libpq_url(settings.DATABASE_URL)
    pg_restore_path = _find_pg_binary("pg_restore")
    psql_path = _find_pg_binary("psql")
    alembic_path = _find_alembic_binary()
    backend_dir = Path(__file__).resolve().parent.parent.parent

    # نام کاربر دیتابیس را از همان DATABASE_URL استخراج می‌کنیم — برای
    # مالک‌کردن دوباره Schema public بعد از بازسازی کاملش (پایین‌تر توضیح داده شده)
    db_user_match = re.search(r"://([^:]+):", libpq_url)
    db_user = db_user_match.group(1) if db_user_match else ""

    # فایل لاگ این‌جا پاک نمی‌شود: این تابع با www-data اجرا می‌شود و لاگ قبلی
    # مالک root دارد (در /tmp با Sticky Bit قابل حذف نیست). خودِ اسکریپت که با
    # root اجرا می‌شود لاگ را با ">" از نو می‌سازد.

    # این اسکریپت از داخل systemd-run --collect به‌عنوان root اجرا می‌شود
    # (نگاه کنید پایین‌تر) — پس دیگر نیازی به sudo داخل خودِ اسکریپت نیست.
    script = f"""
set +e
exec > {_RESTORE_LOG_PATH} 2>&1
echo "=== Restore started: $(date -Iseconds) ==="

echo "Stopping faipco-backend..."
systemctl stop faipco-backend
sleep 2

# ⚠️ داده فعلی پاک نمی‌شود - Schema فعلی فقط تغییر نام می‌دهد تا اگر بازیابی
# یا Migration شکست خورد، دقیقاً همان داده قبلی برگردانده شود.
echo "Moving current data aside (public -> {_PRERESTORE_SCHEMA}) before restoring..."
{psql_path} -v ON_ERROR_STOP=1 "{libpq_url}" -c "DROP SCHEMA IF EXISTS {_PRERESTORE_SCHEMA} CASCADE; ALTER SCHEMA public RENAME TO {_PRERESTORE_SCHEMA}; CREATE SCHEMA public; ALTER SCHEMA public OWNER TO {db_user}; GRANT ALL ON SCHEMA public TO {db_user};"
reset_exit=$?

if [ "$reset_exit" -eq 0 ]; then
  echo "Running pg_restore..."
  {pg_restore_path} --single-transaction --no-owner --no-privileges \
    --dbname={libpq_url} {dump_path}
  restore_exit=$?
else
  echo "Schema reset failed with exit code $reset_exit — aborting before touching pg_restore."
  restore_exit=1
fi

if [ "$restore_exit" -eq 0 ]; then
  echo "Running alembic upgrade head..."
  cd {backend_dir}
  {alembic_path} upgrade head
  migrate_exit=$?
else
  echo "pg_restore failed with exit code $restore_exit — skipping migrations."
  migrate_exit=1
fi

rollback_exit=0
if [ "$reset_exit" -eq 0 ]; then
  if [ "$restore_exit" -eq 0 ] && [ "$migrate_exit" -eq 0 ]; then
    echo "Dropping previous data ({_PRERESTORE_SCHEMA})..."
    {psql_path} "{libpq_url}" -c "DROP SCHEMA IF EXISTS {_PRERESTORE_SCHEMA} CASCADE;"
  else
    echo "Restore failed — putting the previous data back..."
    {psql_path} -v ON_ERROR_STOP=1 "{libpq_url}" -c "DROP SCHEMA public CASCADE; ALTER SCHEMA {_PRERESTORE_SCHEMA} RENAME TO public;"
    rollback_exit=$?
  fi
fi

echo "Starting faipco-backend..."
systemctl start faipco-backend

rm -rf {_RESTORE_STAGING_DIR}

if [ "$restore_exit" -eq 0 ] && [ "$migrate_exit" -eq 0 ]; then
  echo "=== Restore finished successfully: $(date -Iseconds) ==="
elif [ "$reset_exit" -ne 0 ]; then
  echo "=== Restore FAILED: $(date -Iseconds) — nothing was changed; the service is running on the original data. ==="
elif [ "$rollback_exit" -eq 0 ]; then
  echo "=== Restore FAILED: $(date -Iseconds) — the previous data was put back; the service is running on the original data. ==="
else
  echo "=== Restore FAILED and ROLLBACK FAILED: $(date -Iseconds) — the previous data is kept in schema {_PRERESTORE_SCHEMA}. Do not run another restore; ask for manual recovery. ==="
fi
"""
    # ذخیره اسکریپت روی دیسک با دسترسی فقط برای مالک
    script_path = Path("/tmp/faipco-restore-run.sh")
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(0o700)

    # اجرا در یک Scope کاملاً مستقل از systemd، به‌عنوان root — نه زیرمجموعه
    # Cgroup سرویس فعلی. sudo -n دقیقاً همان دستور ثابتی است که در sudoers
    # مجاز شده (نگاه کنید install.sh) — هیچ آرگومان دیگری قابل‌تزریق نیست.
    # systemd-run بلافاصله بعد از ساخت Unit برمی‌گردد (منتظر اتمام اسکریپت نمی‌ماند)؛
    # اجرای synchronous فقط موفقیت راه‌اندازی را بررسی می‌کند تا مثلاً خطای
    # sudoers به‌صورت یک خطای واضح گزارش شود.
    result = subprocess.run(
        [
            "sudo",
            "-n",
            "/usr/bin/systemd-run",
            "--unit=faipco-restore",
            "--collect",
            "/bin/sh",
            str(script_path),
        ],
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise BackupError(
            "راه‌اندازی فرآیند بازیابی در پس‌زمینه ناموفق بود (دیتابیس دست‌نخورده ماند): "
            f"{result.stderr.decode(errors='ignore')[:500]}"
        )
