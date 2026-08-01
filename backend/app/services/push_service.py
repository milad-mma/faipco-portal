"""
سرویس Web Push: ذخیره اشتراک هر دستگاه و ارسال اعلان به کاربران هدف.

اگر VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY در .env تنظیم نشده باشند (هنوز
scripts/generate_vapid_keys.py اجرا نشده)، ارسال Push بی‌صدا نادیده گرفته
می‌شود — یعنی نبود این تنظیمات هرگز باعث خطا در ثبت/انتشار اطلاعیه نمی‌شود.
"""
import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.push_subscription import PushSubscription
from app.schemas.push import PushSubscriptionIn

logger = logging.getLogger("faipco.push")
settings = get_settings()


class PushService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_subscription(self, user_id: int, payload: PushSubscriptionIn) -> None:
        result = await self.db.execute(
            select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.user_id = user_id
            existing.p256dh = payload.keys.p256dh
            existing.auth = payload.keys.auth
        else:
            self.db.add(
                PushSubscription(
                    user_id=user_id,
                    endpoint=payload.endpoint,
                    p256dh=payload.keys.p256dh,
                    auth=payload.keys.auth,
                )
            )
        await self.db.commit()

    async def remove_subscription(self, endpoint: str) -> None:
        result = await self.db.execute(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
        sub = result.scalar_one_or_none()
        if sub is not None:
            await self.db.delete(sub)
            await self.db.commit()

    async def notify_users(self, user_ids: set[int], title: str, body: str, url: str = "/notices") -> None:
        if not settings.VAPID_PRIVATE_KEY or not user_ids:
            return  # Push هنوز پیکربندی نشده یا مخاطبی وجود ندارد

        result = await self.db.execute(select(PushSubscription).where(PushSubscription.user_id.in_(user_ids)))
        subscriptions = list(result.scalars().all())
        if not subscriptions:
            return

        payload = json.dumps({"title": title, "body": body, "url": url})
        stale_ids: list[int] = []

        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"},
                )
            except WebPushException as e:
                status_code = getattr(getattr(e, "response", None), "status_code", None)
                if status_code in (404, 410):
                    # اشتراک منقضی/لغوشده در مرورگر — از دیتابیس پاک می‌شود
                    stale_ids.append(sub.id)
                else:
                    logger.warning("ارسال Push به کاربر %s ناموفق بود: %s", sub.user_id, e)

        if stale_ids:
            await self.db.execute(delete(PushSubscription).where(PushSubscription.id.in_(stale_ids)))
            await self.db.commit()
