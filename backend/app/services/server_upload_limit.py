"""
«سقف آپلود سرور» از پنل (تنظیمات سامانه؛ فقط ادمین کل) — docs/upload-limit.md

- مقدار در system_settings (`server.upload_limit_mb`، پیش‌فرض ۲۵) و فایل /var/lib/faipco/upload-limit-mb ذخیره می‌شود.
- scripts/nginx-upload-limit.sh apply (systemd-run به‌عنوان root، قانون sudoers ثابت در install.sh) آن را در
  /etc/nginx/faipco-upload-limit.conf می‌نویسد، nginx -t و reload؛ اگر تست رد شود مقدار قبلی برمی‌گردد.
- سقف حجم هر فایل در پرتال (تنظیم پیوست سایت‌ها) = این مقدار منهای ۱ مگابایت (سربار فرم آپلود).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting

SETTING_KEY = "server.upload_limit_mb"
DEFAULT_MB = 25
MIN_MB = 2
MAX_MB = 2048
MULTIPART_OVERHEAD_MB = 1
VALUE_FILE = Path("/var/lib/faipco/upload-limit-mb")
NGINX_CONF = Path("/etc/nginx/faipco-upload-limit.conf")
LOG_PATH = Path("/var/log/faipco-upload-limit.log")
UNIT = "faipco-upload-limit"


class UploadLimitError(RuntimeError):
    pass


async def get_limit_mb(db: AsyncSession) -> int:
    value = (await db.execute(select(SystemSetting.value).where(SystemSetting.key == SETTING_KEY))).scalar_one_or_none()
    try:
        mb = int(value) if value is not None else DEFAULT_MB
    except ValueError:
        mb = DEFAULT_MB
    return min(max(mb, MIN_MB), MAX_MB)


async def portal_max_file_mb(db: AsyncSession) -> int:
    """حداکثر حجم هر فایل که تنظیمات پرتال اجازه می‌دهد (سقف nginx منهای سربار فرم)."""
    return max(await get_limit_mb(db) - MULTIPART_OVERHEAD_MB, 1)


def applied_mb() -> int | None:
    """مقداری که الان واقعاً در تنظیم nginx است (اگر فایل خوانا باشد)."""
    try:
        match = re.search(r"client_max_body_size\s+(\d+)m", NGINX_CONF.read_text(encoding="utf-8"))
    except OSError:
        return None
    return int(match.group(1)) if match else None


def _unit_running() -> bool:
    try:
        out = subprocess.run(["systemctl", "is-active", UNIT], capture_output=True, timeout=5, text=True)
        return out.stdout.strip() in ("active", "activating")
    except (OSError, subprocess.SubprocessError):
        return False


def read_job() -> dict:
    text = ""
    if LOG_PATH.exists():
        try:
            text = LOG_PATH.read_text(encoding="utf-8", errors="ignore")[-8000:]
        except OSError:
            text = ""
    running = _unit_running()
    result = None
    if not running:
        if "[UPLOAD-LIMIT] RESULT: OK" in text:
            result = "ok"
        elif "[UPLOAD-LIMIT] RESULT: FAIL" in text:
            result = "fail"
    return {"log": text, "running": running, "result": result}


async def state(db: AsyncSession) -> dict:
    return {
        "limit_mb": await get_limit_mb(db),
        "applied_mb": applied_mb(),
        "portal_max_file_mb": await portal_max_file_mb(db),
        "min_mb": MIN_MB,
        "max_mb": MAX_MB,
        "job": read_job(),
    }


def validate(mb) -> int:
    try:
        value = int(mb)
    except (TypeError, ValueError):
        raise UploadLimitError("سقف آپلود باید عدد صحیح (مگابایت) باشد") from None
    if not MIN_MB <= value <= MAX_MB:
        raise UploadLimitError(f"سقف آپلود باید بین {MIN_MB} و {MAX_MB} مگابایت باشد")
    return value


async def set_limit(db: AsyncSession, mb) -> int:
    """ذخیره و اعمال روی nginx (پس‌زمینه). خطای ذخیره یا راه‌اندازی → UploadLimitError؛ commit با فراخواننده."""
    value = validate(mb)
    if _unit_running():
        raise UploadLimitError("اعمال قبلی هنوز در حال اجراست؛ چند ثانیه بعد دوباره امتحان کنید.")
    script = Path(__file__).resolve().parents[3] / "scripts" / "nginx-upload-limit.sh"
    if not script.exists():
        raise UploadLimitError(f"اسکریپت پیدا نشد: {script}")
    try:
        VALUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        VALUE_FILE.write_text(f"{value}\n", encoding="utf-8")
    except OSError as e:
        raise UploadLimitError(f"ذخیره‌ی مقدار روی سرور ناموفق بود: {e}") from None
    row = await db.get(SystemSetting, SETTING_KEY)
    if row is None:
        db.add(SystemSetting(key=SETTING_KEY, value=str(value)))
    else:
        row.value = str(value)
    result = subprocess.run(
        ["sudo", "-n", "/usr/bin/systemd-run", f"--unit={UNIT}", "--collect", "/bin/bash", str(script), "apply"],
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise UploadLimitError(
            "اعمال روی nginx راه‌اندازی نشد (قانون sudoers با آپدیت پرتال اضافه می‌شود؛ اگر تازه آپدیت کرده‌اید یک بار "
            f"دیگر آپدیت را اجرا کنید): {result.stderr.decode(errors='ignore')[:400]}"
        )
    return value
