"""
ارسال Web Push در پس‌زمینه (خارج از مسیر درخواست HTTP).

ارسال webpush به FCM/سرویس مرورگر ممکن است چند ثانیه طول بکشد یا Timeout بخورد؛
درخواستی که اعلان را تولید می‌کند نباید منتظر آن بماند. این ماژول ارسال را به‌صورت
Task پس‌زمینه با Session جدا زمان‌بندی می‌کند و فوراً برمی‌گردد.

کاربرد: شناسه‌ی گیرندگان را با Session درخواست حساب کنید، سپس schedule_push را صدا بزنید.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from app.services.push_service import PushService

logger = logging.getLogger(__name__)

# Task های پس‌زمینه‌ی ارسال Push (نگه‌داشتن مرجع تا GC آن‌ها را وسط کار جمع نکند)
_background_push_tasks: set[asyncio.Task] = set()


def schedule_push(
    user_ids: set[int] | Iterable[int],
    url: str,
    body: str | None = None,
    priority: str = "normal",
    notice_type: str = "normal",
) -> None:
    """
    ارسال Push به کاربران user_ids را به‌صورت Task پس‌زمینه زمان‌بندی می‌کند و فوراً برمی‌گردد.
    اگر لیست گیرندگان خالی باشد هیچ کاری نمی‌کند. خطاهای ارسال فقط لاگ می‌شوند.
    """
    ids = set(user_ids)
    if not ids:
        return
    task = asyncio.create_task(_send(ids, url, body, priority, notice_type))
    _background_push_tasks.add(task)
    task.add_done_callback(_background_push_tasks.discard)


async def _send(
    user_ids: set[int],
    url: str,
    body: str | None,
    priority: str,
    notice_type: str,
) -> None:
    """ارسال واقعی با Session جدا؛ هرگز استثنا پرتاب نمی‌کند (Push نباید خطای کاربر شود)."""
    from app.db.session import AsyncSessionLocal  # import محلی برای جلوگیری از import حلقه‌ای

    try:
        async with AsyncSessionLocal() as db:
            await asyncio.wait_for(
                PushService(db).notify_users(
                    set(user_ids),
                    url=url,
                    priority=priority,
                    notice_type=notice_type,
                    body=body,
                ),
                timeout=120,
            )
    except Exception:  # noqa: BLE001 - Push هرگز نباید خطای کاربر شود
        logger.exception("ارسال Push پس‌زمینه با خطا مواجه شد (url=%s, گیرندگان=%d)", url, len(user_ids))
