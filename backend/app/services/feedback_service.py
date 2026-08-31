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

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.profanity_filter import contains_prohibited_phrase
from app.core.site_access import get_sites_with_permission
from app.models.employee import Employee
from app.models.feedback import FeedbackMessage, ProhibitedPhrase
from app.models.site import Site
from app.models.user import User
from app.schemas.feedback import FeedbackMessageOut

FEEDBACK_RATE_LIMIT_SECONDS = 60


class FeedbackAccessDenied(Exception):
    pass


class FeedbackRateLimitExceeded(Exception):
    pass


class FeedbackService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_prohibited_phrases(self) -> list[str]:
        result = await self.db.execute(select(ProhibitedPhrase.phrase))
        return [p for (p,) in result.all()]

    async def _check_rate_limit(self, sender_id: int) -> None:
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

    async def submit_feedback(self, sender: User, title: str, message: str, is_anonymous: bool) -> FeedbackMessage:
        await self._check_rate_limit(sender.id)

        prohibited_phrases = await self._get_prohibited_phrases()
        # هم عنوان هم متن پیام بررسی می‌شوند - چون عنوان هم بخشی از محتوای
        # قابل‌مشاهده پیام است، نه فقط یک برچسب داخلی.
        contains_profanity = contains_prohibited_phrase(f"{title} {message}", prohibited_phrases)

        feedback = FeedbackMessage(
            sender_id=sender.id,
            title=title.strip(),
            message=message.strip(),
            is_anonymous_requested=is_anonymous,
            contains_profanity=contains_profanity,
        )
        self.db.add(feedback)
        await self.db.commit()
        await self.db.refresh(feedback)
        return feedback

    async def _get_accessible_scope(self, current_user: User) -> tuple[set[int] | None, bool]:
        """
        برمی‌گرداند: (site_ids قابل‌دسترسی یا None برای سراسری/نامحدود، آیا اصلاً دسترسی دارد).
        هر دو مجوز feedback.view و feedback.view_all چک می‌شوند و ترکیب می‌شوند -
        اگر هرکدام به‌صورت سراسری اختصاص یافته باشد، دسترسی نامحدود است.
        """
        if current_user.is_superuser:
            return None, True

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
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[FeedbackMessageOut]:
        accessible_site_ids, has_access = await self._get_accessible_scope(current_user)
        if not has_access:
            raise FeedbackAccessDenied("اجازه مشاهده انتقادات و پیشنهادات را ندارید")

        query = (
            select(FeedbackMessage, User, Employee, Site.id, Site.name)
            .join(User, User.id == FeedbackMessage.sender_id)
            .outerjoin(Employee, Employee.id == User.employee_id)
            .outerjoin(Site, Site.id == Employee.site_id)
            .order_by(desc(FeedbackMessage.created_at))
        )

        conditions = []
        if accessible_site_ids is not None:
            conditions.append(Employee.site_id.in_(accessible_site_ids))
        if sender_id is not None:
            conditions.append(FeedbackMessage.sender_id == sender_id)
        if site_id is not None:
            conditions.append(Employee.site_id == site_id)
        if date_from is not None:
            conditions.append(FeedbackMessage.created_at >= date_from)
        if date_to is not None:
            conditions.append(FeedbackMessage.created_at <= date_to)
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.db.execute(query)
        rows = result.all()

        # فقط Admin واقعی همیشه فرستنده را می‌بیند - دارنده مجوز
        # (حتی اگر مجوز سراسری feedback.view_all داشته باشد)، طبق درخواست
        # صریح، باید به همان قانون محرمانگی/ناشناس‌بودن پایبند بماند.
        always_reveal_sender = current_user.is_superuser

        out = []
        for feedback, sender, employee, site_id_val, site_name in rows:
            reveal_sender = always_reveal_sender or not feedback.is_anonymous_requested or feedback.contains_profanity
            sender_name = f"{employee.first_name} {employee.last_name}" if employee else (sender.username or "—")
            out.append(
                FeedbackMessageOut(
                    id=feedback.id,
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
        return out

    async def delete_feedback(self, feedback_id: int) -> bool:
        """حذف یک پیام - فقط از طریق پنل ادمین (Endpoint این را به Admin واقعی محدود می‌کند، نه اینجا)."""
        feedback = await self.db.get(FeedbackMessage, feedback_id)
        if feedback is None:
            return False
        await self.db.delete(feedback)
        await self.db.commit()
        return True

    # ---------- مدیریت فهرست کلمات/عبارات نامناسب (فقط Admin واقعی) ----------

    async def list_prohibited_phrases(self) -> list[ProhibitedPhrase]:
        result = await self.db.execute(select(ProhibitedPhrase).order_by(ProhibitedPhrase.phrase))
        return list(result.scalars().all())

    async def add_prohibited_phrase(self, phrase: str) -> ProhibitedPhrase:
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
        entry = await self.db.get(ProhibitedPhrase, phrase_id)
        if entry is None:
            return False
        await self.db.delete(entry)
        await self.db.commit()
        return True
