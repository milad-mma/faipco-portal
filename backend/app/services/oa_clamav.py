"""
اسکن ویروس اختیاری و مدیریت ClamAV از پنل (docs/office-automation.md «اسکن اختیاری»).

- تنظیم سراسری `oa.scan_enabled` (پیش‌فرض خاموش): خاموش = فایل بعد از بررسی نوع/ساختار «سالم (بدون اسکن ویروس)» می‌شود.
- نصب/دریافت بانک/روشن/خاموش با scripts/clamav.sh در Unit موقت systemd به‌عنوان root (قانون sudoers در install.sh)؛
  منتظر پایان نمی‌ماند؛ وضعیت از /var/log/faipco-clamav.log (نشانگرهای [CLAMAV] START/RESULT) خوانده می‌شود.
- clamd خاموش = بدون مصرف RAM (بانک فقط وقتی سرویس روشن است در حافظه است).
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting

SCAN_SETTING_KEY = "oa.scan_enabled"
ACTIONS = {
    "install": "نصب و راه‌اندازی",
    "update-db": "دریافت/به‌روزرسانی بانک شناسایی",
    "start": "روشن کردن",
    "stop": "خاموش کردن",
}
LOG_PATH = Path("/var/log/faipco-clamav.log")
UNIT = "faipco-clamav"
DB_DIR = "/var/lib/clamav"


class ClamavError(RuntimeError):
    pass


async def scan_enabled(db: AsyncSession) -> bool:
    value = (await db.execute(select(SystemSetting.value).where(SystemSetting.key == SCAN_SETTING_KEY))).scalar_one_or_none()
    return value == "true"


async def set_scan_enabled(db: AsyncSession, enabled: bool) -> None:
    row = await db.get(SystemSetting, SCAN_SETTING_KEY)
    if row is None:
        db.add(SystemSetting(key=SCAN_SETTING_KEY, value="true" if enabled else "false"))
    else:
        row.value = "true" if enabled else "false"


def _script() -> Path:
    return Path(__file__).resolve().parents[3] / "scripts" / "clamav.sh"


def _unit_running() -> bool:
    try:
        out = subprocess.run(["systemctl", "is-active", UNIT], capture_output=True, timeout=5, text=True)
        return out.stdout.strip() in ("active", "activating")
    except (OSError, subprocess.SubprocessError):
        return False


def _service_state(name: str) -> str:
    try:
        out = subprocess.run(["systemctl", "is-active", name], capture_output=True, timeout=5, text=True)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def read_log() -> dict:
    """آخرین اجرای اسکریپت: متن لاگ، عملیات، در حال اجرا/موفق/ناموفق."""
    text = ""
    if LOG_PATH.exists():
        try:
            text = LOG_PATH.read_text(encoding="utf-8", errors="ignore")[-20000:]
        except OSError:
            text = ""
    action = None
    for line in text.splitlines():
        if line.startswith("[CLAMAV] START"):
            parts = line.split()
            action = parts[2] if len(parts) > 2 else None
    result = None
    if "[CLAMAV] RESULT: OK" in text:
        result = "ok"
    elif "[CLAMAV] RESULT: FAIL" in text:
        result = "fail"
    running = _unit_running()
    return {
        "log": text,
        "action": action,
        "action_label": ACTIONS.get(action or "", action),
        "running": running,
        "result": None if running else result,
    }


def system_state() -> dict:
    """نصب بودن، فایل‌های بانک و وضعیت سرویس‌ها (بدون نیاز به root)."""
    installed = bool(shutil.which("clamd") or os.path.exists("/usr/sbin/clamd"))
    db_files = []
    for path in sorted(glob.glob(os.path.join(DB_DIR, "*.cvd")) + glob.glob(os.path.join(DB_DIR, "*.cld"))):
        try:
            db_files.append({"name": os.path.basename(path), "size": os.path.getsize(path), "mtime": os.path.getmtime(path)})
        except OSError:
            continue
    return {
        "installed": installed,
        "db_files": db_files,
        "has_db": any(f["name"].startswith("main.") for f in db_files) and any(f["name"].startswith("daily.") for f in db_files),
        "daemon": _service_state("clamav-daemon") if installed else "not-installed",
        "freshclam": _service_state("clamav-freshclam") if installed else "not-installed",
    }


def run_action(action: str) -> None:
    """اجرای scripts/clamav.sh <action> در پس‌زمینه (root، systemd-run)؛ منتظر پایان نمی‌ماند."""
    if action not in ACTIONS:
        raise ClamavError("عملیات نامعتبر است")
    script = _script()
    if not script.exists():
        raise ClamavError(f"اسکریپت پیدا نشد: {script}")
    if _unit_running():
        raise ClamavError("یک عملیات ClamAV هنوز در حال اجراست؛ صبر کنید تا تمام شود.")
    result = subprocess.run(
        ["sudo", "-n", "/usr/bin/systemd-run", f"--unit={UNIT}", "--collect", "/bin/bash", str(script), action],
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise ClamavError(
            "اجرای دستور ناموفق بود (اگر تازه آپدیت کرده‌اید، قانون sudoers با همین آپدیت اضافه می‌شود؛ یک بار دیگر آپدیت را "
            f"اجرا کنید): {result.stderr.decode(errors='ignore')[:400]}"
        )
