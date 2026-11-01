"""
کارهای پس‌زمینه‌ی بکاپ (docs/backup.md): بکاپ دستی و آماده‌سازی بازیابی از نسخه‌ی روی سرور.
هر دو در Task جدا با Session جدا اجرا می‌شوند تا درخواست HTTP منتظر نماند؛ بکاپ همان Advisory Lock بکاپ زمان‌بندی‌شده را
می‌گیرد (دو بکاپ هم‌زمان یا بکاپ هم‌زمان با پاک‌سازی فایل‌های موقت اتوماسیون اجرا نمی‌شود).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("faipco.backup")

_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.get_running_loop().create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


# ---------- بکاپ دستی ----------


async def _manual_backup(user_id: int | None, send: bool) -> None:
    from app.core.scheduler import _BACKUP_LOCK_KEY, _advisory_unlock, _try_advisory_lock
    from app.db.session import AsyncSessionLocal
    from app.models.backup_v4 import BackupRun
    from app.services.backup_settings_service import run_scheduled_backup

    async with AsyncSessionLocal() as db:
        if not await _try_advisory_lock(db, _BACKUP_LOCK_KEY):
            db.add(BackupRun(
                set_id=uuid.uuid4().hex, trigger="manual", status="failed", started_by=user_id,
                message="بکاپ دیگری (یا پاک‌سازی فایل‌های موقت) در حال اجراست؛ چند دقیقه بعد دوباره امتحان کنید.",
                finished_at=datetime.now(timezone.utc),
            ))
            await db.commit()
            return
        try:
            await run_scheduled_backup(db, trigger="manual", user_id=user_id, send_to_destinations=send)
        except Exception:  # noqa: BLE001
            logger.exception("بکاپ دستی ناموفق بود")
        finally:
            await _advisory_unlock(db, _BACKUP_LOCK_KEY)


def start_manual_backup(user_id: int | None, send_to_destinations: bool) -> None:
    _spawn(_manual_backup(user_id, send_to_destinations))


# ---------- بازیابی از نسخه‌ی روی سرور ----------


def _stage_state_path() -> Path:
    from app.services.backup_service import _private_dir

    return _private_dir() / "restore-stage.json"


def write_stage_state(phase: str, message: str = "", filename: str | None = None) -> None:
    try:
        _stage_state_path().write_text(json.dumps({
            "phase": phase, "message": message, "filename": filename,
            "at": datetime.now(timezone.utc).isoformat(),
        }, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        logger.warning("ثبت وضعیت آماده‌سازی بازیابی ناموفق بود")


def read_stage_state() -> dict | None:
    try:
        return json.loads(_stage_state_path().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


UPLOAD_CHUNK = 1 << 20


async def save_upload(file) -> Path:
    """فایل بکاپ آپلودی را تکه‌تکه (بدون خواندن کامل در RAM) در پوشه‌ی خصوصی بازیابی ذخیره می‌کند."""
    from app.services.backup_service import BackupError, _private_dir

    dst = _private_dir() / "upload.zip"
    try:
        dst.unlink(missing_ok=True)
        with open(dst, "xb") as out:
            while True:
                block = await file.read(UPLOAD_CHUNK)
                if not block:
                    break
                out.write(block)
    except OSError as e:
        dst.unlink(missing_ok=True)
        raise BackupError(f"ذخیره‌ی فایل بکاپ روی سرور ناموفق بود: {e}") from None
    os.chmod(dst, 0o600)
    return dst


async def _restore_upload(path: Path, password: str | None) -> None:
    from app.services.backup_archive import ArchiveError, stage_zip
    from app.services.backup_service import BackupError, _restore_staging_dir, schedule_restore

    try:
        write_stage_state("staging", "باز کردن فایل و بررسی همه‌ی فایل‌ها…")
        result = await asyncio.to_thread(stage_zip, path, _restore_staging_dir(), password)
        path.unlink(missing_ok=True)
        write_stage_state(
            "scheduled",
            "بکاپ قدیمی (فقط دیتابیس) — بازیابی شروع شد." if result["legacy"]
            else f"بکاپ سالم است ({result['file_count']} فایل آپلودی)؛ بازیابی شروع شد.",
        )
        await asyncio.to_thread(schedule_restore, result["dump"], result["files_dir"])
    except (ArchiveError, BackupError) as e:
        path.unlink(missing_ok=True)
        write_stage_state("failed", str(e))
    except Exception as e:  # noqa: BLE001
        path.unlink(missing_ok=True)
        logger.exception("آماده‌سازی بازیابی ناموفق بود")
        write_stage_state("failed", f"آماده‌سازی بازیابی ناموفق بود: {e}")


def start_restore_upload(path: Path, password: str | None) -> None:
    write_stage_state("staging", "در صف…")
    _spawn(_restore_upload(path, password))


STALE_RUN_HOURS = 3


async def close_stale_runs() -> int:
    """
    ردیف‌های «running» قدیمی‌تر از STALE_RUN_HOURS (فرآیند با ری‌استارت/خرابی قطع شده) «ناموفق — قطع‌شده» می‌شوند تا دکمه‌ی
    ساخت بکاپ برای همیشه قفل نماند. در شروع هر Worker و پیش از هر نمای کلی صدا زده می‌شود.
    """
    from datetime import timedelta

    from sqlalchemy import update

    from app.db.session import AsyncSessionLocal
    from app.models.backup_v4 import BackupRun

    cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_RUN_HOURS)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(BackupRun)
            .where(BackupRun.status == "running", BackupRun.started_at < cutoff)
            .values(status="failed", finished_at=datetime.now(timezone.utc),
                    message="قطع‌شده: فرآیند ساخت بکاپ کامل نشد (ری‌استارت یا خرابی سرویس).")
        )
        await db.commit()
        return result.rowcount or 0
