"""
سرویس بررسی و اعمال آپدیت از پنل، و اجرای بررسی‌های سلامت (check.sh):

۱. check_for_update(): فقط می‌پرسد «آخرین نسخه منتشرشده در GitHub چیست؟»
   و با نسخه فعلی مقایسه می‌کند. کاملاً Read-Only، بدون هیچ اثری روی سرور.
   این تنها بخشی از کل برنامه است که به اینترنت وابسته است — و کاملاً
   اختیاری/غیرمسدودکننده: اگر GitHub در دسترس نبود، فقط پیام مناسب
   برمی‌گردد، هیچ بخش دیگری از برنامه تحت تأثیر قرار نمی‌گیرد.

۲. schedule_update()/get_update_status(): همان الگوی Restore دیتابیس
   (systemd-run تا فرآیند هنگام Restart سرویس faipco-backend توسط install.sh
   همراه Cgroup سرویس کشته نشود). به‌جای یک اسکریپت دست‌ساز، مستقیماً همان
   install.sh روی سرور اجرا می‌شود — یعنی این قابلیت عملاً معادل اجرای دستی
   sudo bash install.sh از طریق SSH است، فقط از پنل. این یک تصمیم آگاهانه
   و پذیرفته‌شده است (نه یک محدودیت امنیتی سبک‌تر) — چون این عملیات همان
   قدرت کامل نصب/آپدیت (نصب پکیج سیستمی، تغییر تنظیمات Nginx/سیستم‌عامل)
   را از راه دور در اختیار می‌گذارد، فقط پشت همان مجوز Admin کامل که
   برای Backup/Restore هم لازم است.

۳. schedule_checks()/get_check_status(): اجرای scripts/check.sh --log در
   پس‌زمینه و خواندن نتیجه از /var/log/faipco-check.log.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import httpx

from app.core.config import get_settings


class UpdateError(Exception):
    """خطای قابل‌نمایش به کاربر در راه‌اندازی آپدیت یا بررسی سلامت."""
    pass


_UPDATE_LOG_PATH = Path("/var/log/faipco-install.log")  # لاگی که install.sh به آن Append می‌کند
_UPDATE_OFFSET_MARKER = Path("/tmp/faipco-update-log-offset")  # اندازه لاگ در لحظه شروع آپدیت فعلی

UPDATE_CONFIRMATION_PHRASE = "UPDATE"  # عبارتی که کاربر باید برای تأیید آپدیت بفرستد


def _clean_tag(raw: str) -> str:
    """از خروجی git describe (که ممکن است مثل v1.0.0-beta.1-1-g27d3737 باشد)
    فقط قسمت تگ اصلی را جدا می‌کند — چون -N-gHASH یعنی «N کامیت بعد از این
    تگ»، نه یک نسخه متفاوت."""
    return re.sub(r"-\d+-g[0-9a-f]+$", "", raw.strip())


async def check_for_update() -> dict:
    """
    آخرین تگ مخزن GitHub را با APP_VERSION فعلی مقایسه می‌کند (فقط خواندنی).
    خروجی: dict با checked، current_version، update_channel، latest_version، has_update، release_url.
    """
    settings = get_settings()
    current = _clean_tag(settings.APP_VERSION)

    # دریافت فهرست تگ‌های مخزن از GitHub API
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"https://api.github.com/repos/{settings.GITHUB_REPO}/tags",
                headers={"Accept": "application/vnd.github+json"},
            )
            response.raise_for_status()
            tags = response.json()
    except Exception:
        # بدون خطا برمی‌گردد (checked=False) — اگر اینترنت یا GitHub در دسترس
        # نباشد، کاربر فقط یک پیام مناسب می‌بیند، نه یک خطای بحرانی.
        return {
            "checked": False,
            "current_version": settings.APP_VERSION,
            "update_channel": settings.UPDATE_CHANNEL,
            "latest_version": None,
            "has_update": False,
            "release_url": None,
        }

    # مخزن هیچ تگی ندارد
    if not tags:
        return {
            "checked": True,
            "current_version": settings.APP_VERSION,
            "update_channel": settings.UPDATE_CHANNEL,
            "latest_version": None,
            "has_update": False,
            "release_url": None,
        }

    latest = tags[0]["name"]  # GitHub تگ‌ها را جدیدترین اول برمی‌گرداند
    # نسخه‌های dev/unknown (اجرای خارج از git) هرگز «آپدیت دارد» نشان داده نمی‌شوند
    has_update = current != "dev" and current != "unknown" and _clean_tag(current) != latest

    return {
        "checked": True,
        "current_version": settings.APP_VERSION,
        "update_channel": settings.UPDATE_CHANNEL,
        "latest_version": latest,
        "has_update": has_update,
        "release_url": f"https://github.com/{settings.GITHUB_REPO}/releases/tag/{latest}",
    }


def schedule_update(confirm_phrase: str) -> None:
    """
    ورودی: عبارت تأیید. اجرای install.sh را در پس‌زمینه (systemd-run، root) راه‌اندازی می‌کند و منتظر اتمام نمی‌ماند.
    خطا: UpdateError برای عبارت اشتباه، نبود install.sh یا شکست راه‌اندازی.
    """
    if confirm_phrase != UPDATE_CONFIRMATION_PHRASE:
        raise UpdateError(f'برای تأیید، باید دقیقاً عبارت «{UPDATE_CONFIRMATION_PHRASE}» ارسال شود.')

    install_dir = Path(__file__).resolve().parent.parent.parent.parent  # ریشه پروژه
    install_script = install_dir / "install.sh"
    if not install_script.exists():
        raise UpdateError(f"فایل install.sh پیدا نشد: {install_script}")

    # قبل از شروع، اندازه فعلی لاگ را ثبت می‌کنیم — چون install.sh هربار به
    # همان فایل لاگ Append می‌کند (نه از نو می‌سازد)، بدون این علامت‌گذاری
    # get_update_status() ممکن است پیام موفقیت یک اجرای قبلی را با همین
    # اجرا اشتباه بگیرد.
    current_size = _UPDATE_LOG_PATH.stat().st_size if _UPDATE_LOG_PATH.exists() else 0
    _UPDATE_OFFSET_MARKER.write_text(str(current_size), encoding="utf-8")

    # همان الگوی schedule_restore (backup_service.py): اجرای install.sh در یک
    # Unit مستقل systemd به‌عنوان root، تا با Restart سرویس faipco-backend کشته نشود.
    # --setenv=HOME=/root لازم است چون Unit موقت systemd-run متغیر HOME ندارد و
    # «git config --global» در install.sh بدون آن با خطای "$HOME not set" متوقف می‌شود.
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


_CHECK_LOG_PATH = Path("/var/log/faipco-check.log")  # خروجی check.sh --log


def schedule_checks() -> None:
    """
    اجرای «بررسی‌های سلامت پروژه» (scripts/check.sh --log) از پنل، با همان الگوی آپدیت: یک Scope مستقل systemd به‌عنوان root
    (تست Migration به ساخت دیتابیس موقت با کاربر postgres نیاز دارد)؛ مجوزش
    در sudoers (install.sh) است. خروجی در /var/log/faipco-check.log.
    فقط می‌خواند/تست می‌کند - هیچ چیزی در پروژه یا دیتابیس واقعی تغییر نمی‌دهد.
    خطا: UpdateError اگر اسکریپت نباشد، بررسی دیگری در حال اجرا باشد یا راه‌اندازی شکست بخورد.
    """
    install_dir = Path(__file__).resolve().parent.parent.parent.parent
    script = install_dir / "scripts" / "check.sh"
    if not script.exists():
        raise UpdateError(f"اسکریپت بررسی پیدا نشد: {script}")
    if get_check_status()["is_running"]:
        raise UpdateError("یک بررسی هنوز در حال اجراست.")
    # راه‌اندازی check.sh در Unit موقت faipco-check (بدون انتظار برای اتمام)
    result = subprocess.run(
        [
            "sudo",
            "-n",
            "/usr/bin/systemd-run",
            "--unit=faipco-check",
            "--collect",
            "--setenv=HOME=/root",
            "/bin/bash",
            str(script),
            "--log",
        ],
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise UpdateError(
            "راه‌اندازی بررسی ناموفق بود (احتمالاً قانون sudoers هنوز اضافه نشده - یک بار آپدیت از پنل "
            "یا اجرای install.sh آن را اضافه می‌کند): "
            f"{result.stderr.decode(errors='ignore')[:500]}"
        )


def get_check_status() -> dict:
    """
    وضعیت آخرین بررسی سلامت را از لاگ و systemctl می‌خواند.
    خروجی: dict با log، is_running، is_passed، is_failed.
    """
    log_content = ""
    if _CHECK_LOG_PATH.exists():
        try:
            log_content = _CHECK_LOG_PATH.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            log_content = ""
    # آیا Unit موقت faipco-check هنوز در حال اجراست
    is_unit_active = False
    try:
        result = subprocess.run(["systemctl", "is-active", "faipco-check"], capture_output=True, timeout=5)
        is_unit_active = result.stdout.decode().strip() in {"active", "activating"}
    except Exception:
        pass
    # نتیجه نهایی از خط RESULT در لاگ تشخیص داده می‌شود
    is_passed = "[CHECK] RESULT: PASS" in log_content
    is_failed = "[CHECK] RESULT: FAIL" in log_content
    # پروسه تمام شده ولی خط نتیجه در لاگ نیست (کشته شده/قطع شده) → شکست، نه «در حال اجرا» تا ابد
    if log_content and not is_unit_active and not is_passed and not is_failed:
        is_failed = True
        log_content += "\n[CHECK] RESULT: FAIL (بررسی بدون خط نتیجه پایان یافت - لاگ ناقص)"
    return {
        "log": log_content,
        "is_running": is_unit_active,
        "is_passed": is_passed,
        "is_failed": is_failed,
    }


def get_update_status() -> dict:
    """
    وضعیت آپدیت جاری را از بخش جدید لاگ install.sh و systemctl می‌خواند.
    خروجی: dict با log، is_running، is_finished، is_failed.
    """
    if not _UPDATE_OFFSET_MARKER.exists() or not _UPDATE_LOG_PATH.exists():
        return {"log": "", "is_running": False, "is_finished": False, "is_failed": False}

    # فقط بخشی از لاگ که بعد از شروع آپدیت فعلی نوشته شده خوانده می‌شود
    try:
        offset = int(_UPDATE_OFFSET_MARKER.read_text(encoding="utf-8").strip())
    except ValueError:
        offset = 0

    with open(_UPDATE_LOG_PATH, "rb") as f:
        f.seek(offset)
        log_content = f.read().decode("utf-8", errors="ignore")

    # آیا Unit موقت faipco-update هنوز در حال اجراست
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

    # پیام‌های پایانی install.sh برای موفقیت/شکست
    is_finished = "updated successfully" in log_content or "installed successfully" in log_content
    is_failed = "Install failed at line" in log_content

    return {
        "log": log_content,
        "is_running": is_unit_active or (bool(log_content) and not is_finished and not is_failed),
        "is_finished": is_finished,
        "is_failed": is_failed,
    }
