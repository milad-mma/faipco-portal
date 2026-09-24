"""
سرویس «ری‌اکشن تبریک تولد» — ثبت/تغییر/حذف ری‌اکشن و خواندن فهرست
کسانی که تبریک گفته‌اند.

قواعد اعتبارسنجی:
    - فقط برای کسی که **امروز** روز تولدش است (نه دیروز، نه فردا).
    - خودِ متولد **نمی‌تواند** به تولد خودش ری‌اکشن بزند.
    - هر فرد فقط یک ری‌اکشن دارد؛ ری‌اکشن جدید جایگزین قبلی می‌شود و
      کلیک دوباره روی همان ایموجی، آن را برمی‌دارد.
"""
from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.persian_date import get_current_jalali_date
from app.core.site_access import get_accessible_site_ids
from app.models.birthday_reaction import BirthdayReaction, BirthdayReactionEmoji
from app.models.employee import Department, Employee
from app.models.user import User
from app.services.push_service import PushService

logger = logging.getLogger(__name__)

# نگاشت هر مقدار BirthdayReactionEmoji به کاراکتر ایموجی آن؛ منبع واحد
# برای هر جای Backend که به کاراکتر نمایشی نیاز دارد.
EMOJI_CHARS = {
    BirthdayReactionEmoji.party: "🎉",
    BirthdayReactionEmoji.cake: "🎂",
    BirthdayReactionEmoji.white_heart: "🤍",
    BirthdayReactionEmoji.blue_heart: "💙",
}


class BirthdayReactionError(Exception):
    """خطای اعتبارسنجی ری‌اکشن (پرسنل یافت نشد، امروز تولدش نیست، ری‌اکشن به خود)."""
    pass


class BirthdayReactionService:
    """ثبت/تغییر/حذف ری‌اکشن تبریک تولد، خواندن ری‌اکشن‌ها و ارسال اعلان‌های مربوط."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _assert_is_birthday_today(self, employee_id: int) -> Employee:
        """
        بررسی می‌کند پرسنل فعال است و امروز (شمسی) روز تولدش است؛ پرسنل را برمی‌گرداند.
        در غیر این صورت BirthdayReactionError می‌دهد (ری‌اکشن فقط در همان روز تولد مجاز است).
        """
        employee = await self.db.get(Employee, employee_id)
        if employee is None or not employee.is_active:
            raise BirthdayReactionError("پرسنل موردنظر یافت نشد")
        _, month, day = get_current_jalali_date()
        if employee.birth_month != month or employee.birth_day != day:
            raise BirthdayReactionError("امروز روز تولد این فرد نیست")
        return employee

    async def set_reaction(
        self, current_user: User, birthday_employee_id: int, emoji: BirthdayReactionEmoji
    ) -> dict:
        """
        ثبت یا تغییر ری‌اکشن کاربر جاری برای تولد یک پرسنل. اگر همان ایموجی از قبل
        ثبت شده باشد، برداشته می‌شود (Toggle). خروجی: {"emoji": مقدار جدید یا None}.
        """
        employee = await self._assert_is_birthday_today(birthday_employee_id)

        # خودِ متولد نمی‌تواند به تولد خودش ری‌اکشن بزند
        if current_user.employee_id == birthday_employee_id:
            raise BirthdayReactionError("نمی‌توانید به تولد خودتان واکنش ثبت کنید")

        # فقط به تولد پرسنل سایت‌هایی که کاربر به آن‌ها دسترسی دارد (همان محدودیت لیست تولد داشبورد)
        accessible_site_ids = await get_accessible_site_ids(self.db, current_user)
        if accessible_site_ids is not None and employee.site_id not in accessible_site_ids:
            raise BirthdayReactionError("امکان ثبت واکنش برای این فرد وجود ندارد")

        jalali_year, _, _ = get_current_jalali_date()
        # ری‌اکشن فعلی همین کاربر برای همین متولد در سال جاری
        result = await self.db.execute(
            select(BirthdayReaction).where(
                BirthdayReaction.reactor_user_id == current_user.id,
                BirthdayReaction.birthday_employee_id == birthday_employee_id,
                BirthdayReaction.jalali_year == jalali_year,
            )
        )
        existing = result.scalar_one_or_none()

        is_first_ever = False
        if existing is None:
            # آیا این اولین تبریک امروز برای این فرد است؟ (برای اعلان فوری)
            count_result = await self.db.execute(
                select(BirthdayReaction.id).where(
                    BirthdayReaction.birthday_employee_id == birthday_employee_id,
                    BirthdayReaction.jalali_year == jalali_year,
                )
            )
            is_first_ever = count_result.first() is None

            self.db.add(
                BirthdayReaction(
                    reactor_user_id=current_user.id,
                    birthday_employee_id=birthday_employee_id,
                    jalali_year=jalali_year,
                    emoji=emoji,
                )
            )
            await self.db.commit()
        # همان ایموجی دوباره انتخاب شده: ری‌اکشن برداشته می‌شود
        elif existing.emoji == emoji:
            await self.db.delete(existing)
            await self.db.commit()
            return {"emoji": None}
        # ایموجی متفاوت: جایگزین ری‌اکشن قبلی
        else:
            existing.emoji = emoji
            await self.db.commit()

        # فقط اولین تبریک روز اعلان فوری دارد تا متولد به‌ازای هر تبریک اعلان نگیرد؛
        # خلاصه روزانه را Job زمان‌بندی‌شده ۴ ساعت مانده به پایان روز می‌فرستد.
        if is_first_ever:
            await self._notify_first_reaction(employee)

        return {"emoji": emoji.value}

    async def _notify_first_reaction(self, employee: Employee) -> None:
        """به کاربرِ متولد اعلان Push «همکاران تبریک گفتند» می‌فرستد؛ خطاها فقط لاگ می‌شوند."""
        try:
            result = await self.db.execute(select(User).where(User.employee_id == employee.id))
            target_user = result.scalar_one_or_none()
            if target_user is None:
                return  # پرسنل حساب کاربری ندارد
            await PushService(self.db).notify_users(
                {target_user.id},
                url="/my-dashboard",
                priority="normal",
                body=(
                    "همکارانتان تولد شما را تبریک گفتند.\n"
                    "جهت مشاهده روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید."
                ),
            )
        except Exception:
            logger.exception("ارسال Push اولین تبریک تولد با خطا مواجه شد")

    async def get_reactions_for_employees(self, employee_ids: list[int]) -> dict[int, dict]:
        """
        ری‌اکشن‌های امسال برای مجموعه‌ای از متولدین (کارت داشبورد) با یک Query واحد.
        خروجی به‌ازای هر employee_id:
            {"counts": {emoji: n}, "reactors": [{name, department, emoji}]}
        """
        if not employee_ids:
            return {}
        jalali_year, _, _ = get_current_jalali_date()
        result = await self.db.execute(
            select(
                BirthdayReaction.birthday_employee_id,
                BirthdayReaction.emoji,
                BirthdayReaction.reactor_user_id,
                Employee.first_name,
                Employee.last_name,
                Department.name,
                Employee.id,
                # خودِ عکس (حجیم) خوانده نمی‌شود، فقط وجود یا نبود آن،
                # تا فرانت‌اند بداند درخواست تصویر بزند یا نه.
                Employee.photo_thumbnail.isnot(None),
            )
            .join(User, User.id == BirthdayReaction.reactor_user_id)
            .outerjoin(Employee, Employee.id == User.employee_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .where(
                BirthdayReaction.birthday_employee_id.in_(employee_ids),
                BirthdayReaction.jalali_year == jalali_year,
            )
            .order_by(BirthdayReaction.created_at)
        )

        # ساختار خروجی برای همه متولدین (حتی بدون ری‌اکشن) از قبل ساخته می‌شود
        out: dict[int, dict] = {eid: {"counts": {}, "reactors": []} for eid in employee_ids}
        for (
            emp_id,
            emoji,
            reactor_user_id,
            first_name,
            last_name,
            dept_name,
            reactor_employee_id,
            has_photo,
        ) in result.all():
            entry = out[emp_id]
            key = emoji.value
            entry["counts"][key] = entry["counts"].get(key, 0) + 1  # شمارش به‌ازای هر ایموجی
            # کاربران مدیریتی محض (بدون Employee) نام ندارند و با نام جایگزین
            # «کاربر سامانه» نمایش داده می‌شوند.
            entry["reactors"].append(
                {
                    "user_id": reactor_user_id,
                    "employee_id": reactor_employee_id,
                    "name": f"{first_name} {last_name}" if first_name else "کاربر سامانه",
                    "department": dept_name,
                    "emoji": key,
                    "has_photo": bool(has_photo),
                }
            )
        return out

    async def get_my_reactions(self, current_user: User, employee_ids: list[int]) -> dict[int, str]:
        """ری‌اکشن خودِ کاربر جاری برای هر متولد - تا UI بتواند آن را برجسته نشان دهد."""
        if not employee_ids:
            return {}
        jalali_year, _, _ = get_current_jalali_date()
        result = await self.db.execute(
            select(BirthdayReaction.birthday_employee_id, BirthdayReaction.emoji).where(
                BirthdayReaction.reactor_user_id == current_user.id,
                BirthdayReaction.birthday_employee_id.in_(employee_ids),
                BirthdayReaction.jalali_year == jalali_year,
            )
        )
        return {emp_id: emoji.value for emp_id, emoji in result.all()}

    async def send_end_of_day_summaries(self) -> dict:
        """
        به هر متولد امروز که حداقل یک تبریک گرفته، یک اعلان خلاصه («N نفر تبریک گفتند») می‌فرستد.
        توسط Job زمان‌بندی‌شده ۴ ساعت مانده به پایان روز اجرا می‌شود. خروجی: {"notified": تعداد}.
        """
        jalali_year, month, day = get_current_jalali_date()
        # متولدین فعال امروز که حساب کاربری دارند
        result = await self.db.execute(
            select(Employee.id, User.id)
            .join(User, User.employee_id == Employee.id)
            .where(
                Employee.is_active.is_(True),
                Employee.birth_month == month,
                Employee.birth_day == day,
            )
        )
        rows = result.all()
        if not rows:
            return {"notified": 0}

        counts = await self.get_reactions_for_employees([emp_id for emp_id, _ in rows])
        notified = 0
        for emp_id, user_id in rows:
            total = sum(counts.get(emp_id, {}).get("counts", {}).values())
            if total <= 0:
                continue  # بدون تبریک، اعلانی فرستاده نمی‌شود
            # مطابقت فعل با تعداد: «۱ نفر ... تبریک گفت» در برابر «۳ نفر ... تبریک گفتند»
            verb = "گفت" if total == 1 else "گفتند"
            try:
                await PushService(self.db).notify_users(
                    {user_id},
                    url="/my-dashboard",
                    priority="normal",
                    body=(
                        f"امروز {total} نفر از همکارانتان تولد شما را تبریک {verb}.\n"
                        "جهت مشاهده روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید."
                    ),
                )
                notified += 1
            except Exception:
                logger.exception("ارسال Push خلاصه تبریک تولد برای کاربر %s با خطا مواجه شد", user_id)
        return {"notified": notified}
