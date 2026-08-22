"""
نمونه‌برداری دوره‌ای مصرف منابع خودِ سرور (CPU/RAM/دیسک) — برای نمودار
«مصرف سرور» در پنل Admin.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import psutil
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.server_stat import ServerStat

logger = logging.getLogger("faipco.server_stats")

# دیسکی که پرتال واقعاً رویش نصب است — نه لزوماً هر Mount Point دیگری که
# ممکن است روی همین سرور باشد (مثلاً یک دیسک جدا برای Backup)
DISK_PATH = "/"
RETENTION_DAYS = 30


def _sample_sync() -> dict:
    """
    این تابع Blocking است (psutil.cpu_percent با interval واقعاً ۱ ثانیه
    صبر می‌کند تا مصرف CPU را دقیق اندازه بگیرد) — عمداً از asyncio.to_thread
    صدا زده می‌شود، نه مستقیم await، تا Event Loop اصلی برنامه در این ۱
    ثانیه هرگز بلاک نشود (وگرنه همه درخواست‌های هم‌زمان کاربران دیگر هم
    برای همان ۱ ثانیه معطل می‌ماندند).
    """
    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(DISK_PATH)
    return {
        "cpu_percent": cpu_percent,
        "ram_percent": mem.percent,
        "ram_used_mb": mem.used // (1024 * 1024),
        "ram_total_mb": mem.total // (1024 * 1024),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / (1024**3), 2),
        "disk_total_gb": round(disk.total / (1024**3), 2),
    }


async def record_server_stats(db: AsyncSession) -> None:
    try:
        sample = await asyncio.to_thread(_sample_sync)
        stat = ServerStat(recorded_at=datetime.now(timezone.utc), **sample)
        db.add(stat)

        # پاک‌سازی نمونه‌های قدیمی‌تر از RETENTION_DAYS — همین‌جا و همین لحظه
        # (نه یک Job جدا)، چون هزینه‌اش کم است (یک DELETE با ایندکس روی
        # recorded_at) و از رشد نامحدود این جدول در طول زمان جلوگیری می‌کند.
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
        await db.execute(delete(ServerStat).where(ServerStat.recorded_at < cutoff))

        await db.commit()
    except Exception:  # noqa: BLE001 - هرگز نباید زمان‌بند اصلی برنامه را متوقف کند
        logger.exception("نمونه‌برداری مصرف سرور ناموفق بود")


async def get_server_stats(db: AsyncSession, days: int = 7) -> list[ServerStat]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(ServerStat).where(ServerStat.recorded_at >= cutoff).order_by(ServerStat.recorded_at)
    )
    return list(result.scalars().all())
