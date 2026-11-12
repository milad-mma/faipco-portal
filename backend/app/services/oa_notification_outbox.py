"""Durable, transactionally recorded Office Automation push delivery.

At-least-once semantics: a worker dying after a provider accepted a push but
before the DB commit may result in one duplicate on retry. The outbox never
mutates access grants or the letter and must not include confidential content.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.office_automation import OaNotificationLog, OaNotificationOutbox, OaNotificationPref
from app.models.user import User
from app.services import notification_templates
from app.services.push_service import PushService

logger = logging.getLogger("faipco.automation.push")
MAX_ATTEMPTS = 10


def next_retry(attempts: int) -> timedelta:
    # Cap to one hour to avoid bursts if the push provider is unavailable.
    return timedelta(seconds=min(3600, 30 * 2 ** min(max(attempts - 1, 0), 7)))


async def _deliver_one(db, event: OaNotificationOutbox) -> str:
    """Return 'sent' or 'skipped', raise on transient failure.

    The caller holds a FOR UPDATE SKIP LOCKED transaction on this event.
    Push subscription pruning may commit; use a DIFFERENT session for it.
    """
    p = event.payload
    # Backwards compatibility: v9.2 may have sent this key before the outbox existed.
    if await db.scalar(select(OaNotificationLog.id).where(OaNotificationLog.key == event.key)):
        return "skipped"
    pref = await db.get(OaNotificationPref, p["employee_id"])
    if pref is not None and p.get("event") in (pref.disabled_events or []):
        db.add(OaNotificationLog(key=event.key))
        return "skipped"
    user_ids = set((await db.execute(
        select(User.id).where(User.employee_id == p["employee_id"], User.is_active.is_(True))
    )).scalars().all())
    if not user_ids:
        raise RuntimeError("No active OA recipient account")
    body = await notification_templates.render(db, p["site_id"], p["text_key"], **p.get("values", {}))
    async with AsyncSessionLocal() as push_db:
        stats = await asyncio.wait_for(
            PushService(push_db).notify_users(
                user_ids, url=p["url"], priority=p.get("priority", "normal"),
                body=body, return_stats=True,
            ), timeout=60,
        )
    if not stats:
        raise RuntimeError("Push provider returned no status")
    if stats.get("attempted", 0) == 0:
        # No subscribed device exists. Keep a durable record of the intentionally
        # skipped push, while the letter is still available in its authenticated cartable.
        db.add(OaNotificationLog(key=event.key))
        return "skipped"
    if stats.get("failed", 0) or stats.get("sent", 0) == 0:
        raise RuntimeError(f"Push delivery failed: {stats}")
    db.add(OaNotificationLog(key=event.key))
    return "sent"


async def drain_oa_outbox(limit: int = 20, keys: list[str] | None = None) -> int:
    """Process pending jobs safely with multiple FastAPI workers.

    Row-level SKIP LOCKED prevents concurrent workers delivering the same job.
    Every delivered, skipped or deferred row is committed separately.
    """
    count = 0
    for _ in range(max(0, min(limit, 30))):
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            stmt = (
                select(OaNotificationOutbox)
                .where(OaNotificationOutbox.status == "pending", OaNotificationOutbox.next_attempt_at <= now)
                .order_by(OaNotificationOutbox.next_attempt_at, OaNotificationOutbox.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if keys is not None:
                if not keys:
                    return count
                stmt = stmt.where(OaNotificationOutbox.key.in_(keys))
            event = (await db.execute(stmt)).scalar_one_or_none()
            if event is None:
                break
            event_id = event.id  # rollback expires ORM attributes, including primary keys
            try:
                status = await _deliver_one(db, event)
                event.status = status
                event.sent_at = datetime.now(timezone.utc)
                event.last_error = None
                await db.commit()
                count += 1
            except Exception as exc:  # noqa: BLE001 - outbox must survive provider outages
                # A failed delivery must not leave an unusable transaction in progress.
                await db.rollback()
                event = (await db.execute(
                    select(OaNotificationOutbox).where(
                        OaNotificationOutbox.id == event_id, OaNotificationOutbox.status == "pending"
                    ).with_for_update(skip_locked=True)
                )).scalar_one_or_none()
                if event is None:
                    continue
                event.attempts += 1
                event.last_error = f"{type(exc).__name__}: {str(exc)[:500]}"[:600]
                if event.attempts >= MAX_ATTEMPTS:
                    event.status = "failed"
                    logger.error("OA push exhausted retries (outbox_id=%s)", event.id)
                else:
                    event.next_attempt_at = datetime.now(timezone.utc) + next_retry(event.attempts)
                    logger.warning("OA push retry scheduled (outbox_id=%s, attempt=%s)", event.id, event.attempts)
                await db.commit()
                count += 1
    return count
