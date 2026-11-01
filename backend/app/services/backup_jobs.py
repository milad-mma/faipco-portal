"""
کارهای پس‌زمینه‌ی بکاپ (docs/backup.md): بکاپ دستی و آماده‌سازی بازیابی از نسخه‌ی روی سرور.
هر دو در Task جدا با Session جدا اجرا می‌شوند تا درخواست HTTP منتظر نماند؛ بکاپ همان Advisory Lock بکاپ زمان‌بندی‌شده را
می‌گیرد (دو بکاپ هم‌زمان یا بکاپ هم‌زمان با پاک‌سازی فایل‌های موقت اتوماسیون اجرا نمی‌شود).
"""
from __future__ import annotations

import asyncio
import json
import logging
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


async def _restore_local(filename: str, identities: list[str]) -> None:
    from app.services.backup_archive import ArchiveError, local_path, stage_archive
    from app.services.backup_service import BackupError, _restore_staging_dir, schedule_restore

    try:
        path = local_path(filename)
        staging = _restore_staging_dir()
        write_stage_state("staging", "رمزگشایی، استخراج و بررسی هش‌ها…", filename)
        manifest = await asyncio.to_thread(stage_archive, path, staging, identities)
        files_dir = staging / "files" / "objects"
        write_stage_state(
            "scheduled",
            f"بکاپ سالم است ({manifest['files']['count']} فایل اتوماسیون)؛ بازیابی شروع شد.",
            filename,
        )
        await asyncio.to_thread(
            schedule_restore, staging / "database.dump", files_dir if files_dir.is_dir() else None
        )
    except (ArchiveError, BackupError) as e:
        write_stage_state("failed", str(e), filename)
    except Exception as e:  # noqa: BLE001
        logger.exception("آماده‌سازی بازیابی ناموفق بود")
        write_stage_state("failed", f"آماده‌سازی بازیابی ناموفق بود: {e}", filename)


def start_restore_local(filename: str, identities: list[str]) -> None:
    write_stage_state("staging", "در صف…", filename)
    _spawn(_restore_local(filename, identities))
