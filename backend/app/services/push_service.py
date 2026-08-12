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

    async def notify_users(
        self,
        user_ids: set[int],
        title: str,
        body: str,
        url: str = "/notices",
        priority: str = "normal",
        notice_type: str = "normal",
    ) -> None:
        if not settings.VAPID_PRIVATE_KEY or not user_ids:
            return  # Push هنوز پیکربندی نشده یا مخاطبی وجود ندارد

        result = await self.db.execute(select(PushSubscription).where(PushSubscription.user_id.in_(user_ids)))
        subscriptions = list(result.scalars().all())
        if not subscriptions:
            return

        # نام و نام‌خانوادگی هرکدام از مخاطبان (برای شخصی‌سازی متن اعلان) —
        # کاربران مدیریتی محض (بدون employee_id، مثل admin) در این نگاشت
        # نیستند و همان متن عمومی اطلاعیه را بدون خطاب شخصی می‌گیرند.
        from app.models.employee import Employee
        from app.models.user import User

        name_result = await self.db.execute(
            select(User.id, Employee.first_name, Employee.last_name)
            .join(Employee, Employee.id == User.employee_id)
            .where(User.id.in_(user_ids))
        )
        name_by_user_id = {row[0]: f"{row[1]} {row[2]}" for row in name_result.all()}

        # اطلاعیه‌های با اولویت بالا/فوری هم در FCM با Urgency=high سریع‌تر و
        # مطمئن‌تر تحویل داده می‌شوند (حتی وقتی گوشی در حالت Doze/کم‌مصرف است)،
        # هم در Service Worker با ویبره قوی‌تر و requireInteraction نمایش داده
        # می‌شوند — تا واقعاً دیده شوند، نه این‌که بی‌صدا از دست بروند.
        is_urgent = priority in ("high", "urgent")

        sent_count = 0
        failed_count = 0
        stale_ids: list[int] = []

        for sub in subscriptions:
            recipient_name = name_by_user_id.get(sub.user_id)
            personalized_body = f"{recipient_name} عزیز،\n{body}" if recipient_name else body
            payload = json.dumps(
                {
                    "title": title,
                    "body": personalized_body,
                    "url": url,
                    "priority": priority,
                    "notice_type": notice_type,
                }
            )
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"},
                    # اگر دستگاه گیرنده لحظه ارسال آفلاین باشد، تا ۲۴ ساعت روی
                    # سرور Push نگه داشته می‌شود و به‌محض آنلاین‌شدن تحویل داده می‌شود
                    ttl=60 * 60 * 24,
                    headers={"Urgency": "high" if is_urgent else "normal"},
                )
                sent_count += 1
            except WebPushException as e:
                status_code = getattr(getattr(e, "response", None), "status_code", None)
                if status_code in (404, 410):
                    # اشتراک منقضی/لغوشده در مرورگر — از دیتابیس پاک می‌شود
                    stale_ids.append(sub.id)
                else:
                    failed_count += 1
                    logger.warning(
                        "ارسال Push به کاربر %s ناموفق بود (status=%s): %s", sub.user_id, status_code, e
                    )

        if stale_ids:
            await self.db.execute(delete(PushSubscription).where(PushSubscription.id.in_(stale_ids)))
            await self.db.commit()

        # این خط عمداً همیشه (حتی موفقیت کامل) لاگ می‌شود — قبلاً هیچ ردی از
        # نتیجه ارسال Push در لاگ نبود و اگر چیزی شکست می‌خورد کاملاً بی‌صدا
        # گم می‌شد؛ حالا هر انتشار اطلاعیه یک خط قابل‌جستجو در لاگ دارد.
        logger.info(
            "ارسال Push اطلاعیه به %s مخاطب هدف: %s موفق، %s ناموفق، %s اشتراک منقضی حذف شد",
            len(user_ids),
            sent_count,
            failed_count,
            len(stale_ids),
        )
