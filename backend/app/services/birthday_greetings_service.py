"""
سرویس «پیام‌های تبریک تولد» — پول متن‌های آماده که مدیر منابع انسانی (و
ادمین) مدیریت می‌کنند، ساعت ارسال روزانه، و خودِ منطق ارسال (Job زمان‌بندی‌شده
با APScheduler): هر روز در همان ساعت، برای هر پرسنلی که امروز (شمسی) تولدش
است، یک متن تصادفی از پول به‌عنوان یک اطلاعیه شخصی فرستاده می‌شود.

اگر پول خالی باشد، هیچ‌چیزی فرستاده نمی‌شود (رفتار پیش‌فرض امن).
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timezone

import jdatetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.birthday_message_template import BirthdayMessageTemplate
from app.models.employee import Employee
from app.models.notice import Notice, NoticePriority, NoticeStatus, NoticeTarget, NoticeTargetType, NoticeType
from app.models.user import User
from app.services.notice_service import send_publish_notifications
from app.services.system_settings_service import SystemSettingsService

logger = logging.getLogger("faipco.birthday_greetings")


class BirthdayGreetingsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- مدیریت پول متن‌ها ----------

    async def list_templates(self) -> list[BirthdayMessageTemplate]:
        result = await self.db.execute(
            select(BirthdayMessageTemplate).order_by(BirthdayMessageTemplate.created_at.desc())
        )
        return list(result.scalars().all())

    async def add_template(self, text: str) -> BirthdayMessageTemplate:
        text = text.strip()
        if not text:
            raise ValueError("متن پیام نمی‌تواند خالی باشد")
        template = BirthdayMessageTemplate(text=text, created_at=datetime.now(timezone.utc))
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def delete_template(self, template_id: int) -> bool:
        template = await self.db.get(BirthdayMessageTemplate, template_id)
        if template is None:
            return False
        await self.db.delete(template)
        await self.db.commit()
        return True

    # ---------- ساعت ارسال ----------

    async def get_send_time(self) -> tuple[int, int]:
        return await SystemSettingsService(self.db).get_birthday_send_time()

    async def set_send_time(self, hour: int, minute: int) -> tuple[int, int]:
        return await SystemSettingsService(self.db).set_birthday_send_time(hour, minute)

    async def get_enabled(self) -> bool:
        return await SystemSettingsService(self.db).get_birthday_greetings_enabled()

    async def set_enabled(self, enabled: bool) -> bool:
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

        templates_result = await self.db.execute(select(BirthdayMessageTemplate))
        templates = list(templates_result.scalars().all())
        if not templates:
            logger.info("پول پیام تبریک تولد خالی است — امروز چیزی فرستاده نشد.")
            return 0

        today_jalali = jdatetime.date.fromgregorian(date=datetime.now().date())
        employees_result = await self.db.execute(
            select(Employee).where(
                Employee.is_active.is_(True),
                Employee.birth_month == today_jalali.month,
                Employee.birth_day == today_jalali.day,
            )
        )
        birthday_employees = list(employees_result.scalars().all())
        if not birthday_employees:
            return 0

        sender_result = await self.db.execute(select(User).where(User.is_superuser.is_(True)).limit(1))
        sender = sender_result.scalar_one_or_none()
        if sender is None:
            logger.error("هیچ کاربر Admin ای برای فرستنده اطلاعیه تبریک تولد پیدا نشد — ارسال لغو شد.")
            return 0

        now = datetime.now(timezone.utc)
        sent_count = 0
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
            await self.db.flush()
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
        return sent_count
