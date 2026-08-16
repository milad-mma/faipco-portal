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


def get_restore_status() -> dict:
    """
    وضعیت فعلی آخرین Restore را برمی‌گرداند — با خواندن لاگ + پرسیدن از
    خودِ systemd آیا Unit موقت هنوز در حال اجراست. توجه: در همان چند ثانیه‌ای
    که خودِ سرویس بک‌اند دارد Stop/Start می‌شود، این Endpoint هم موقتاً در
    دسترس نیست (چون بخشی از همان سرویس است) — فرانت‌اند باید این حالت را با
    Retry کردن مدیریت کند، نه خطا نشان دادن.
    """
    log_content = ""
    if _RESTORE_LOG_PATH.exists():
        log_content = _RESTORE_LOG_PATH.read_text(encoding="utf-8", errors="ignore")

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
    برخلاف نسخه‌های قبلی، اینجا کل کار واقعی به یک Scope کاملاً مستقل و جدا
    از systemd (با systemd-run) واگذار می‌شود که:
      ۱. اول خودِ سرویس بک‌اند را کامل متوقف می‌کند
      ۲. بعد pg_restore را اجرا می‌کند
      ۳. Migration های آخرین کد را اجرا می‌کند
      ۴. سرویس را دوباره بالا می‌آورد

    چرا systemd-run لازم بود (نه فقط setsid): تلاش قبلی از یک فرآیند
    setsid‌شده (ولی هنوز زیرمجموعه Cgroup خودِ faipco-backend.service)
    استفاده می‌کرد — همان لحظه که آن اسکریپت دستور «متوقف‌کردن
    faipco-backend» را صادر می‌کرد، systemd کل Cgroup آن سرویس (که خودِ
    همین اسکریپت هم داخلش بود) را می‌کشت، درست بعد از چاپ «در حال توقف
    سرویس» و قبل از رسیدن به pg_restore — یعنی هیچ‌وقت واقعاً بازیابی
    اجرا نمی‌شد. systemd-run یک Scope واقعاً جدا (و به‌عنوان root) می‌سازد
    که از این Cgroup Kill در امان است.
    """
    settings = get_settings()
    libpq_url = _to_libpq_url(settings.DATABASE_URL)
    pg_restore_path = _find_pg_binary("pg_restore")
    alembic_path = _find_alembic_binary()
    backend_dir = Path(__file__).resolve().parent.parent.parent

    # نکته حیاتی: خودِ این تابع با کاربر www-data اجرا می‌شود، ولی خودِ
    # اسکریپت (چند خط پایین‌تر) با systemd-run به‌عنوان root اجرا می‌شود —
    # یعنی هرکدام این‌ها لاگ را بسازند/دست بزنند، مالکش همان کاربر می‌شود.
    # اگر اینجا (www-data) سعی کنیم فایل لاگِ ساخته‌شده توسط تلاش قبلی
    # (که مالکش root بود) را پاک کنیم، چون /tmp با Sticky Bit است، www-data
    # اجازه حذف فایل root را ندارد و با PermissionError کل این تابع (حتی
    # قبل از رسیدن به systemd-run) شکست می‌خورد — دقیقاً همان چیزی که باعث
    # پیام مبهم «راه‌اندازی ناموفق بود» شد. راه‌حل: اصلاً از این‌جا لاگ را
    # پاک نمی‌کنیم؛ به‌جایش خودِ اسکریپت (که همیشه به‌عنوان root اجرا
    # می‌شود) با ">" (نه ">>") آن را از نو می‌سازد — همیشه یک‌دست، همیشه
    # مالکش root.

    # این اسکریپت از داخل systemd-run --collect به‌عنوان root اجرا می‌شود
    # (نگاه کنید پایین‌تر) — پس دیگر نیازی به sudo داخل خودِ اسکریپت نیست.
    script = f"""
set +e
exec > {_RESTORE_LOG_PATH} 2>&1
echo "=== Restore started: $(date -Iseconds) ==="

echo "Stopping faipco-backend..."
systemctl stop faipco-backend
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
systemctl start faipco-backend

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

    # اجرا در یک Scope کاملاً مستقل از systemd، به‌عنوان root — نه زیرمجموعه
    # Cgroup سرویس فعلی. sudo -n دقیقاً همان دستور ثابتی است که در sudoers
    # مجاز شده (نگاه کنید install.sh) — هیچ آرگومان دیگری قابل‌تزریق نیست.
    # چون systemd-run معمولاً بلافاصله بعد از ساخت Scope برمی‌گردد (منتظر
    # اتمام خودِ اسکریپت نمی‌ماند)، همین‌جا synchronous صبر می‌کنیم تا از
    # موفقیت خودِ «راه‌اندازی» مطمئن شویم — اگر مثلاً sudoers درست تنظیم
    # نشده باشد، همین‌جا با یک خطای واضح متوجه می‌شویم، نه با یک لاگ خالی
    # و سکوت کامل.
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
