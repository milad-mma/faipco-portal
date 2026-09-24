"""Endpoint های Web Push: دریافت کلید عمومی VAPID، ثبت/لغو اشتراک دستگاه کاربر."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.push import PushSubscriptionIn, UnsubscribeIn
from app.services.push_service import PushService

router = APIRouter()
settings = get_settings()


@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """کلید عمومی VAPID را برای ساخت اشتراک در مرورگر برمی‌گرداند. دسترسی: عمومی (بدون احراز هویت)."""
    return {"public_key": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(
    payload: PushSubscriptionIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """اشتراک Push دستگاه جاری را برای کاربر لاگین‌شده ذخیره می‌کند. خروجی: 204 بدون بدنه."""
    await PushService(db).save_subscription(current_user.id, payload)


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    payload: UnsubscribeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """اشتراک Push خودِ کاربر با endpoint داده‌شده را حذف می‌کند (اشتراک دیگران دست نمی‌خورد). خروجی: 204."""
    await PushService(db).remove_subscription(payload.endpoint, current_user.id)
