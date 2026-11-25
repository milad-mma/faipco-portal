"""Signed delivery-specific capabilities. A retry preserves the first server confirmation."""
import hashlib
import hmac
from time import time

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.models.office_automation import OaNotificationOutbox
from app.models.push_dispatch import OfficePushReceipt, PushDispatchDelivery, PushDispatchJob


def signature(value):
    return hmac.new(get_settings().SECRET_KEY.encode(), b"push-receipt-v1:" + value.encode(),
                    hashlib.sha256).hexdigest()


def issue_receipt(key, sub):
    expires = int(time()) + 60 * 86400
    value = f"{expires}.{sub.id}.{sub.session_id}.{sub.user_id}.{key}"
    return f"{signature(value)}.{value}"


async def record_receipt(db, token, opened):
    mac, _, value = token.partition(".")
    if not mac.isascii() or not hmac.compare_digest(signature(value), mac):
        return False
    expires, sub, session, user, key = value.split(".", 4)
    if int(expires) < time():
        return False
    sid, session_id, uid = int(sub), int(session), int(user)
    if key.startswith("dispatch:"):
        row = PushDispatchDelivery
        fields = {"received_at": func.coalesce(row.received_at, func.now())}
        if opened:
            fields["opened_at"] = func.coalesce(row.opened_at, func.now())
        stmt = update(row).where(row.job_id == select(PushDispatchJob.id).where(
            PushDispatchJob.key == key).scalar_subquery(), row.subscription_id == sid,
            row.session_id == session_id, row.user_id == uid).values(**fields)
    else:
        event_id = await db.scalar(select(OaNotificationOutbox.id).where(OaNotificationOutbox.key == key))
        if event_id is None:
            return False
        row = OfficePushReceipt
        stmt = insert(row).values(event_id=event_id, subscription_id=sid, session_id=session_id,
                                  user_id=uid, received_at=func.now(), opened_at=func.now() if opened else None)
        stmt = (stmt.on_conflict_do_update(index_elements=[row.event_id, row.subscription_id, row.session_id],
                set_={"opened_at": func.coalesce(row.opened_at, func.now())}) if opened
                else stmt.on_conflict_do_nothing())
    await db.execute(stmt)
    await db.commit()
    return True
