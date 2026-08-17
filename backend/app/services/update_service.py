"""
سرویس بررسی و اعمال آپدیت از پنل — دو بخش کاملاً مستقل:

۱. check_for_update(): فقط می‌پرسد «آخرین نسخه منتشرشده در GitHub چیست؟»
   و با نسخه فعلی مقایسه می‌کند. کاملاً Read-Only، بدون هیچ اثری روی سرور.
   این تنها بخشی از کل برنامه است که به اینترنت وابسته است — و کاملاً
   اختیاری/غیرمسدودکننده: اگر GitHub در دسترس نبود، فقط پیام مناسب
   برمی‌گردد، هیچ بخش دیگری از برنامه تحت تأثیر قرار نمی‌گیرد.

۲. schedule_update()/get_update_status(): دقیقاً همان الگوی امن که برای
   Restore دیتابیس ساخته شد (systemd-run برای فرار از Cgroup Kill، چون
   install.sh در پایان کار خودِ سرویس faipco-backend را Restart می‌کند —
   یعنی همان مشکلی که باعث گیرکردن اولین تلاش Restore شد، این‌جا هم پیش
   می‌آمد). تفاوت اصلی: به‌جای یک اسکریپت دست‌ساز، مستقیماً همان install.sh
   واقعی روی سرور اجرا می‌شود — یعنی این قابلیت عملاً معادل اجرای دستی
   sudo bash install.sh از طریق SSH است، فقط از پنل. این یک تصمیم آگاهانه
   و پذیرفته‌شده است (نه یک محدودیت امنیتی سبک‌تر) — چون این عملیات همان
   قدرت کامل نصب/آپدیت (نصب پکیج سیستمی، تغییر تنظیمات Nginx/سیستم‌عامل)
   را از راه دور در اختیار می‌گذارد، فقط پشت همان مجوز Admin کامل که
   برای Backup/Restore هم لازم است.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import httpx

from app.core.config import get_settings


class UpdateError(Exception):
    pass


_UPDATE_LOG_PATH = Path("/var/log/faipco-install.log")
_UPDATE_OFFSET_MARKER = Path("/tmp/faipco-update-log-offset")

UPDATE_CONFIRMATION_PHRASE = "UPDATE"


def _clean_tag(raw: str) -> str:
    """از خروجی git describe (که ممکن است مثل v1.0.0-beta.1-1-g27d3737 باشد)
    فقط قسمت تگ اصلی را جدا می‌کند — چون -N-gHASH یعنی «N کامیت بعد از این
    تگ»، نه یک نسخه متفاوت."""
    return re.sub(r"-\d+-g[0-9a-f]+$", "", raw.strip())


async def check_for_update() -> dict:
    settings = get_settings()
    current = _clean_tag(settings.APP_VERSION)

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"https://api.github.com/repos/{settings.GITHUB_REPO}/tags",
                headers={"Accept": "application/vnd.github+json"},
            )
            response.raise_for_status()
            tags = response.json()
    except Exception:
        # عمداً بی‌سروصدا — این قابلیت اختیاری و غیرمسدودکننده است؛ اگر
        # اینترنت نبود یا GitHub در دسترس نبود، کاربر فقط یک پیام مناسب
        # می‌بیند، نه یک خطای بحرانی.
        return {
            "checked": False,
            "current_version": settings.APP_VERSION,
            "latest_version": None,
            "has_update": False,
            "release_url": None,
        }

    if not tags:
        return {
            "checked": True,
            "current_version": settings.APP_VERSION,
            "latest_version": None,
            "has_update": False,
            "release_url": None,
        }

    latest = tags[0]["name"]
    has_update = current != "dev" and current != "unknown" and _clean_tag(current) != latest

    return {
        "checked": True,
        "current_version": settings.APP_VERSION,
        "latest_version": latest,
        "has_update": has_update,
        "release_url": f"https://github.com/{settings.GITHUB_REPO}/releases/tag/{latest}",
    }


def schedule_update(confirm_phrase: str) -> None:
    if confirm_phrase != UPDATE_CONFIRMATION_PHRASE:
        raise UpdateError(f'برای تأیید، باید دقیقاً عبارت «{UPDATE_CONFIRMATION_PHRASE}» ارسال شود.')

    install_dir = Path(__file__).resolve().parent.parent.parent.parent
    install_script = install_dir / "install.sh"
    if not install_script.exists():
        raise UpdateError(f"فایل install.sh پیدا نشد: {install_script}")

    # قبل از شروع، اندازه فعلی لاگ را ثبت می‌کنیم — چون install.sh هربار به
    # همان فایل لاگ Append می‌کند (نه از نو می‌سازد)، بدون این علامت‌گذاری
    # get_update_status() ممکن است پیام موفقیت یک اجرای قبلی را با همین
    # اجرا اشتباه بگیرد.
    current_size = _UPDATE_LOG_PATH.stat().st_size if _UPDATE_LOG_PATH.exists() else 0
    _UPDATE_OFFSET_MARKER.write_text(str(current_size), encoding="utf-8")

    # دقیقاً همان الگوی schedule_restore (نگاه کنید backup_service.py) —
    # یک Scope کاملاً مستقل از systemd، به‌عنوان root، تا وقتی install.sh
    # خودش سرویس faipco-backend را Restart می‌کند، این فرآیند خودش کشته
    # نشود. --setenv=HOME=/root حیاتی است: برخلاف یک نشست تعاملی sudo،
    # Scope موقت systemd-run این متغیر را ندارد — و install.sh با
    # «git config --global» کار می‌کند که بدون HOME با خطای
    # "$HOME not set" متوقف می‌شود.
    result = subprocess.run(
        [
            "sudo",
            "-n",
            "/usr/bin/systemd-run",
            "--unit=faipco-update",
            "--collect",
            "--setenv=HOME=/root",
            "/bin/bash",
            str(install_script),
        ],
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise UpdateError(
            "راه‌اندازی فرآیند آپدیت در پس‌زمینه ناموفق بود (چیزی هنوز تغییر نکرده): "
            f"{result.stderr.decode(errors='ignore')[:500]}"
        )


def get_update_status() -> dict:
    if not _UPDATE_OFFSET_MARKER.exists() or not _UPDATE_LOG_PATH.exists():
        return {"log": "", "is_running": False, "is_finished": False, "is_failed": False}

    try:
        offset = int(_UPDATE_OFFSET_MARKER.read_text(encoding="utf-8").strip())
    except ValueError:
        offset = 0

    with open(_UPDATE_LOG_PATH, "rb") as f:
        f.seek(offset)
        log_content = f.read().decode("utf-8", errors="ignore")

    is_unit_active = False
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "faipco-update"],
            capture_output=True,
            timeout=5,
        )
        is_unit_active = result.stdout.decode().strip() == "active"
    except Exception:
        pass

    is_finished = "updated successfully" in log_content or "installed successfully" in log_content
    is_failed = "Install failed at line" in log_content

    return {
        "log": log_content,
        "is_running": is_unit_active or (bool(log_content) and not is_finished and not is_failed),
        "is_finished": is_finished,
        "is_failed": is_failed,
    }
