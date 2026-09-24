"""
سرویس «پیام‌های تبریک تولد» — مجموعه (پول) متن‌های آماده که مدیر منابع انسانی (و
ادمین) مدیریت می‌کنند، ساعت ارسال روزانه، و خودِ منطق ارسال (Job زمان‌بندی‌شده
با APScheduler): هر روز در همان ساعت، برای هر پرسنلی که امروز (شمسی) تولدش
است، یک متن تصادفی از پول به‌عنوان یک اطلاعیه شخصی فرستاده می‌شود.

اگر پول خالی باشد، هیچ‌چیزی فرستاده نمی‌شود (رفتار پیش‌فرض امن).
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.persian_date import get_current_jalali_date
from app.models.birthday_message_template import BirthdayMessageTemplate
from app.models.employee import Employee
from app.models.notice import Notice, NoticePriority, NoticeStatus, NoticeTarget, NoticeTargetType, NoticeType
from app.models.user import User
from app.services.notice_service import send_publish_notifications
from app.services.system_settings_service import SystemSettingsService

logger = logging.getLogger("faipco.birthday_greetings")


class BirthdayGreetingsService:
    """مدیریت متن‌های تبریک، تنظیمات ارسال و ارسال روزانه اطلاعیه تبریک تولد."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- مدیریت پول متن‌ها ----------

    async def list_templates(self) -> list[BirthdayMessageTemplate]:
        """همه متن‌های تبریک را به ترتیب جدیدترین برمی‌گرداند."""
        result = await self.db.execute(
            select(BirthdayMessageTemplate).order_by(BirthdayMessageTemplate.created_at.desc())
        )
        return list(result.scalars().all())

    async def add_template(self, text: str) -> BirthdayMessageTemplate:
        """یک متن تبریک جدید (پس از strip) ذخیره و برمی‌گرداند؛ متن خالی ValueError می‌دهد."""
        text = text.strip()
        if not text:
            raise ValueError("متن پیام نمی‌تواند خالی باشد")
        template = BirthdayMessageTemplate(text=text, created_at=datetime.now(timezone.utc))
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def delete_template(self, template_id: int) -> bool:
        """متن تبریک را حذف می‌کند؛ اگر یافت نشود False برمی‌گرداند."""
        template = await self.db.get(BirthdayMessageTemplate, template_id)
        if template is None:
            return False
        await self.db.delete(template)
        await self.db.commit()
        return True

    # ---------- ساعت ارسال ----------

    async def get_send_time(self) -> tuple[int, int]:
        """ساعت و دقیقه ارسال روزانه را از تنظیمات سیستم برمی‌گرداند."""
        return await SystemSettingsService(self.db).get_birthday_send_time()

    async def set_send_time(self, hour: int, minute: int) -> tuple[int, int]:
        """ساعت و دقیقه ارسال روزانه را ذخیره می‌کند و مقدار ذخیره‌شده را برمی‌گرداند."""
        return await SystemSettingsService(self.db).set_birthday_send_time(hour, minute)

    async def get_enabled(self) -> bool:
        """فعال بودن ارسال خودکار تبریک تولد را برمی‌گرداند."""
        return await SystemSettingsService(self.db).get_birthday_greetings_enabled()

    async def set_enabled(self, enabled: bool) -> bool:
        """ارسال خودکار تبریک تولد را فعال/غیرفعال می‌کند."""
        return await SystemSettingsService(self.db).set_birthday_greetings_enabled(enabled)

    # ---------- ارسال روزانه ----------

    async def send_todays_birthday_greetings(self) -> int:
        """
        برای هر پرسنل فعالی که امروز (شمسی) تولدش است، یک متن تصادفی از پول
        به‌عنوان یک اطلاعیه شخصی می‌فرستد. تعداد پیام‌های واقعاً فرستاده‌شده
        را برمی‌گرداند (برای لاگ).
        """
        if not await self.get_enabled():
            logger.info("ارسال خودکار پیام تبریک تولد غیرفعال است — امروز چیزی فرستاده نشد.")
            return 0

        today_year, today_month, today_day = get_current_jalali_date()
        today_str = f"{today_year:04d}-{today_month:02d}-{today_day:02d}"

        # جلوگیری از ارسال تکراری: چون Job دارای misfire_grace_time است، ممکن است
        # در یک روز چند بار اجرا شود (مثلاً پس از Restart سرور)؛ تاریخ آخرین ارسال
        # ذخیره می‌شود تا هر پرسنل حداکثر یک‌بار در روز پیام تبریک بگیرد.
        already_sent_today = await SystemSettingsService(self.db).get_last_birthday_greetings_date()
        if already_sent_today == today_str:
            logger.info("پیام تبریک تولد امروز (%s) قبلاً ارسال شده — دوباره ارسال نمی‌شود.", today_str)
            return 0

        # بارگذاری همه متن‌های تبریک
        templates_result = await self.db.execute(select(BirthdayMessageTemplate))
        templates = list(templates_result.scalars().all())
        if not templates:
            logger.info("پول پیام تبریک تولد خالی است — امروز چیزی فرستاده نشد.")
            return 0

        # پرسنل فعالی که ماه و روز تولدشان برابر امروز (شمسی) است
        employees_result = await self.db.execute(
            select(Employee).where(
                Employee.is_active.is_(True),
                Employee.birth_month == today_month,
                Employee.birth_day == today_day,
            )
        )
        birthday_employees = list(employees_result.scalars().all())
        # اگر کسی تولد ندارد، امروز به‌عنوان «انجام‌شده» علامت می‌خورد
        if not birthday_employees:
            await SystemSettingsService(self.db).set_last_birthday_greetings_date(today_str)
            return 0

        # فرستنده اطلاعیه تبریک: اولین کاربر superuser
        sender_result = await self.db.execute(select(User).where(User.is_superuser.is_(True)).limit(1))
        sender = sender_result.scalar_one_or_none()
        if sender is None:
            logger.error("هیچ کاربر Admin ای برای فرستنده اطلاعیه تبریک تولد پیدا نشد — ارسال لغو شد.")
            return 0

        now = datetime.now(timezone.utc)
        sent_count = 0
        # برای هر متولد: ساخت اطلاعیه منتشرشده با یک متن تصادفی، هدف‌گیری فقط همان پرسنل، و ارسال Push
        for employee in birthday_employees:
            message_text = random.choice(templates).text
            notice = Notice(
                sender_id=sender.id,
                title="تولدت مبارک! 🎉",
                body=message_text,
                priority=NoticePriority.normal,
                status=NoticeStatus.published,
                notice_type=NoticeType.normal,
                publish_at=now,
            )
            self.db.add(notice)
            await self.db.flush()  # برای گرفتن notice.id
            self.db.add(
                NoticeTarget(notice_id=notice.id, target_type=NoticeTargetType.employee, target_id=employee.id)
            )
            await self.db.commit()
            sent_count += 1
            try:
                await send_publish_notifications(notice.id)
            except Exception:  # noqa: BLE001 - خطای Push یک نفر نباید بقیه را متوقف کند
                logger.exception("ارسال Push تبریک تولد برای پرسنل %s ناموفق بود", employee.id)

        logger.info("پیام تبریک تولد برای %s پرسنل فرستاده شد.", sent_count)
        await SystemSettingsService(self.db).set_last_birthday_greetings_date(today_str)
        return sent_count
