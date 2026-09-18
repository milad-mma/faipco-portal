"""
سرویس «ری‌اکشن تبریک تولد» — ثبت/تغییر/حذف ری‌اکشن و خواندن فهرست
کسانی که تبریک گفته‌اند.

⚠️ قواعد اعتبارسنجی (طبق تصمیمات صریح کاربر):
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
from app.models.birthday_reaction import BirthdayReaction, BirthdayReactionEmoji
from app.models.employee import Department, Employee
from app.models.user import User
from app.services.push_service import PushService

logger = logging.getLogger(__name__)

# ⚠️ متن نمایشی هر ایموجی - در UI به کاربر نشان داده می‌شود تا انتخابش
# آگاهانه باشد. اینجا نگه داشته می‌شود (نه فقط در فرانت‌اند) تا اگر
# جای دیگری هم لازم شد، یک منبع واحد داشته باشد.
EMOJI_CHARS = {
    BirthdayReactionEmoji.party: "🎉",
    BirthdayReactionEmoji.cake: "🎂",
    BirthdayReactionEmoji.white_heart: "🤍",
    BirthdayReactionEmoji.blue_heart: "💙",
}


class BirthdayReactionError(Exception):
    pass


class BirthdayReactionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _assert_is_birthday_today(self, employee_id: int) -> Employee:
        """⚠️ ری‌اکشن فقط در همان روز تولد مجاز است - نه قبل، نه بعد."""
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
        ثبت یا تغییر ری‌اکشن. اگر همان ایموجی قبلاً ثبت شده باشد، برداشته
        می‌شود (Toggle) - تا اگر کسی اشتباهی زد بتواند پس بگیرد.
        """
        employee = await self._assert_is_birthday_today(birthday_employee_id)

        # ⚠️ طبق تصمیم صریح کاربر: خودِ متولد نمی‌تواند به تولد خودش
        # ری‌اکشن بزند.
        if current_user.employee_id == birthday_employee_id:
            raise BirthdayReactionError("نمی‌توانید به تولد خودتان واکنش ثبت کنید")

        jalali_year, _, _ = get_current_jalali_date()
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
        elif existing.emoji == emoji:
            await self.db.delete(existing)
            await self.db.commit()
            return {"emoji": None}
        else:
            existing.emoji = emoji
            await self.db.commit()

        # ⚠️ طبق تصمیم صریح کاربر: فقط **اولین** تبریک اعلان فوری دارد -
        # وگرنه اگر ۵۰ نفر تبریک بگویند، متولد ۵۰ اعلان می‌گرفت. خلاصه
        # روزانه را Job زمان‌بندی‌شده ۴ ساعت مانده به پایان روز می‌فرستد.
        if is_first_ever:
            await self._notify_first_reaction(employee)

        return {"emoji": emoji.value}

    async def _notify_first_reaction(self, employee: Employee) -> None:
        try:
            result = await self.db.execute(select(User).where(User.employee_id == employee.id))
            target_user = result.scalar_one_or_none()
            if target_user is None:
                return
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
        ⚠️ برای کارت داشبورد - یک درخواست برای همه متولدین امروز (نه یک
        Query به‌ازای هر نفر). خروجی به‌ازای هر employee_id:
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
                # ⚠️ خودِ عکس کشیده نمی‌شود (حجیم است) - فقط اینکه وجود
                # دارد یا نه، تا فرانت‌اند بداند درخواست تصویر بزند یا نه.
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
            entry["counts"][key] = entry["counts"].get(key, 0) + 1
            # کاربران مدیریتی محض (بدون Employee) نام ندارند - کنار گذاشته
            # نمی‌شوند ولی با نام جایگزین نمایش داده می‌شوند.
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
        ⚠️ طبق تصمیم صریح کاربر: ۴ ساعت مانده به پایان روز تولد، یک اعلان
        خلاصه به هر متولد می‌رود («N نفر تبریک گفتند») - به‌جای اینکه
        به‌ازای هر تبریک یک اعلان جداگانه برود.

        فقط متولدینی که واقعاً حداقل یک تبریک گرفته‌اند اعلان می‌گیرند -
        وگرنه پیام «۰ نفر تبریک گفتند» فرستادن، از نفرستادن بدتر است.
        """
        jalali_year, month, day = get_current_jalali_date()
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
                continue
            # ⚠️ طبق درخواست صریح کاربر: فعل با تعداد مطابقت کند -
            # «۱ نفر ... تبریک گفت» در برابر «۳ نفر ... تبریک گفتند».
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
