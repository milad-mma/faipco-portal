"""Durable, bounded Web Push dispatch, distinct from the OA business outbox.

PostgreSQL producers enqueue in the business transaction. External database
producers use an independent committed transaction. The scheduler owns
all provider I/O. A provider acceptance is NOT an OS display or a read receipt.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import cast, func, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.employee import Employee
from app.models.notice import Notice, NoticeStatus
from app.models.notice_read import NoticeRead
from app.models.push_dispatch import PushDispatchDelivery, PushDispatchJob
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.services.push_service import PushService, eligible_subscriptions

logger = logging.getLogger("faipco.push.dispatch")
BATCH_SIZE = 20
RETRY_WINDOW = timedelta(days=7)
MAX_ATTEMPTS = 32
DEVICE_WAIT_INTERVAL = timedelta(minutes=5)
# Give the client time to persist its new authenticated Service Worker marker
# after /push/subscribe returns. Never restore the previous session binding.
DEVICE_REGISTRATION_GRACE = timedelta(seconds=30)
# Explicit producers only. Legacy generic jobs have no trusted object/recipient
# context for historical replay; keep their original one-shot policy.
DEFERRED_MODULES = frozenset({"advance", "loan", "leave", "photo", "family",
                              "insurance", "evaluation", "feedback", "birthday",
                              "login_security", "careers"})


def can_defer(job):
    if job.notice_id is not None:
        return True
    parts = getattr(job, "key", "").split(":", 4)
    return (len(parts) == 5 and parts[0] == "dispatch"
            and parts[1] in DEFERRED_MODULES and all(parts[2:])
            and (parts[1] != "leave" or (parts[2].isdigit()
                 and parts[3].partition(".")[0].isdigit() and "." in parts[3])))


# Shared transaction lock with OA transport, all workers. Never acquired by HTTP producers.
PUSH_TRANSPORT_LOCK = 875312021


def utcnow():
    return datetime.now(timezone.utc)


def dispatch_origin() -> str:
    return get_settings().FRONTEND_URL.rstrip("/")


async def wake_waiting_jobs(db, user_id: int):
    """Best-effort fast path after an authenticated subscription is saved.

    Only still-live waiting jobs for the exact account. The normal scheduler
    remains the recovery mechanism if these rows are locked or this hint fails.
    Never send from an HTTP handler, revive terminal rows, expand recipients,
    or shorten a provider backoff for a different account.
    """
    from app.models.office_automation import OaNotificationOutbox

    now = utcnow()
    due = now + DEVICE_REGISTRATION_GRACE
    jobs = (select(PushDispatchJob.id).where(
        PushDispatchJob.origin == dispatch_origin(),
        PushDispatchJob.status == "pending",
        PushDispatchJob.last_error == "awaiting_eligible_devices",
        PushDispatchJob.next_attempt_at > due,
        PushDispatchJob.deadline_at > due,
        cast(PushDispatchJob.user_ids, JSONB).contains([user_id]),
    ).order_by(PushDispatchJob.next_attempt_at, PushDispatchJob.id).limit(100)
      .with_for_update(skip_locked=True))
    await db.execute(update(PushDispatchJob).where(PushDispatchJob.id.in_(jobs))
                     .values(next_attempt_at=due).execution_options(synchronize_session=False))
    oa = (select(OaNotificationOutbox.id).where(
        OaNotificationOutbox.status == "pending",
        OaNotificationOutbox.last_error == "awaiting_eligible_devices",
        OaNotificationOutbox.next_attempt_at > due,
        OaNotificationOutbox.created_at > due - RETRY_WINDOW,
        cast(OaNotificationOutbox.payload, JSONB)["_delivery"]["recipient_user_ids"].contains([user_id]),
    ).order_by(OaNotificationOutbox.next_attempt_at, OaNotificationOutbox.id).limit(100)
      .with_for_update(skip_locked=True))
    await db.execute(update(OaNotificationOutbox).where(OaNotificationOutbox.id.in_(oa))
                     .values(next_attempt_at=due).execution_options(synchronize_session=False))


def retry_delay(attempts: int) -> timedelta:
    return timedelta(seconds=min(6 * 3600, 30 * (2 ** min(max(attempts - 1, 0), 10))))


async def enqueue_notice_push(db, notice: Notice, *, user_ids: set[int] | None = None, resend=False):
    """Idempotent initial publication; each explicit resend is a new event.

    No commit here: the caller commits the business record AND this job together.
    No historical migration/backfill. A future publication is not pushed early.
    """
    now = utcnow()
    due = max(now, notice.publish_at or now)
    kind = getattr(notice.notice_type, "value", notice.notice_type) or "normal"
    priority = getattr(notice.priority, "value", notice.priority) or "normal"
    key = f"dispatch:notice:{notice.id}:{uuid4().hex if resend else 'publish'}"
    url = f"/notices?type={kind}" if kind in ("payroll", "attendance_card") else "/notices"
    stmt = insert(PushDispatchJob).values(
        key=key, origin=dispatch_origin(), notice_id=notice.id,
        user_ids=sorted(user_ids) if user_ids is not None else None,
        url=url, priority=priority, notice_type=kind, body=None,
        status="pending", initialized=False, target_count=0, no_device_count=0,
        next_attempt_at=due, deadline_at=due + RETRY_WINDOW,
    ).on_conflict_do_nothing(index_elements=[PushDispatchJob.key])
    await db.execute(stmt)


def business_event_key(module: str, object_id, event_id, kind: str) -> str:
    """A stable, searchable server-generated key; never include message content."""
    import hashlib
    key = f"dispatch:{module}:{object_id}:{event_id}:{kind}"
    if len(key) > 100:
        key = f"dispatch:{module}:{hashlib.sha256(key.encode()).hexdigest()}"
    if len(key) > 100:
        raise ValueError("Invalid push event module")
    return key


async def enqueue_event_push(db, user_ids, url, body=None, priority="normal", notice_type="normal", *,
                             event_key, lifetime=RETRY_WINDOW):
    """Add a job in the caller's PostgreSQL transaction; NEVER commit here.

    No provider I/O. A rollback of the domain operation rolls back its job.
    Even zero-recipient events have a traceable terminal record. Callers own commit.
    """
    if not event_key.startswith("dispatch:") or len(event_key) > 100:
        raise ValueError("Invalid internal push event key")
    ids = sorted(set(user_ids))
    now = utcnow()
    await db.execute(insert(PushDispatchJob).values(
        key=event_key, origin=dispatch_origin(), user_ids=ids,
        url=url, body=body if ids else None, priority=priority, notice_type=notice_type,
        status="pending" if ids else "no_targets", initialized=not ids,
        target_count=len(ids), no_device_count=0,
        next_attempt_at=now, deadline_at=now + lifetime,
        finished_at=None if ids else now,
        last_error=None if ids else "no_recipient_account",
    ).on_conflict_do_nothing(index_elements=[PushDispatchJob.key]))


async def enqueue_generic_push(user_ids, url, body=None, priority="normal", notice_type="normal", *, key=None):
    """Compatibility entry point for callers without a shared business transaction."""
    import hashlib
    ids = sorted(set(user_ids))
    if not ids:
        return
    job_key = "dispatch:generic:" + (hashlib.sha256(key.encode()).hexdigest() if key else uuid4().hex)
    async with AsyncSessionLocal() as db:
        await enqueue_event_push(db, ids, url, body, priority, notice_type, event_key=job_key)
        await db.commit()
    logger.info("Push durably queued: key=%s target_users=%s", job_key, len(ids))


async def current_audience(db, job, now):
    """None means the notice is no longer eligible; empty set is valid."""
    if job.notice_id is None:
        from app.services.push_audience import restrict_business_audience
        return await restrict_business_audience(db, job)
    # Local import avoids a cycle with notice publication.
    from app.services.notice_service import NoticeService

    notice = (await db.execute(select(Notice).options(selectinload(Notice.targets))
                              .where(Notice.id == job.notice_id))).scalar_one_or_none()
    if (notice is None or notice.is_deleted or notice.status != NoticeStatus.published
            or (notice.publish_at and notice.publish_at > now)
            or (notice.expire_at and notice.expire_at < now)):
        return None
    audience = await NoticeService(db)._resolve_audience_user_ids(notice)
    if job.user_ids is not None:
        audience.intersection_update(job.user_ids)
    if not audience:
        return set()
    # Match list_for_user: new employees do not receive historical notices.
    visible_at = notice.publish_at or notice.created_at
    if visible_at:
        joined_later = (await db.execute(select(User.id).join(Employee, Employee.id == User.employee_id)
                       .where(User.id.in_(audience), Employee.created_at > visible_at))).scalars().all()
        audience.difference_update(joined_later)
    read = (await db.execute(select(NoticeRead.user_id).where(NoticeRead.notice_id == notice.id))).scalars().all()
    return audience.difference(read)


async def covered_users(db, job):
    return set((await db.execute(select(PushDispatchDelivery.user_id).where(
        PushDispatchDelivery.job_id == job.id,
        PushDispatchDelivery.status.in_(("pending", "accepted")),
    ).distinct())).scalars().all())


async def add_devices(db, job, audience, now):
    """Only snapshot IDs; never persist endpoint URLs or encryption keys."""
    if not audience:
        return set()
    stmt = eligible_subscriptions(audience).with_only_columns(
        PushSubscription.id, PushSubscription.session_id, PushSubscription.user_id,
        maintain_column_froms=True,
    )
    rows = (await db.execute(stmt)).all()
    for start in range(0, len(rows), 500):
        await db.execute(insert(PushDispatchDelivery).values([
            dict(job_id=job.id, subscription_id=sid, session_id=session_id, user_id=uid,
                 status="pending", attempts=0, next_attempt_at=now)
            for sid, session_id, uid in rows[start:start + 500]
        ]).on_conflict_do_nothing(index_elements=[PushDispatchDelivery.job_id,
            PushDispatchDelivery.subscription_id, PushDispatchDelivery.session_id]))
    return {row[2] for row in rows}


async def initialize_job(db, job, audience, now):
    """Snapshot intended accounts and current active devices before provider I/O."""
    job.user_ids = sorted(audience)
    job.target_count = len(audience)
    found = await add_devices(db, job, audience, now)
    job.no_device_count = len(audience - found)
    job.initialized = True
    if not audience or (not found and not can_defer(job)):
        job.status = "no_devices" if audience else "no_targets"
        job.finished_at = now
        job.body = None
        logger.warning("Push job %s: %s (%s users)", job.id, job.status, job.target_count)
    elif not found:
        # Retain the original event and body until the recipient has an eligible
        # session, the audience changes, or its original lifetime expires.
        job.next_attempt_at = min(now + DEVICE_WAIT_INTERVAL, job.deadline_at)
        job.last_error = "awaiting_eligible_devices"


def apply_delivery_result(delivery, result, now, deadline, *, error=None, retry_after=None):
    """Only retry failed devices. Provider acceptance is explicitly named accepted."""
    delivery.attempts += 1
    if result == "sent":
        delivery.status = "accepted"
        delivery.accepted_at = now
        delivery.last_error = None
    elif result in ("stale", "ineligible", "permanent"):
        delivery.status = "failed" if result == "permanent" else result
        delivery.last_error = error or result
    elif delivery.attempts >= MAX_ATTEMPTS or now >= deadline:
        delivery.status = "failed"
        delivery.last_error = ("retry_exhausted:" + (error or "provider_error"))[:120]
    else:
        delivery.status = "pending"
        delivery.last_error = error or "provider_or_network_error"
        delay = retry_delay(delivery.attempts)
        if retry_after is not None:
            delay = max(delay, timedelta(seconds=retry_after))
        if error in ("http_401", "http_403"):
            delay = max(delay, timedelta(minutes=15))
        delivery.next_attempt_at = min(now + delay, deadline)


async def finish_if_ready(db, job, now, audience):
    await db.flush()
    states = dict((await db.execute(select(PushDispatchDelivery.status, func.count())
                  .where(PushDispatchDelivery.job_id == job.id)
                  .group_by(PushDispatchDelivery.status))).all())
    waiting = audience - await covered_users(db, job) if can_defer(job) else set()
    if can_defer(job):
        job.no_device_count = len(waiting)
    if states.get("pending", 0) or waiting:
        next_times = []
        if states.get("pending", 0):
            next_times.append((await db.execute(select(func.min(PushDispatchDelivery.next_attempt_at))
                               .where(PushDispatchDelivery.job_id == job.id,
                                      PushDispatchDelivery.status == "pending"))).scalar_one())
        if waiting:
            next_times.append(now + DEVICE_WAIT_INTERVAL)
        job.next_attempt_at = min([*next_times, job.deadline_at])
        job.last_error = "awaiting_eligible_devices" if waiting else None
        return
    accepted = states.get("accepted", 0)
    missed = job.no_device_count or states.get("failed", 0) or states.get("stale", 0) or states.get("ineligible", 0) or states.get("expired", 0)
    job.status = ("partial" if missed else "accepted") if accepted else "not_accepted"
    job.finished_at = now
    job.body = None
    job.last_error = "unaccepted_targets_or_devices" if missed else None
    logger.info("Push job %s finished: status=%s device_results=%s users_without_devices=%s",
                job.id, job.status, states, job.no_device_count)


async def process_job(db, job, now):
    if now >= job.deadline_at:
        await db.execute(update(PushDispatchDelivery).where(
            PushDispatchDelivery.job_id == job.id, PushDispatchDelivery.status == "pending"
        ).values(status="expired", last_error="retry_window_elapsed"))
        job.status = "expired"
        job.finished_at = now
        job.last_error = "retry_window_elapsed"
        job.body = None
        return
    audience = await current_audience(db, job, now)
    if audience is None:
        await db.execute(update(PushDispatchDelivery).where(
            PushDispatchDelivery.job_id == job.id, PushDispatchDelivery.status == "pending"
        ).values(status="ineligible", last_error="notice_no_longer_visible"))
        job.status = "cancelled"
        job.finished_at = now
        job.body = None
        return
    if not job.initialized:
        await initialize_job(db, job, audience, now)
        return  # persist snapshot before contacting provider, even if worker dies
    # Recover only accounts with NO accepted or pending delivery. An account
    # which already received provider acceptance must not get old events again
    # just because it logs in on another device. The unique binding constraint
    # also prevents a terminally failed binding from being retried as a new one.
    if can_defer(job):
        await add_devices(db, job, audience - await covered_users(db, job),
                          now + DEVICE_REGISTRATION_GRACE)
    candidates = (await db.execute(select(PushDispatchDelivery).where(
        PushDispatchDelivery.job_id == job.id, PushDispatchDelivery.status == "pending",
        PushDispatchDelivery.next_attempt_at <= now,
    ).order_by(PushDispatchDelivery.next_attempt_at, PushDispatchDelivery.id).limit(BATCH_SIZE))).scalars().all()
    # Two historical bindings may use the same endpoint ID. Never mix them in
    # a batch whose transport result is keyed by subscription ID.
    batch = list({d.subscription_id: d for d in reversed(candidates)}.values())
    if batch and can_defer(job) and job.notice_id is None:
        from app.services.push_audience import restrict_delivery_audience
        candidates_users = {d.user_id for d in batch} & audience
        permitted = await restrict_delivery_audience(db, job, candidates_users, now)
        audience = (audience - candidates_users) | permitted
    eligible = [d for d in batch if d.user_id in audience]
    for delivery in batch:
        if delivery.user_id not in audience:
            delivery.status = "ineligible"
            delivery.last_error = "recipient_or_notice_changed"
    if eligible:
        try:
            async with AsyncSessionLocal() as push_db:
                stats = await PushService(push_db).notify_users(
                    {d.user_id for d in eligible}, url=job.url, body=job.body,
                    priority=job.priority, notice_type=job.notice_type, return_stats=True,
                    notification_key=job.key,
                    ttl_seconds=max(0, int((job.deadline_at - utcnow()).total_seconds())),
                    session_bindings={d.subscription_id: d.session_id for d in eligible},
                )
            # An empty result from a configured service is ineligibility, not success.
            if stats is None or stats.get("configured") is False:
                results = {d.subscription_id: "failed" for d in eligible}
            else:
                results = {item["id"]: item for item in stats.get("results", [])}
        except Exception as exc:
            logger.warning("Push job %s provider batch failed: %s", job.id, type(exc).__name__)
            results = {d.subscription_id: "failed" for d in eligible}
        completed_at = utcnow()
        for delivery in eligible:
            result = results.get(delivery.subscription_id, "ineligible")
            if isinstance(result, dict):
                apply_delivery_result(delivery, result["status"], completed_at, job.deadline_at,
                                      error=result.get("error"), retry_after=result.get("retry_after"))
            else:
                apply_delivery_result(delivery, result, completed_at, job.deadline_at)
    await finish_if_ready(db, job, utcnow(), audience)


async def drain_push_dispatch_jobs(limit=12):
    """One bounded batch per locked job/transaction, concurrent worker safe.

    A crash after provider acceptance but before commit can resend the same key;
    the Service Worker deduplicates it. No accepted device is retried normally.
    """
    processed = 0
    for _ in range(limit):
        async with AsyncSessionLocal() as db:
            now = utcnow()
            if not await db.scalar(select(func.pg_try_advisory_xact_lock(PUSH_TRANSPORT_LOCK))):
                break
            job = (await db.execute(select(PushDispatchJob).where(
                PushDispatchJob.origin == dispatch_origin(), PushDispatchJob.status == "pending",
                PushDispatchJob.next_attempt_at <= now,
            ).order_by(PushDispatchJob.next_attempt_at, PushDispatchJob.id).limit(1)
              .with_for_update(skip_locked=True))).scalar_one_or_none()
            if job is None:
                break
            job_id = job.id
            try:
                await process_job(db, job, now)
                await db.commit()
            except Exception as exc:
                await db.rollback()
                # Do not hot-loop on a persistent DB/template error. Never log
                # endpoint/auth keys or custom notification text.
                logger.error("Push job %s processing failed: %s", job_id, type(exc).__name__)
                await db.execute(update(PushDispatchJob).where(
                    PushDispatchJob.id == job_id, PushDispatchJob.status == "pending"
                ).values(next_attempt_at=utcnow() + timedelta(minutes=1),
                         last_error=type(exc).__name__[:120]))
                await db.commit()
            processed += 1
    return processed
