"""Endpoint های Web Push: دریافت کلید عمومی VAPID، ثبت/لغو اشتراک دستگاه کاربر."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """اشتراک Push دستگاه جاری را برای کاربر لاگین‌شده ذخیره می‌کند. خروجی: 204 بدون بدنه."""
    sid = getattr(request.state, "session_sid", None)
    session = (await db.execute(
        select(UserSession).where(UserSession.sid == sid, UserSession.user_id == current_user.id,
                                  UserSession.revoked_at.is_(None))
    )).scalar_one_or_none() if sid else None
    if session is None:
        raise HTTPException(status_code=401, detail="برای فعال‌سازی اعلان دوباره وارد حساب شوید")
    await PushService(db).save_subscription(current_user.id, payload, session_id=session.id)


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    payload: UnsubscribeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """اشتراک Push خودِ کاربر با endpoint داده‌شده را حذف می‌کند (اشتراک دیگران دست نمی‌خورد). خروجی: 204."""
    await PushService(db).remove_subscription(payload.endpoint, current_user.id)
