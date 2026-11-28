"""Durable native inbox. Web fallback competes for the same leased delivery."""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import text, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from app.db.session import AsyncSessionLocal
from app.models.mobile_device import MobileDevice
from app.models.push_dispatch import AndroidNotification as Inbox, PushDispatchJob
from app.models.push_subscription import PushSubscription
from app.models.user_session import UserSession


def now():
    return datetime.now(timezone.utc)


async def register_transport(db, device, session_id):
    values = dict(user_id=device.user_id, session_id=session_id, native_device_id=device.id,
                  endpoint=f"android:{device.id}:{session_id}", p256dh="", auth="", client_ready=True)
    await db.execute(insert(PushSubscription).values(**values).on_conflict_do_update(
        index_elements=[PushSubscription.endpoint], set_={"client_ready": True}))


async def offer(sub, payload, ttl):
    expiry = now() + timedelta(seconds=ttl)
    stmt = insert(Inbox).values(device_id=sub.native_device_id, subscription_id=sub.id, session_id=sub.session_id,
        event_key=payload["notification_key"], payload=payload, state="pending", expires_at=expiry)
    async with AsyncSessionLocal() as db:
        await db.execute(stmt.on_conflict_do_nothing())
        await db.execute(text("SELECT pg_notify('faipco_android_inbox', :target)"), {"target": str(sub.native_device_id)})
        await db.commit()
    # Give a running native client the first opportunity. Never hold a DB connection while waiting.
    await asyncio.sleep(5)
    async with AsyncSessionLocal() as db:
        row = await db.scalar(select(Inbox).where(Inbox.subscription_id == sub.id,
            Inbox.session_id == sub.session_id, Inbox.event_key == payload["notification_key"]).with_for_update())
        if row.state in ("native", "web", "web_seen", "web_showing"):
            return "accepted", None
        if row.expires_at <= now() or (row.lease_until and row.lease_until > now()):
            return "pending", None
        from app.services.push_service import eligible_subscriptions
        fallback = (await db.execute(eligible_subscriptions({sub.user_id}, all_transports=True)
            .where(PushSubscription.session_id == sub.session_id, PushSubscription.native_device_id.is_(None))
            .order_by(PushSubscription.id.desc()).limit(1))).first()
        if not fallback:
            return "queued", None
        row.state, row.lease_until = "sending_web", now() + timedelta(minutes=1)
        await db.commit()
        return row.id, fallback[0]


async def finish_web(row_id, success):
    async with AsyncSessionLocal() as db:
        await db.execute(update(Inbox).where(Inbox.id == row_id, Inbox.state == "sending_web")
                         .values(state="web" if success else "pending", lease_until=now() + timedelta(minutes=2) if success else None))
        await db.commit()


async def still_allowed(db, row, user_id):
    from app.services.push_dispatch import current_audience
    if row.event_key.startswith("dispatch:"):
        job = await db.scalar(select(PushDispatchJob).where(PushDispatchJob.key == row.event_key))
        if job is None or user_id not in (await current_audience(db, job, now()) or set()):
            return False
        from app.services.push_dispatch import can_defer
        if job.notice_id is None and can_defer(job):
            from app.services.push_audience import restrict_delivery_audience
            return user_id in await restrict_delivery_audience(db, job, {user_id}, now())
        return True
    from app.models.office_automation import OaNotificationOutbox, OaNotificationPref
    from app.services.oa_notification_outbox import _current_recipient
    event = await db.scalar(select(OaNotificationOutbox).where(OaNotificationOutbox.key == row.event_key))
    if not event:
        return False
    pref = await db.get(OaNotificationPref, event.payload["employee_id"])
    if pref and event.payload.get("event") in (pref.disabled_events or []):
        return False
    recipients, _, _ = await _current_recipient(db, event.payload)
    return user_id in recipients


async def take(db, device, session_id):
    rows = await db.scalars(select(Inbox).where(Inbox.device_id == device.id, Inbox.session_id == session_id,
        Inbox.expires_at > now(), Inbox.state.in_(("pending", "offered", "sending_web", "web", "web_showing")),
        or_(Inbox.lease_until.is_(None), Inbox.lease_until <= now())).order_by(Inbox.id)
        .limit(12).with_for_update(skip_locked=True))
    items = []
    for row in rows:
        if not await still_allowed(db, row, device.user_id):
            row.state = "cancelled"
            continue
        row.state, row.lease_until = "offered", now() + timedelta(seconds=35)
        items.append({"id": row.id, **row.payload})
    await db.commit()
    return items


async def claim_web_display(db, token):
    from app.services.push_receipts import signature
    import hmac
    mac, _, value = token.partition(".")
    if not mac.isascii() or not hmac.compare_digest(signature(value), mac):
        return False
    expiry, sub, session, user, key = value.split(".", 4)
    if int(expiry) <= now().timestamp():
        return False
    row = await db.scalar(select(Inbox).where(Inbox.subscription_id == int(sub), Inbox.session_id == int(session),
        Inbox.event_key == key, Inbox.expires_at > now()).with_for_update())
    if not row or row.state not in ("web", "sending_web") or not await still_allowed(db, row, int(user)):
        return False
    from app.services.mobile_app_service import active_device_session, is_feature_enabled
    device = await db.get(MobileDevice, row.device_id)
    if (not device or device.revoked_at or device.user_id != int(user) or not await is_feature_enabled(db)
            or await active_device_session(db, device) != int(session)):
        return False
    row.state, row.lease_until = "web_showing", now() + timedelta(minutes=2)
    await db.commit()
    return True
