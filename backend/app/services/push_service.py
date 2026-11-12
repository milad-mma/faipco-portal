"""
سرویس Web Push: ذخیره اشتراک هر دستگاه و ارسال اعلان به کاربران هدف.

اگر VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY در .env تنظیم نشده باشند (هنوز
scripts/generate_vapid_keys.py اجرا نشده)، ارسال Push بی‌صدا نادیده گرفته
می‌شود — یعنی نبود این تنظیمات هرگز باعث خطا در ثبت/انتشار اطلاعیه نمی‌شود.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import notification_templates
from app.core.config import get_settings
from app.models.push_subscription import PushSubscription
from app.models.user_session import UserSession
from app.models.user import User
from app.models.employee import Employee
from app.schemas.push import PushSubscriptionIn

logger = logging.getLogger("faipco.push")
settings = get_settings()


class PushService:
    """ثبت/حذف اشتراک‌های Web Push و ارسال اعلان به مجموعه‌ای از کاربران."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_subscription(self, user_id: int, payload: PushSubscriptionIn, *, session_id: int) -> None:
        """Bind exactly one browser endpoint to its verified authenticated session.

        PostgreSQL UPSERT avoids duplicate unique-endpoint inserts when login and
        layout both register in parallel. An endpoint moved to another account
        must never remain associated with the previous user's session.
        """
        stmt = pg_insert(PushSubscription).values(
            user_id=user_id, session_id=session_id, endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh, auth=payload.keys.auth,
        )
        await self.db.execute(stmt.on_conflict_do_update(
            index_elements=[PushSubscription.endpoint],
            set_={"user_id": user_id, "session_id": session_id,
                  "p256dh": payload.keys.p256dh, "auth": payload.keys.auth},
        ))
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
        return_stats: bool = False,
        subscription_ids: set[int] | None = None,
        notification_key: str | None = None,
    ) -> dict | None:
        """
        به همه دستگاه‌های کاربران user_ids یک اعلان Push می‌فرستد (موازی، حداکثر ۲۰ هم‌زمان).
        ورودی: آدرس مقصد کلیک، اولویت، نوع اطلاعیه و متن اختیاری body؛ اگر body داده نشود،
        متن پیش‌فرض «اطلاعیه جدید» استفاده می‌شود. اشتراک‌های منقضی (404/410) حذف می‌شوند.
        """
        if not user_ids:
            return {"attempted": 0, "sent": 0, "failed": 0, "stale": 0, "results": []} if return_stats else None
        if not settings.VAPID_PRIVATE_KEY:
            return {"attempted": 0, "sent": 0, "failed": 0, "stale": 0,
                    "configured": False, "results": []} if return_stats else None

        # No legacy/unbound or revoked/expired sessions may receive any Push.
        # The same rule applies to notices, payroll and OA, not just OA.
        expires_before = datetime.now(timezone.utc) - timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        stmt = (
            select(PushSubscription, UserSession.sid)
            .join(UserSession, PushSubscription.session_id == UserSession.id)
            .join(User, PushSubscription.user_id == User.id)
            .outerjoin(Employee, User.employee_id == Employee.id)
            .where(
                PushSubscription.user_id.in_(user_ids),
                UserSession.user_id == PushSubscription.user_id,
                UserSession.revoked_at.is_(None),
                UserSession.last_seen_at >= expires_before,
                User.is_active.is_(True),
                or_(User.employee_id.is_(None),
                    (Employee.is_active.is_(True) & Employee.is_enabled.is_(True))),
            )
        )
        if subscription_ids is not None:
            stmt = stmt.where(PushSubscription.id.in_(subscription_ids))
        subscription_rows = (await self.db.execute(stmt)).all()
        subscriptions = [row[0] for row in subscription_rows]
        marker_by_subscription = {row[0].id: row[1] for row in subscription_rows}
        if not subscriptions:
            return {"attempted": 0, "sent": 0, "failed": 0, "stale": 0, "results": []} if return_stats else None

        # نام و نام‌خانوادگی هرکدام از مخاطبان (برای شخصی‌سازی متن اعلان) —
        # کاربران مدیریتی محض (بدون employee_id، مثل admin) در این نگاشت
        # نیستند و همان متن عمومی اطلاعیه را بدون خطاب شخصی می‌گیرند.
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
        # متن پیش‌فرض اعلان اطلاعیه (قابل‌ویرایش در «متن اعلان‌ها»ی اطلاعیه‌ها؛ جدا برای فیش حقوقی/کارکرد)
        default_body = None
        if not body:
            key = {"payroll": "notices.payroll", "attendance_card": "notices.attendance_card"}.get(
                notice_type, "notices.new"
            )
            default_body = await notification_templates.render(self.db, None, key)
        sent_count = 0
        failed_count = 0
        stale_ids: list[int] = []  # شناسه اشتراک‌های منقضی برای حذف
        delivery_results: list[dict] = []  # subscription IDs only, never endpoints/keys
        semaphore = asyncio.Semaphore(20)

        async def send_one(sub: PushSubscription) -> None:
            """اعلان را برای یک اشتراک می‌سازد و ارسال می‌کند و شمارنده‌های نتیجه را به‌روز می‌کند."""
            nonlocal sent_count, failed_count
            recipient_name = name_by_user_id.get(sub.user_id)
            # عنوان/متن واقعی اطلاعیه در اعلان نمایش داده نمی‌شود؛ یک پیام
            # استاندارد و ثابت که فقط با نام مخاطب شخصی‌سازی می‌شود.
            notification_title = f"{recipient_name} عزیز،" if recipient_name else "پرتال سازمانی"
            notification_body = body or default_body
            payload = json.dumps(
                {
                    "title": notification_title,
                    "body": notification_body,
                    "url": url,
                    "priority": priority,
                    "notice_type": notice_type,
                    # Not a credential: device-session correlation so a delayed
                    # Push from a previous login cannot appear after account switch.
                    "session_marker": marker_by_subscription[sub.id],
                    **({"notification_key": notification_key} if notification_key else {}),
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
                        timeout=15,  # سرور Push کند/در دسترس نیست → بقیه‌ی گیرندگان معطل نمانند
                    )
                    sent_count += 1
                    delivery_results.append({"id": sub.id, "status": "sent"})
                except WebPushException as e:
                    status_code = getattr(getattr(e, "response", None), "status_code", None)
                    if status_code in (404, 410):
                        # اشتراک منقضی/لغوشده در مرورگر — از دیتابیس پاک می‌شود
                        stale_ids.append(sub.id)
                        delivery_results.append({"id": sub.id, "status": "stale"})
                    else:
                        failed_count += 1
                        delivery_results.append({"id": sub.id, "status": "failed"})
                        logger.warning(
                            "ارسال Push ناموفق (user_id=%s, subscription_id=%s, status=%s): %s",
                            sub.user_id, sub.id, status_code, type(e).__name__,
                        )
                except Exception as e:  # noqa: BLE001
                    # خطای شبکه (DNS، قطع اتصال، Timeout) برای یک دستگاه: فقط همان دستگاه ناموفق شمرده می‌شود.
                    # قبلاً این خطا کل ارسال را با «خطای سرور» متوقف می‌کرد و پاک‌سازی اشتراک‌های منقضی و لاگ خلاصه
                    # اجرا نمی‌شد. اشتراک حذف نمی‌شود چون مشکل از شبکه‌ی سرور است، نه از دستگاه.
                    failed_count += 1
                    delivery_results.append({"id": sub.id, "status": "failed"})
                    host = sub.endpoint.split("/")[2] if sub.endpoint.count("/") >= 2 else "?"
                    logger.warning(
                        "ارسال Push ناموفق (user_id=%s, subscription_id=%s, provider=%s): %s: %s",
                        sub.user_id,
                        sub.id,
                        host,
                        type(e).__name__,
                        str(e)[:200],
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
        if return_stats:
            return {"attempted": len(subscriptions), "sent": sent_count,
                    "failed": failed_count, "stale": len(stale_ids), "results": delivery_results}
