"""Durable, transactionally recorded Office Automation push delivery.

At-least-once semantics: a worker dying after a provider accepted a push but
before the DB commit may result in one duplicate on retry. The outbox never
mutates access grants or the letter and must not include confidential content.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select

from app.db.session import AsyncSessionLocal
from app.core.oa_access_rules import can
from app.core.permission_grants import grants_subquery
from app.models.office_automation import (OaApprovalStep, OaLetter, OaLetterAccess, OaNotificationLog, OaNotificationOutbox, OaNotificationPref)
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.services import notification_templates
from app.services.push_service import PushService, eligible_subscriptions, bindings_are_ready
from app.services.push_dispatch import (
    PUSH_TRANSPORT_LOCK, RETRY_WINDOW, DEVICE_WAIT_INTERVAL, DEVICE_REGISTRATION_GRACE,
)

logger = logging.getLogger("faipco.automation.push")
MAX_ATTEMPTS = 10


def next_retry(attempts: int) -> timedelta:
    # Cap to one hour to avoid bursts if the push provider is unavailable.
    return timedelta(seconds=min(3600, 30 * 2 ** min(max(attempts - 1, 0), 7)))


async def _current_recipient(db, payload):
    """Re-use the domain view rule, including direct grants and confidentiality."""
    match = re.fullmatch(r"/automation/letters/(\d+)", payload["url"])
    if not match:
        return set(), None, {}
    letter = await db.get(OaLetter, int(match[1]))
    if letter is None or letter.discarded_at is not None:
        return set(), None, {}
    employee_id = payload["employee_id"]
    rows = (await db.execute(select(OaLetterAccess).where(
        OaLetterAccess.letter_id == letter.id, OaLetterAccess.employee_id == employee_id
    ))).scalars().all()
    info = {"status": letter.status, "confidentiality": letter.confidentiality}
    if not can("view", letter=info, rows=[dict(source=r.source, can_act=r.can_act,
            can_refer=r.can_refer, revoked_at=r.revoked_at) for r in rows]):
        return set(), None, {}
    if payload.get("event") == "approval":
        if not await db.scalar(select(OaApprovalStep.id).where(
            OaApprovalStep.letter_id == letter.id, OaApprovalStep.round == letter.approval_round,
            OaApprovalStep.approver_employee_id == employee_id, OaApprovalStep.status == "active").limit(1)):
            return set(), None, {}
    grants = grants_subquery()
    ids = set((await db.execute(select(User.id).where(
        User.employee_id == employee_id, User.is_active.is_(True),
        or_(User.is_superuser.is_(True), User.id.in_(select(grants.c.user_id)
             .where(grants.c.code == "automation.access")))))).scalars().all())
    if letter.confidentiality == "confidential" or payload["text_key"] == "automation.confidential":
        return ids, "automation.confidential", {}
    return ids, payload["text_key"], payload.get("values", {})


async def _snapshot_bindings(db, user_ids):
    stmt = eligible_subscriptions(user_ids).with_only_columns(
        PushSubscription.id, PushSubscription.session_id, maintain_column_froms=True)
    return {str(sid): session_id for sid, session_id in (await db.execute(stmt)).all()}


async def _deliver_one(db, event: OaNotificationOutbox) -> tuple[str, str | None]:
    """Persist device/session snapshot before network I/O; never guess a legacy binding."""
    p = event.payload
    if await db.scalar(select(OaNotificationLog.id).where(OaNotificationLog.key == event.key)):
        return "skipped", None
    if getattr(event, "created_at", None) and datetime.now(timezone.utc) >= event.created_at + RETRY_WINDOW:
        return "failed", "retry_window_elapsed"
    pref = await db.get(OaNotificationPref, p["employee_id"])
    if pref is not None and p.get("event") in (pref.disabled_events or []):
        db.add(OaNotificationLog(key=event.key))
        return "skipped", None
    user_ids, text_key, values = await _current_recipient(db, p)
    if not user_ids:
        db.add(OaNotificationLog(key=event.key))
        return "skipped", "recipient_or_letter_changed"
    tracking = p.get("_delivery")
    if tracking is None:
        bindings = await _snapshot_bindings(db, user_ids)
        event.payload = {**p, "_delivery": {"remaining": sorted(map(int, bindings)),
            "bindings": bindings, "sent": [], "stale": [], "failed": [],
            "recipient_user_ids": sorted(user_ids),
            "seen_bindings": sorted(f"{sid}:{session_id}" for sid, session_id in bindings.items())}}
        if not bindings:
            # Waiting for a login is NOT a failed provider attempt. Keep the
            # business event, original accounts and confidentiality rules.
            return "waiting", "awaiting_eligible_devices"
        return "initialized", None
    # Only a snapshot made by this version can be rebound. Historical tracking
    # without recipient identity must keep its original session-only policy.
    recoverable = "recipient_user_ids" in tracking and "seen_bindings" in tracking
    if recoverable:
        user_ids &= set(tracking["recipient_user_ids"])
        if not user_ids:
            db.add(OaNotificationLog(key=event.key))
            return "skipped", "recipient_or_letter_changed"
    remaining, sent, stale = (set(tracking[k]) for k in ("remaining", "sent", "stale"))
    failed = set(tracking.get("failed", []))
    bindings = tracking.get("bindings", {})
    # Old retry rows did not record the session. Never attach them to a new login.
    stale.update(sid for sid in remaining if str(sid) not in bindings)
    remaining.difference_update(stale)
    if recoverable and not remaining and not sent:
        # Rebind only an event with no previous provider acceptance for this
        # employee. Never retry an already attempted subscription/session pair.
        current = await _snapshot_bindings(db, user_ids)
        seen = set(tracking["seen_bindings"])
        new = {sid: session_id for sid, session_id in current.items()
               if f"{sid}:{session_id}" not in seen}
        if not new:
            return "waiting", "awaiting_eligible_devices"
        new_ids = set(map(int, new))
        event.payload = {**p, "_delivery": {**tracking,
            "remaining": sorted(new_ids), "bindings": {**bindings, **new},
            "stale": sorted(stale - new_ids), "failed": sorted(failed - new_ids),
            "seen_bindings": sorted(seen | {f"{sid}:{session_id}" for sid, session_id in new.items()})}}
        # Commit the new bindings before contacting the provider, and allow the
        # new login to persist its Service Worker marker on the device.
        return "rebound", None
    body = await notification_templates.render(db, p["site_id"], text_key, **values)
    batch = set(sorted(remaining)[:20])
    retry_after = 0
    if batch:
        async with AsyncSessionLocal() as push_db:
            stats = await asyncio.wait_for(PushService(push_db).notify_users(
                user_ids, url=p["url"], priority=p.get("priority", "normal"), body=body,
                return_stats=True, subscription_ids=batch, notification_key=event.key,
                session_bindings={sid: bindings[str(sid)] for sid in batch},
                ttl_seconds=max(0, int((event.created_at + RETRY_WINDOW - datetime.now(timezone.utc)).total_seconds()))
                    if getattr(event, "created_at", None) else 24 * 3600,
            ), timeout=120)
        if not stats or stats.get("configured") is False:
            raise RuntimeError("Push service is not configured or returned no status")
        results = stats.get("results", [])
        missing = batch - {int(item["id"]) for item in results}
        stale.update(missing)
        remaining.difference_update(missing)
        for item in results:
            sid = int(item["id"])
            if sid not in batch:
                continue
            status = item["status"]
            if status in ("sent", "stale", "permanent", "ineligible"):
                (sent if status == "sent" else failed if status == "permanent" else stale).add(sid)
                remaining.discard(sid)
            else:
                retry_after = max(retry_after, item.get("retry_after") or 0,
                                  900 if item.get("error") in ("http_401", "http_403") else 0)
    event.payload = {**p, "_delivery": {**tracking, "remaining": sorted(remaining), "sent": sorted(sent),
        "stale": sorted(stale), "failed": sorted(failed), "bindings": bindings,
        "retry_after": retry_after}}
    if remaining:
        # A new batch is not a retry when all attempted subscriptions were terminal.
        if not (remaining & batch):
            return "initialized", None
        return "pending", f"Push pending for {len(remaining)} subscription(s); {len(sent)} accepted"
    if recoverable and not sent:
        return "waiting", "awaiting_eligible_devices"
    db.add(OaNotificationLog(key=event.key))
    if failed:
        return "failed", f"{len(failed)} permanent failure(s); {len(sent)} accepted"
    return ("sent" if sent else "skipped"), (f"{len(stale)} stale/unbound device(s)" if stale else None)


async def drain_oa_outbox(limit: int = 20, keys: list[str] | None = None) -> int:
    """Process pending jobs safely with multiple FastAPI workers.

    Row-level SKIP LOCKED prevents concurrent workers delivering the same job.
    Every delivered, skipped or deferred row is committed separately.
    """
    count = 0
    for _ in range(max(0, min(limit, 30))):
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            if not await db.scalar(select(func.pg_try_advisory_xact_lock(PUSH_TRANSPORT_LOCK))):
                break
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
                if status in ("initialized", "rebound"):
                    delay = timedelta(0)
                    if status == "rebound":
                        tracking = event.payload["_delivery"]
                        bindings = {str(sid): tracking["bindings"][str(sid)] for sid in tracking["remaining"]}
                        if not await bindings_are_ready(db, bindings):
                            delay = DEVICE_REGISTRATION_GRACE
                    event.next_attempt_at = min(datetime.now(timezone.utc) + delay,
                                                event.created_at + RETRY_WINDOW)
                    event.last_error = None
                elif status == "waiting":
                    # Do not consume the provider retry budget while logged out.
                    event.next_attempt_at = min(datetime.now(timezone.utc) + DEVICE_WAIT_INTERVAL,
                                                event.created_at + RETRY_WINDOW)
                    event.last_error = error
                elif status == "pending":
                    event.attempts += 1
                    event.last_error = error
                    if event.attempts >= MAX_ATTEMPTS:
                        event.status = "failed"
                        logger.error("OA push exhausted retries (outbox_id=%s)", event.id)
                    else:
                        event.next_attempt_at = datetime.now(timezone.utc) + max(next_retry(event.attempts), timedelta(seconds=event.payload.get("_delivery", {}).get("retry_after", 0)))
                        logger.warning("OA push retry scheduled (outbox_id=%s, attempt=%s)", event.id, event.attempts)
                else:
                    event.status = status
                    event.sent_at = datetime.now(timezone.utc)
                    event.last_error = error
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
                event.last_error = type(exc).__name__[:120]
                if event.attempts >= MAX_ATTEMPTS:
                    event.status = "failed"
                    logger.error("OA push exhausted retries (outbox_id=%s)", event.id)
                else:
                    event.next_attempt_at = datetime.now(timezone.utc) + next_retry(event.attempts)
                    logger.warning("OA push retry scheduled (outbox_id=%s, attempt=%s)", event.id, event.attempts)
                await db.commit()
                count += 1
    return count
