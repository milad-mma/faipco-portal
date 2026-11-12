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


async def _deliver_one(db, event: OaNotificationOutbox) -> tuple[str, str | None]:
    """Send only outstanding subscriptions; persist partial successes in outbox payload.

    The caller holds this event row locked, so two workers cannot choose the
    same targets. A failure of one subscription does not re-send to others.
    The resulting payload and next retry time commit atomically.
    """
    p = event.payload
    if await db.scalar(select(OaNotificationLog.id).where(OaNotificationLog.key == event.key)):
        return "skipped", None
    pref = await db.get(OaNotificationPref, p["employee_id"])
    if pref is not None and p.get("event") in (pref.disabled_events or []):
        db.add(OaNotificationLog(key=event.key))
        return "skipped", None
    user_ids = set((await db.execute(
        select(User.id).where(User.employee_id == p["employee_id"], User.is_active.is_(True))
    )).scalars().all())
    if not user_ids:
        raise RuntimeError("No active OA recipient account")
    body = await notification_templates.render(db, p["site_id"], p["text_key"], **p.get("values", {}))
    tracking = p.get("_delivery")
    # Snapshot the FIRST round's subscriptions. New devices do not receive an
    # old event just because they were registered while that event was retrying.
    remaining = set(tracking["remaining"]) if tracking is not None else None
    if remaining is not None and not remaining:
        db.add(OaNotificationLog(key=event.key))
        return ("sent" if tracking["sent"] else "skipped"), None
    async with AsyncSessionLocal() as push_db:
        stats = await asyncio.wait_for(
            PushService(push_db).notify_users(
                user_ids, url=p["url"], priority=p.get("priority", "normal"),
                body=body, return_stats=True,
                subscription_ids=set(remaining) if remaining is not None else None,
                notification_key=event.key,
            ), timeout=120,
        )
    if not stats or stats.get("configured") is False:
        raise RuntimeError("Push service is not configured or returned no status")

    results = stats.get("results", [])
    if tracking is None:
        initial = {int(item["id"]) for item in results}
        tracking = {"remaining": sorted(initial), "sent": [], "stale": []}
        remaining = initial
    # An endpoint deleted/unbound/revoked during a retry is no longer eligible:
    # mark it complete, never resurrect an old device subscription.
    returned = {int(item["id"]) for item in results}
    sent = set(tracking["sent"])
    stale = set(tracking["stale"])
    stale.update(remaining - returned)
    remaining &= returned
    for item in results:
        sid = int(item["id"])
        if item["status"] == "sent":
            sent.add(sid)
            remaining.discard(sid)
        elif item["status"] == "stale":
            stale.add(sid)
            remaining.discard(sid)
    event.payload = {**p, "_delivery": {
        "remaining": sorted(remaining), "sent": sorted(sent), "stale": sorted(stale),
    }}
    if remaining:
        return "pending", f"Push pending for {len(remaining)} subscription(s); {len(sent)} accepted"
    db.add(OaNotificationLog(key=event.key))
    return ("sent" if sent else "skipped"), None


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
                status, error = await _deliver_one(db, event)
                if status == "pending":
                    event.attempts += 1
                    event.last_error = error
                    if event.attempts >= MAX_ATTEMPTS:
                        event.status = "failed"
                        logger.error("OA push exhausted retries (outbox_id=%s)", event.id)
                    else:
                        event.next_attempt_at = datetime.now(timezone.utc) + next_retry(event.attempts)
                        logger.warning("OA push retry scheduled (outbox_id=%s, attempt=%s)", event.id, event.attempts)
                else:
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
