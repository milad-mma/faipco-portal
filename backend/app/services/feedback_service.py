"""
سرویس «انتقادات و پیشنهادات» - منطق محرمانگی/ناشناس‌بودن اینجا پیاده‌سازی
می‌شود (نه در Endpoint یا Frontend):

    - Admin واقعی (is_superuser): همیشه فرستنده واقعی همه پیام‌ها را
      می‌بیند (به‌همراه این‌که کاربر خودش درخواست ناشناس‌ماندن داشته یا نه).
    - دارنده مجوز feedback.view (سایت‌محور) یا feedback.view_all (سراسری):
      اگر is_anonymous_requested=True و contains_profanity=False باشد،
      فرستنده نمایش داده نمی‌شود؛ در غیر این صورت (پیام حاوی الفاظ
      نامناسب بود)، فرستنده کاملاً قابل‌مشاهده می‌شود.

تشخیص الفاظ نامناسب کاملاً در Backend انجام می‌شود (app.core.profanity_filter)
- غیرقابل‌دورزدن با تغییر Frontend، چون Frontend فقط متن خام را می‌فرستد
و این سرویس، مستقل از هرچه Frontend فرستاده، خودش تشخیص می‌دهد.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.profanity_filter import contains_prohibited_phrase
from app.core.site_access import get_sites_with_permission
from app.models.employee import Employee
from app.models.feedback import FeedbackCategory, FeedbackMessage, ProhibitedPhrase
from app.models.site import Site
from app.models.user import Permission, Role, RolePermission, User, UserRole
from app.services.push_service import PushService
from app.schemas.feedback import FeedbackMessageOut

FEEDBACK_RATE_LIMIT_SECONDS = 60  # حداقل فاصله بین دو پیام از یک فرستنده (ثانیه)


logger = logging.getLogger(__name__)


class FeedbackAccessDenied(Exception):
    """کاربر مجوز مشاهده انتقادات و پیشنهادات را ندارد."""
    pass


class FeedbackRateLimitExceeded(Exception):
    """فرستنده در بازه محدودیت نرخ، پیام دیگری فرستاده است."""
    pass


class FeedbackService:
    """ثبت، فهرست (با اعمال محرمانگی)، حذف نرم بازخوردها و مدیریت عبارات نامناسب."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_prohibited_phrases(self) -> list[str]:
        """متن همه عبارات نامناسب ثبت‌شده را برمی‌گرداند."""
        result = await self.db.execute(select(ProhibitedPhrase.phrase))
        return [p for (p,) in result.all()]

    async def _check_rate_limit(self, sender_id: int) -> None:
        """اگر فرستنده در FEEDBACK_RATE_LIMIT_SECONDS اخیر پیامی داده باشد، FeedbackRateLimitExceeded می‌دهد."""
        window_start = datetime.now(timezone.utc) - timedelta(seconds=FEEDBACK_RATE_LIMIT_SECONDS)
        result = await self.db.execute(
            select(FeedbackMessage.id)
            .where(FeedbackMessage.sender_id == sender_id, FeedbackMessage.created_at >= window_start)
            .limit(1)
        )
        if result.first() is not None:
            raise FeedbackRateLimitExceeded(
                "برای جلوگیری از ارسال مکرر، حداکثر هر یک دقیقه یک پیام می‌توانید بفرستید — لطفاً کمی صبر کنید."
            )

    async def submit_feedback(
        self, sender: User, category: FeedbackCategory, title: str, message: str, is_anonymous: bool
    ) -> FeedbackMessage:
        """
        پیام جدید را پس از بررسی محدودیت نرخ و تشخیص الفاظ نامناسب ذخیره می‌کند،
        به بازبین‌ها اعلان می‌دهد و رکورد ذخیره‌شده را برمی‌گرداند.
        """
        await self._check_rate_limit(sender.id)

        prohibited_phrases = await self._get_prohibited_phrases()
        # هم عنوان هم متن پیام بررسی می‌شوند - چون عنوان هم بخشی از محتوای
        # قابل‌مشاهده پیام است، نه فقط یک برچسب داخلی.
        contains_profanity = contains_prohibited_phrase(f"{title} {message}", prohibited_phrases)

        feedback = FeedbackMessage(
            sender_id=sender.id,
            category=category,
            title=title.strip(),
            message=message.strip(),
            is_anonymous_requested=is_anonymous,
            contains_profanity=contains_profanity,
        )
        self.db.add(feedback)
        await self.db.commit()
        await self.db.refresh(feedback)

        # اطلاع‌رسانی به دارندگان مجوز مشاهده؛ خطای Push ثبت پیام را متوقف
        # نمی‌کند، چون پیام پیش از این مرحله commit شده است.
        await self._notify_reviewers_of_new_feedback(sender)

        return feedback

    async def _notify_reviewers_of_new_feedback(self, sender: User) -> None:
        """
        به دارندگان مجوز feedback.view یا feedback.view_all (به‌جز خودِ فرستنده) اعلان Push می‌فرستد؛
        فقط کسانی که این مجوز را سراسری یا برای سایت فرستنده دارند (feedback.view_all همیشه).
        متن اعلان هیچ اشاره‌ای به فرستنده، عنوان یا محتوا ندارد (حفظ محرمانگی روی صفحه قفل گوشی).
        خطاها فقط لاگ می‌شوند.
        """
        try:
            # کاربرانی که از طریق یکی از نقش‌هایشان مجوز مشاهده بازخورد دارند
            stmt = (
                select(User.id)
                .join(UserRole, UserRole.user_id == User.id)
                .join(Role, Role.id == UserRole.role_id)
                .join(RolePermission, RolePermission.role_id == Role.id)
                .join(Permission, Permission.id == RolePermission.permission_id)
                .where(Permission.code.in_(["feedback.view", "feedback.view_all"]))
                .distinct()
            )
            # سایت فرستنده: بازبین‌های سایتیِ سایت‌های دیگر اعلان نمی‌گیرند
            sender_site_id = None
            if sender.employee_id is not None:
                sender_employee = await self.db.get(Employee, sender.employee_id)
                sender_site_id = sender_employee.site_id if sender_employee else None
            site_condition = UserRole.site_id.is_(None) | (Permission.code == "feedback.view_all")
            if sender_site_id is not None:
                site_condition = site_condition | (UserRole.site_id == sender_site_id)
            stmt = stmt.where(site_condition)
            result = await self.db.execute(stmt)
            user_ids = {row[0] for row in result.all()} - {sender.id}  # حذف خودِ فرستنده
            if not user_ids:
                return
            await PushService(self.db).notify_users(
                user_ids,
                url="/feedback-report",
                priority="normal",
                body=(
                    "پیام جدیدی در انتقادات و پیشنهادات ثبت شده است.\n"
                    "جهت مشاهده روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید."
                ),
            )
        except Exception:
            logger.exception("ارسال Push برای پیام جدید انتقادات و پیشنهادات با خطا مواجه شد")

    async def _get_accessible_scope(self, current_user: User) -> tuple[set[int] | None, bool]:
        """
        برمی‌گرداند: (site_ids قابل‌دسترسی یا None برای سراسری/نامحدود، آیا اصلاً دسترسی دارد).
        هر دو مجوز feedback.view و feedback.view_all چک می‌شوند و ترکیب می‌شوند -
        اگر هرکدام به‌صورت سراسری اختصاص یافته باشد، دسترسی نامحدود است.
        """
        # superuser دسترسی سراسری دارد
        if current_user.is_superuser:
            return None, True

        # None از get_sites_with_permission یعنی مجوز به‌صورت سراسری اختصاص یافته
        view_all_sites = await get_sites_with_permission(self.db, current_user, "feedback.view_all")
        if view_all_sites is None:
            return None, True

        view_sites = await get_sites_with_permission(self.db, current_user, "feedback.view")
        if view_sites is None:
            return None, True

        combined = view_all_sites | view_sites
        return combined, bool(combined)

    async def get_feedback_list(
        self,
        current_user: User,
        *,
        sender_id: int | None = None,
        site_id: int | None = None,
        category: FeedbackCategory | None = None,
        is_anonymous: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict:
        """
        فهرست صفحه‌بندی‌شده پیام‌ها با فیلترهای اختیاری، محدود به سایت‌های قابل‌دسترسی کاربر.
        فرستنده طبق قواعد محرمانگی پنهان/آشکار می‌شود. خروجی: {items, total, page, page_size}.
        خطا: FeedbackAccessDenied اگر کاربر هیچ دسترسی نداشته باشد.
        """
        accessible_site_ids, has_access = await self._get_accessible_scope(current_user)
        if not has_access:
            raise FeedbackAccessDenied("اجازه مشاهده انتقادات و پیشنهادات را ندارید")

        # کوئری اصلی: پیام + فرستنده + پرسنل و سایت فرستنده، جدیدترین اول
        query = (
            select(FeedbackMessage, User, Employee, Site.id, Site.name)
            .join(User, User.id == FeedbackMessage.sender_id)
            .outerjoin(Employee, Employee.id == User.employee_id)
            .outerjoin(Site, Site.id == Employee.site_id)
            .order_by(desc(FeedbackMessage.created_at))
        )

        # شرط‌های فیلتر؛ پیام‌های حذف‌شده (حذف نرم) هرگز در فهرست نمی‌آیند
        conditions = [FeedbackMessage.is_deleted.is_(False)]
        if accessible_site_ids is not None:
            conditions.append(Employee.site_id.in_(accessible_site_ids))
        if sender_id is not None:
            conditions.append(FeedbackMessage.sender_id == sender_id)
        if site_id is not None:
            conditions.append(Employee.site_id == site_id)
        if category is not None:
            conditions.append(FeedbackMessage.category == category)
        if is_anonymous is not None:
            conditions.append(FeedbackMessage.is_anonymous_requested == is_anonymous)
        if date_from is not None:
            conditions.append(FeedbackMessage.created_at >= date_from)
        if date_to is not None:
            conditions.append(FeedbackMessage.created_at <= date_to)
        query = query.where(and_(*conditions))

        # شمارش کل نتایج با همان شرط‌ها (برای صفحه‌بندی)
        count_query = (
            select(func.count())
            .select_from(FeedbackMessage)
            .join(User, User.id == FeedbackMessage.sender_id)
            .outerjoin(Employee, Employee.id == User.employee_id)
            .where(and_(*conditions))
        )
        total = (await self.db.execute(count_query)).scalar_one()

        # محدودسازی شماره و اندازه صفحه به بازه معتبر
        safe_page = max(1, page)
        safe_page_size = max(1, min(page_size, 200))
        result = await self.db.execute(query.offset((safe_page - 1) * safe_page_size).limit(safe_page_size))
        rows = result.all()

        # فقط Admin واقعی همیشه فرستنده را می‌بیند؛ دارنده مجوز (حتی مجوز
        # سراسری feedback.view_all) تابع قانون محرمانگی/ناشناس‌بودن است.
        always_reveal_sender = current_user.is_superuser

        out = []
        # ساخت خروجی؛ فرستنده فقط وقتی آشکار است که: بیننده superuser باشد، یا ناشناس درخواست نشده، یا پیام حاوی الفاظ نامناسب باشد
        for feedback, sender, employee, site_id_val, site_name in rows:
            reveal_sender = always_reveal_sender or not feedback.is_anonymous_requested or feedback.contains_profanity
            sender_name = f"{employee.first_name} {employee.last_name}" if employee else (sender.username or "—")
            out.append(
                FeedbackMessageOut(
                    id=feedback.id,
                    category=feedback.category,
                    title=feedback.title,
                    message=feedback.message,
                    is_anonymous_requested=feedback.is_anonymous_requested,
                    contains_profanity=feedback.contains_profanity,
                    created_at=feedback.created_at,
                    sender_id=sender.id if reveal_sender else None,
                    sender_name=sender_name if reveal_sender else None,
                    site_id=site_id_val if reveal_sender else None,
                    site_name=site_name if reveal_sender else None,
                )
            )
        return {"items": out, "total": total, "page": safe_page, "page_size": safe_page_size}

    async def delete_feedback(self, feedback_id: int, deleted_by_user_id: int | None = None) -> bool:
        """
        حذف نرم یک پیام: رکورد باقی می‌ماند و فقط is_deleted، زمان و کاربر حذف‌کننده ثبت می‌شود.
        خروجی: True در صورت موفقیت، False اگر پیام یافت نشود یا از قبل حذف شده باشد.
        """
        feedback = await self.db.get(FeedbackMessage, feedback_id)
        if feedback is None or feedback.is_deleted:
            return False
        feedback.is_deleted = True
        feedback.deleted_at = datetime.now(timezone.utc)
        feedback.deleted_by_user_id = deleted_by_user_id
        await self.db.commit()
        return True

    # ---------- مدیریت فهرست کلمات/عبارات نامناسب (فقط Admin واقعی) ----------

    async def list_prohibited_phrases(self) -> list[ProhibitedPhrase]:
        """همه عبارات نامناسب را به ترتیب الفبایی برمی‌گرداند."""
        result = await self.db.execute(select(ProhibitedPhrase).order_by(ProhibitedPhrase.phrase))
        return list(result.scalars().all())

    async def add_prohibited_phrase(self, phrase: str) -> ProhibitedPhrase:
        """عبارت جدید را ذخیره می‌کند؛ در خطای commit (مثلاً تکراری) rollback کرده و خطا را بالا می‌دهد."""
        entry = ProhibitedPhrase(phrase=phrase.strip())
        self.db.add(entry)
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        await self.db.refresh(entry)
        return entry

    async def delete_prohibited_phrase(self, phrase_id: int) -> bool:
        """عبارت را حذف می‌کند؛ اگر یافت نشود False برمی‌گرداند."""
        entry = await self.db.get(ProhibitedPhrase, phrase_id)
        if entry is None:
            return False
        await self.db.delete(entry)
        await self.db.commit()
        return True
