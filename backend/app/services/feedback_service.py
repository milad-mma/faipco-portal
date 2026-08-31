"""
سرویس «انتقادات و پیشنهادات» - منطق محرمانگی/ناشناس‌بودن اینجا پیاده‌سازی
می‌شود (نه در Endpoint یا Frontend):

    - Admin واقعی (is_superuser): همیشه فرستنده واقعی همه پیام‌ها را
      می‌بیند (به‌همراه این‌که کاربر خودش درخواست ناشناس‌ماندن داشته یا نه).
    - دارنده مجوز feedback.view (سایت‌محور) یا feedback.view_all (سراسری):
      اگر is_anonymous_requested=True و contains_profanity=False باشد،
      فرستنده نمایش داده نمی‌شود؛ در غیر این صورت (پیام حاوی الفاظ
      نامناسب بود)، فرستنده کاملاً قابل‌مشاهده می‌شود.
"""
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.site_access import get_sites_with_permission
from app.models.employee import Employee
from app.models.feedback import FeedbackMessage, ProhibitedPhrase
from app.models.site import Site
from app.models.user import User
from app.schemas.feedback import FeedbackMessageOut


class FeedbackAccessDenied(Exception):
    pass


class FeedbackService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_contains_prohibited_phrase(self, message: str) -> bool:
        result = await self.db.execute(select(ProhibitedPhrase.phrase))
        phrases = [p for (p,) in result.all()]
        lowered_message = message.lower()
        return any(phrase.strip() and phrase.lower() in lowered_message for phrase in phrases)

    async def submit_feedback(self, sender: User, message: str, is_anonymous: bool) -> FeedbackMessage:
        contains_profanity = await self.check_contains_prohibited_phrase(message)
        feedback = FeedbackMessage(
            sender_id=sender.id,
            message=message,
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

    async def get_feedback_list(self, current_user: User) -> list[FeedbackMessageOut]:
        accessible_site_ids, has_access = await self._get_accessible_scope(current_user)
        if not has_access:
            raise FeedbackAccessDenied("اجازه مشاهده انتقادات و پیشنهادات را ندارید")

        query = (
            select(FeedbackMessage, User, Employee, Site.name)
            .join(User, User.id == FeedbackMessage.sender_id)
            .outerjoin(Employee, Employee.id == User.employee_id)
            .outerjoin(Site, Site.id == Employee.site_id)
            .order_by(desc(FeedbackMessage.created_at))
        )
        if accessible_site_ids is not None:
            query = query.where(Employee.site_id.in_(accessible_site_ids))

        result = await self.db.execute(query)
        rows = result.all()

        # فقط Admin واقعی همیشه فرستنده را می‌بیند - دارنده مجوز
        # (حتی اگر مجوز سراسری feedback.view_all داشته باشد)، طبق درخواست
        # صریح، باید به همان قانون محرمانگی/ناشناس‌بودن پایبند بماند.
        always_reveal_sender = current_user.is_superuser

        out = []
        for feedback, sender, employee, site_name in rows:
            reveal_sender = always_reveal_sender or not feedback.is_anonymous_requested or feedback.contains_profanity
            sender_name = f"{employee.first_name} {employee.last_name}" if employee else (sender.username or "—")
            out.append(
                FeedbackMessageOut(
                    id=feedback.id,
                    message=feedback.message,
                    is_anonymous_requested=feedback.is_anonymous_requested,
                    contains_profanity=feedback.contains_profanity,
                    created_at=feedback.created_at,
                    sender_id=sender.id if reveal_sender else None,
                    sender_name=sender_name if reveal_sender else None,
                    site_name=site_name if reveal_sender else None,
                )
            )
        return out

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
            # ⚠️ محتمل‌ترین علت، تکراری‌بودن phrase (Unique Constraint) است؛
            # بدون rollback صریح، Session برای عملیات بعدی همان درخواست خراب می‌ماند.
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
