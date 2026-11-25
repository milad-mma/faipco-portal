"""Endpoint های Web Push: دریافت کلید عمومی VAPID، ثبت/لغو اشتراک دستگاه کاربر."""
from typing import Literal
from pydantic import BaseModel, Field
from app.services.push_receipts import record_receipt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.push import PushSubscriptionIn, UnsubscribeIn
from app.services.push_service import PushService
from app.models.user_session import UserSession
from sqlalchemy import select

router = APIRouter()
settings = get_settings()


@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """کلید عمومی VAPID را برای ساخت اشتراک در مرورگر برمی‌گرداند. دسترسی: عمومی (بدون احراز هویت)."""
    return {"public_key": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(
    payload: PushSubscriptionIn,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """اشتراک Push دستگاه جاری را برای کاربر لاگین‌شده ذخیره می‌کند. خروجی: 204 بدون بدنه."""
    sid = getattr(request.state, "session_sid", None)
    if ((payload.client_ready is not None or payload.session_marker is not None)
            and (not sid or payload.session_marker != sid)):
        raise HTTPException(status_code=409, detail="نشست هنگام ثبت اعلان تغییر کرده است")
    session = (await db.execute(
        select(UserSession).where(UserSession.sid == sid, UserSession.user_id == current_user.id,
                                  UserSession.revoked_at.is_(None))
    )).scalar_one_or_none() if sid else None
    if session is None:
        raise HTTPException(status_code=401, detail="برای فعال‌سازی اعلان دوباره وارد حساب شوید")
    service = PushService(db)
    if payload.client_ready is True:
        waiting = await service.confirm_subscription_ready(current_user.id, payload, session_id=session.id)
        if waiting is None:
            raise HTTPException(status_code=409, detail="اشتراک اعلان تغییر کرده است؛ دوباره تلاش کنید")
        job_ids, oa_keys, changed = waiting
        if changed:
            from app.services.push_dispatch import drain_ready_jobs
            # Fast path only. Durable records and their due times were committed
            # already; a worker exit here never loses an event.
            background_tasks.add_task(drain_ready_jobs, current_user.id, job_ids, oa_keys)
    else:
        await service.save_subscription(current_user.id, payload, session_id=session.id)


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    payload: UnsubscribeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """اشتراک Push خودِ کاربر با endpoint داده‌شده را حذف می‌کند (اشتراک دیگران دست نمی‌خورد). خروجی: 204."""
    await PushService(db).remove_subscription(payload.endpoint, current_user.id)

class ClientReceipt(BaseModel):
    token: str = Field(min_length=70, max_length=512)
    action: Literal["received", "opened"]


@router.post("/receipt", status_code=204)
async def confirm_receipt(payload: ClientReceipt, db: AsyncSession = Depends(get_db)):
    if not await record_receipt(db, payload.token, payload.action == "opened"):
        raise HTTPException(400, "رسید نامعتبر یا منقضی است")
