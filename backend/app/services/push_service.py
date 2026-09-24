"""
سرویس Web Push: ذخیره اشتراک هر دستگاه و ارسال اعلان به کاربران هدف.

اگر VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY در .env تنظیم نشده باشند (هنوز
scripts/generate_vapid_keys.py اجرا نشده)، ارسال Push بی‌صدا نادیده گرفته
می‌شود — یعنی نبود این تنظیمات هرگز باعث خطا در ثبت/انتشار اطلاعیه نمی‌شود.
"""
import asyncio
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
    """ثبت/حذف اشتراک‌های Web Push و ارسال اعلان به مجموعه‌ای از کاربران."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_subscription(self, user_id: int, payload: PushSubscriptionIn) -> None:
        """
        اشتراک یک دستگاه را برای کاربر ذخیره می‌کند. اگر همان endpoint از قبل ثبت شده باشد،
        مالک و کلیدهایش به‌روز می‌شود (مثلاً ورود کاربر دیگر روی همان مرورگر).
        """
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

    async def remove_subscription(self, endpoint: str, user_id: int | None = None) -> None:
        """اشتراک با endpoint داده‌شده را (در صورت وجود) حذف می‌کند؛ با user_id فقط اگر متعلق به همان کاربر باشد."""
        query = select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        if user_id is not None:
            query = query.where(PushSubscription.user_id == user_id)
        result = await self.db.execute(query)
        sub = result.scalar_one_or_none()
        if sub is not None:
            await self.db.delete(sub)
            await self.db.commit()

    async def notify_users(
        self,
        user_ids: set[int],
        url: str = "/notices",
        priority: str = "normal",
        notice_type: str = "normal",
        body: str | None = None,
    ) -> None:
        """
        به همه دستگاه‌های کاربران user_ids یک اعلان Push می‌فرستد (موازی، حداکثر ۲۰ هم‌زمان).
        ورودی: آدرس مقصد کلیک، اولویت، نوع اطلاعیه و متن اختیاری body؛ اگر body داده نشود،
        متن پیش‌فرض «اطلاعیه جدید» استفاده می‌شود. اشتراک‌های منقضی (404/410) حذف می‌شوند.
        """
        if not settings.VAPID_PRIVATE_KEY or not user_ids:
            return  # Push هنوز پیکربندی نشده یا مخاطبی وجود ندارد

        # همه اشتراک‌های ثبت‌شده برای کاربران هدف
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

        # صرف‌نظر از اولویت اطلاعیه، Urgency همیشه high فرستاده می‌شود تا FCM
        # حتی در حالت Doze/کم‌مصرف گوشی هم آن را فوری (بدون Batch) تحویل بدهد.

        # ارسال‌ها با asyncio.gather به‌صورت موازی انجام می‌شوند و یک Semaphore
        # تعداد ارسال هم‌زمان را به ۲۰ محدود می‌کند تا فشار روی سرویس Push/شبکه
        # کنترل شود؛ به این ترتیب ارسال به صدها گیرنده از Timeout درخواست HTTP عبور نمی‌کند.
        sent_count = 0
        failed_count = 0
        stale_ids: list[int] = []  # شناسه اشتراک‌های منقضی برای حذف
        semaphore = asyncio.Semaphore(20)

        async def send_one(sub: PushSubscription) -> None:
            """اعلان را برای یک اشتراک می‌سازد و ارسال می‌کند و شمارنده‌های نتیجه را به‌روز می‌کند."""
            nonlocal sent_count, failed_count
            recipient_name = name_by_user_id.get(sub.user_id)
            # عنوان/متن واقعی اطلاعیه در اعلان نمایش داده نمی‌شود؛ یک پیام
            # استاندارد و ثابت که فقط با نام مخاطب شخصی‌سازی می‌شود.
            notification_title = f"{recipient_name} عزیز،" if recipient_name else "پرتال سازمانی"
            notification_body = body or (
                "یک اطلاعیه جدید برای شما ارسال شده است.\n"
                "جهت مشاهده روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید."
            )
            payload = json.dumps(
                {
                    "title": notification_title,
                    "body": notification_body,
                    "url": url,
                    "priority": priority,
                    "notice_type": notice_type,
                }
            )
            async with semaphore:
                try:
                    # خودِ webpush() یک تابع مسدودکننده (Blocking) است — با
                    # asyncio.to_thread در یک Thread جدا اجرا می‌شود تا
                    # Event Loop اصلی را برای بقیه درخواست‌های هم‌زمان سرور
                    # مسدود نکند.
                    await asyncio.to_thread(
                        webpush,
                        subscription_info={
                            "endpoint": sub.endpoint,
                            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                        },
                        data=payload,
                        vapid_private_key=settings.VAPID_PRIVATE_KEY,
                        vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"},
                        # اگر دستگاه گیرنده لحظه ارسال آفلاین باشد، تا ۲۴ ساعت
                        # روی سرور Push نگه داشته می‌شود و به‌محض آنلاین‌شدن
                        # تحویل داده می‌شود
                        ttl=60 * 60 * 24,
                        headers={"Urgency": "high"},
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

        await asyncio.gather(*(send_one(sub) for sub in subscriptions))

        # حذف اشتراک‌های منقضی از دیتابیس
        if stale_ids:
            await self.db.execute(delete(PushSubscription).where(PushSubscription.id.in_(stale_ids)))
            await self.db.commit()

        # خلاصه نتیجه ارسال همیشه (حتی در موفقیت کامل) لاگ می‌شود تا هر
        # ارسال یک خط قابل‌جستجو در لاگ داشته باشد.
        logger.info(
            "ارسال Push اطلاعیه به %s مخاطب هدف: %s موفق، %s ناموفق، %s اشتراک منقضی حذف شد",
            len(user_ids),
            sent_count,
            failed_count,
            len(stale_ids),
        )
