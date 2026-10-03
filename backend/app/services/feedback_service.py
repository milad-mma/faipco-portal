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

from sqlalchemy import and_, desc, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.profanity_filter import contains_prohibited_phrase
from app.core.site_access import get_sites_with_permission
from app.models.employee import Employee
from app.models.feedback import FeedbackCategory, FeedbackMessage, FeedbackReply, FeedbackStatus, ProhibitedPhrase
from app.models.system_setting import SystemSetting
from app.models.site import Site
from app.models.user import Permission, Role, RolePermission, User, UserRole
from app.services.push_service import PushService
from app.schemas.feedback import FeedbackMessageOut, FeedbackReplyOut, FeedbackThreadOut, MyFeedbackItemOut

FEEDBACK_RATE_LIMIT_SECONDS = 60  # حداقل فاصله بین دو پیام از یک فرستنده (ثانیه)


logger = logging.getLogger(__name__)



PROFANITY_REVEAL_KEY = "feedback_profanity_reveal_enabled"  # system_settings؛ نبودِ ردیف = روشن

class FeedbackAccessDenied(Exception):
    """کاربر مجوز مشاهده انتقادات و پیشنهادات را ندارد."""
    pass


class FeedbackRateLimitExceeded(Exception):
    """فرستنده در بازه محدودیت نرخ، پیام دیگری فرستاده است."""
    pass


class FeedbackNotFound(Exception):
    """پیام وجود ندارد، حذف شده یا در محدوده‌ی دید کاربر نیست."""
    pass


class FeedbackClosed(Exception):
    """گفتگوی پیام بسته شده و فرستنده نمی‌تواند پاسخ بدهد."""
    pass


class FeedbackService:
    """ثبت، فهرست (با اعمال محرمانگی)، حذف نرم بازخوردها و مدیریت عبارات نامناسب."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def is_profanity_reveal_enabled(self) -> bool:
        """
        آشکار شدن هویت فرستنده‌ی پیام ناشناس در صورت الفاظ نامناسب (پیش‌فرض روشن = رفتار قبلی).
        خاموش: هیچ پیام ناشناسی (قدیم یا جدید) به‌خاطر الفاظ نامناسب آشکار نمی‌شود، برچسب «حاوی الفاظ نامناسب»
        نمایش داده نمی‌شود و متن شرایط ارسال ناشناس کوتاه می‌شود. ستون contains_profanity همچنان ثبت می‌شود.
        """
        row = await self.db.get(SystemSetting, PROFANITY_REVEAL_KEY)
        return row is None or row.value != "false"

    async def set_profanity_reveal_enabled(self, enabled: bool) -> bool:
        row = await self.db.get(SystemSetting, PROFANITY_REVEAL_KEY)
        value = "true" if enabled else "false"
        if row is None:
            self.db.add(SystemSetting(key=PROFANITY_REVEAL_KEY, value=value))
        else:
            row.value = value
        await self.db.commit()
        return enabled

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

    async def _notify_reviewers_of_new_feedback(self, sender: User, *, follow_up: bool = False) -> None:
        """
        به دارندگان مجوز feedback.view / feedback.view_all / feedback.reply (به‌جز خودِ فرستنده) اعلان Push می‌فرستد؛
        فقط کسانی که این مجوز را سراسری یا برای سایت فرستنده دارند (feedback.view_all همیشه).
        follow_up=True: پاسخ تازه‌ی فرستنده در یک گفتگو (متن متفاوت).
        متن اعلان هیچ اشاره‌ای به فرستنده، عنوان یا محتوا ندارد (حفظ محرمانگی روی صفحه قفل گوشی).
        خطاها فقط لاگ می‌شوند.
        """
        try:
            # کاربرانی که از طریق یکی از نقش‌هایشان مجوز مشاهده/پاسخ بازخورد دارند
            stmt = (
                select(User.id)
                .join(UserRole, UserRole.user_id == User.id)
                .join(Role, Role.id == UserRole.role_id)
                .join(RolePermission, RolePermission.role_id == Role.id)
                .join(Permission, Permission.id == RolePermission.permission_id)
                .where(Permission.code.in_(["feedback.view", "feedback.view_all", "feedback.reply"]))
                .distinct()
            )
            # سایت فرستنده: بازبین‌های سایتیِ سایت‌های دیگر اعلان نمی‌گیرند
            sender_site_id = await self._sender_site_id(sender)
            site_condition = UserRole.site_id.is_(None) | (Permission.code == "feedback.view_all")
            if sender_site_id is not None:
                site_condition = site_condition | (UserRole.site_id == sender_site_id)
            stmt = stmt.where(site_condition)
            result = await self.db.execute(stmt)
            user_ids = {row[0] for row in result.all()} - {sender.id}  # حذف خودِ فرستنده
            if not user_ids:
                return
            first_line = (
                "پاسخ جدیدی از فرستنده در یکی از گفتگوهای انتقادات و پیشنهادات ثبت شده است."
                if follow_up
                else "پیام جدیدی در انتقادات و پیشنهادات ثبت شده است."
            )
            await PushService(self.db).notify_users(
                user_ids,
                url="/feedback-report",
                priority="normal",
                body=f"{first_line}\nجهت مشاهده روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید.",
            )
        except Exception:
            logger.exception("ارسال Push برای پیام جدید انتقادات و پیشنهادات با خطا مواجه شد")

    async def _sender_site_id(self, sender: User) -> int | None:
        """سایت پرسنلِ متصل به کاربر فرستنده (None اگر پرسنل ندارد)."""
        if sender.employee_id is None:
            return None
        employee = await self.db.get(Employee, sender.employee_id)
        return employee.site_id if employee else None

    async def _notify_sender_of_reply(self, feedback: FeedbackMessage) -> None:
        """
        اعلان Push به فرستنده‌ی پیام وقتی بازبین پاسخ می‌دهد. متن عمومی است (بدون عنوان/متن) تا روی صفحه‌ی قفل
        چیزی از محتوا دیده نشود؛ لینک به تب «پیام‌های من». خطاها فقط لاگ می‌شوند.
        """
        try:
            await PushService(self.db).notify_users(
                {feedback.sender_id},
                url="/feedback?tab=mine",
                priority="normal",
                body="پاسخی به پیام شما در انتقادات و پیشنهادات ثبت شد.\nبرای مشاهده روی این پیام بزنید.",
            )
        except Exception:
            logger.exception("ارسال Push پاسخ انتقادات و پیشنهادات به فرستنده با خطا مواجه شد")

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

        # دارنده‌ی feedback.reply باید پیام‌های همان سایت‌ها را هم ببیند تا بتواند پاسخ دهد
        reply_sites = await get_sites_with_permission(self.db, current_user, "feedback.reply")
        if reply_sites is None:
            return None, True

        combined = view_all_sites | view_sites | reply_sites
        return combined, bool(combined)

    async def get_feedback_list(
        self,
        current_user: User,
        *,
        sender_id: int | None = None,
        site_id: int | None = None,
        category: FeedbackCategory | None = None,
        is_anonymous: bool | None = None,
        status: FeedbackStatus | None = None,
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

        profanity_reveal = await self.is_profanity_reveal_enabled()

        # شرط‌های فیلتر؛ پیام‌های حذف‌شده (حذف نرم) هرگز در فهرست نمی‌آیند
        conditions = [FeedbackMessage.is_deleted.is_(False)]
        if accessible_site_ids is not None:
            conditions.append(Employee.site_id.in_(accessible_site_ids))
        # فیلتر فرستنده/سایت برای بازبین غیر Admin فقط روی پیام‌هایی اعمال می‌شود که هویتشان برای او آشکار است؛
        # وگرنه با ?sender_id=… می‌توان پیام ناشناس را به یک نفر نسبت داد (نشت هویت از راه فیلتر).
        if (sender_id is not None or site_id is not None) and not current_user.is_superuser:
            conditions.append(
                or_(
                    FeedbackMessage.is_anonymous_requested.is_(False),
                    FeedbackMessage.contains_profanity.is_(True) if profanity_reveal else false(),
                )
            )
        if sender_id is not None:
            conditions.append(FeedbackMessage.sender_id == sender_id)
        if site_id is not None:
            conditions.append(Employee.site_id == site_id)
        if category is not None:
            conditions.append(FeedbackMessage.category == category)
        if is_anonymous is not None:
            conditions.append(FeedbackMessage.is_anonymous_requested == is_anonymous)
        if status is not None:
            conditions.append(FeedbackMessage.status == status.value)
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
        reply_sites = await self._reply_scope(current_user)
        stats = await self._reply_stats([feedback.id for feedback, *_ in rows])

        out = [
            self._message_out(
                feedback, sender, employee, site_id_val, site_name,
                viewer=current_user, profanity_reveal=profanity_reveal, reply_sites=reply_sites, stats=stats.get(feedback.id),
            )
            for feedback, sender, employee, site_id_val, site_name in rows
        ]
        return {"items": out, "total": total, "page": safe_page, "page_size": safe_page_size}

    # ---------- گفتگو (پاسخ بازبین / پیگیری فرستنده) ----------

    @staticmethod
    def _reveal_sender(feedback: FeedbackMessage, viewer: User, profanity_reveal: bool) -> bool:
        """هویت فرستنده برای این بیننده آشکار است؟ (superuser، پیام غیرناشناس، یا آشکارشده با الفاظ نامناسب)"""
        flagged = profanity_reveal and feedback.contains_profanity
        return viewer.is_superuser or not feedback.is_anonymous_requested or flagged

    @staticmethod
    def _display_name(user: User | None, employee: Employee | None) -> str:
        if employee is not None:
            return f"{employee.first_name} {employee.last_name}"
        return (user.username if user else None) or "—"

    async def _reply_scope(self, user: User) -> set[int] | None:
        """سایت‌هایی که کاربر برایشان feedback.reply دارد (None = همه؛ مجموعه‌ی خالی = هیچ)."""
        return await get_sites_with_permission(self.db, user, "feedback.reply")

    @staticmethod
    def _can_reply_to(reply_sites: set[int] | None, sender_site_id: int | None) -> bool:
        """بازبین با مجوز سراسری همه را، و با مجوز سایتی فقط پیام پرسنل همان سایت‌ها را می‌تواند پاسخ دهد."""
        if reply_sites is None:
            return True
        return sender_site_id is not None and sender_site_id in reply_sites

    async def _reply_stats(self, feedback_ids: list[int]) -> dict[int, tuple[int, datetime | None, bool]]:
        """برای هر پیام: (تعداد پاسخ، زمان آخرین پاسخ، آیا آخرین پاسخ از فرستنده است)."""
        if not feedback_ids:
            return {}
        result = await self.db.execute(
            select(FeedbackReply.feedback_id, FeedbackReply.created_at, FeedbackReply.is_from_sender)
            .where(FeedbackReply.feedback_id.in_(feedback_ids))
            .order_by(FeedbackReply.feedback_id, FeedbackReply.created_at)
        )
        stats: dict[int, tuple[int, datetime | None, bool]] = {}
        for fid, created_at, from_sender in result.all():
            count, _, _ = stats.get(fid, (0, None, False))
            stats[fid] = (count + 1, created_at, from_sender)
        return stats

    def _message_out(
        self,
        feedback: FeedbackMessage,
        sender: User,
        employee: Employee | None,
        site_id_val: int | None,
        site_name: str | None,
        *,
        viewer: User,
        profanity_reveal: bool,
        reply_sites: set[int] | None,
        stats: tuple[int, datetime | None, bool] | None,
    ) -> FeedbackMessageOut:
        """ساخت خروجی یک پیام برای بازبین با اعمال قواعد محرمانگی و اطلاعات گفتگو."""
        reveal = self._reveal_sender(feedback, viewer, profanity_reveal)
        count, last_at, last_from_sender = stats or (0, None, False)
        status = FeedbackStatus(feedback.status)
        return FeedbackMessageOut(
            id=feedback.id,
            category=feedback.category,
            title=feedback.title,
            message=feedback.message,
            is_anonymous_requested=feedback.is_anonymous_requested,
            contains_profanity=profanity_reveal and feedback.contains_profanity,
            created_at=feedback.created_at,
            sender_id=sender.id if reveal else None,
            sender_name=self._display_name(sender, employee) if reveal else None,
            site_id=site_id_val if reveal else None,
            site_name=site_name if reveal else None,
            status=status,
            reply_count=count,
            last_reply_at=last_at,
            awaiting_reviewer=status != FeedbackStatus.closed and (count == 0 or last_from_sender),
            can_reply=self._can_reply_to(reply_sites, employee.site_id if employee else None),
        )

    async def _load_for_reviewer(self, current_user: User, feedback_id: int):
        """پیام + فرستنده + پرسنل + سایت، فقط اگر در محدوده‌ی دید بازبین باشد؛ وگرنه FeedbackNotFound/FeedbackAccessDenied."""
        accessible_site_ids, has_access = await self._get_accessible_scope(current_user)
        if not has_access:
            raise FeedbackAccessDenied("اجازه مشاهده انتقادات و پیشنهادات را ندارید")
        result = await self.db.execute(
            select(FeedbackMessage, User, Employee, Site.id, Site.name)
            .join(User, User.id == FeedbackMessage.sender_id)
            .outerjoin(Employee, Employee.id == User.employee_id)
            .outerjoin(Site, Site.id == Employee.site_id)
            .where(FeedbackMessage.id == feedback_id, FeedbackMessage.is_deleted.is_(False))
        )
        row = result.first()
        if row is None:
            raise FeedbackNotFound("پیام یافت نشد")
        feedback, sender, employee, site_id_val, site_name = row
        if accessible_site_ids is not None and (employee is None or employee.site_id not in accessible_site_ids):
            raise FeedbackNotFound("پیام یافت نشد")
        return feedback, sender, employee, site_id_val, site_name

    async def _replies_out(self, feedback: FeedbackMessage, viewer: User, reveal_sender: bool) -> list[FeedbackReplyOut]:
        """پاسخ‌های یک پیام به ترتیب زمان؛ نام نویسنده‌ی پاسخ فرستنده فقط با reveal_sender."""
        result = await self.db.execute(
            select(FeedbackReply, User, Employee)
            .outerjoin(User, User.id == FeedbackReply.author_user_id)
            .outerjoin(Employee, Employee.id == User.employee_id)
            .where(FeedbackReply.feedback_id == feedback.id)
            .order_by(FeedbackReply.created_at, FeedbackReply.id)
        )
        out: list[FeedbackReplyOut] = []
        for reply, author, employee in result.all():
            show_name = reveal_sender if reply.is_from_sender else True
            out.append(
                FeedbackReplyOut(
                    id=reply.id,
                    is_from_sender=reply.is_from_sender,
                    is_mine=reply.author_user_id == viewer.id,
                    author_name=self._display_name(author, employee) if show_name else None,
                    body=reply.body,
                    created_at=reply.created_at,
                )
            )
        return out

    async def get_thread(self, current_user: User, feedback_id: int) -> FeedbackThreadOut:
        """گفتگوی یک پیام برای بازبین (view scope). هویت فرستنده در پیام و پاسخ‌هایش طبق همان قواعد محرمانگی."""
        feedback, sender, employee, site_id_val, site_name = await self._load_for_reviewer(current_user, feedback_id)
        profanity_reveal = await self.is_profanity_reveal_enabled()
        reply_sites = await self._reply_scope(current_user)
        stats = await self._reply_stats([feedback.id])
        message = self._message_out(
            feedback, sender, employee, site_id_val, site_name,
            viewer=current_user, profanity_reveal=profanity_reveal, reply_sites=reply_sites, stats=stats.get(feedback.id),
        )
        replies = await self._replies_out(feedback, current_user, message.sender_id is not None)
        return FeedbackThreadOut(message=message, replies=replies)

    async def add_reviewer_reply(self, current_user: User, feedback_id: int, body: str) -> FeedbackThreadOut:
        """
        پاسخ بازبین (feedback.reply برای سایت فرستنده یا سراسری). وضعیت پیام «پاسخ داده شد» می‌شود (حتی اگر بسته بود)
        و به فرستنده اعلان عمومی می‌رود. خطا: FeedbackAccessDenied بدون مجوز پاسخ.
        """
        feedback, _sender, employee, *_ = await self._load_for_reviewer(current_user, feedback_id)
        reply_sites = await self._reply_scope(current_user)
        if not self._can_reply_to(reply_sites, employee.site_id if employee else None):
            raise FeedbackAccessDenied("اجازه پاسخ به این پیام را ندارید")
        self.db.add(FeedbackReply(feedback_id=feedback.id, author_user_id=current_user.id, is_from_sender=False, body=body.strip()))
        feedback.status = FeedbackStatus.answered.value
        await self.db.commit()
        await self._notify_sender_of_reply(feedback)
        return await self.get_thread(current_user, feedback_id)

    async def set_status(self, current_user: User, feedback_id: int, status: FeedbackStatus) -> FeedbackThreadOut:
        """تغییر وضعیت پیگیری (در دست بررسی / بسته / بازگشایی) توسط بازبین با feedback.reply."""
        feedback, _sender, employee, *_ = await self._load_for_reviewer(current_user, feedback_id)
        reply_sites = await self._reply_scope(current_user)
        if not self._can_reply_to(reply_sites, employee.site_id if employee else None):
            raise FeedbackAccessDenied("اجازه تغییر وضعیت این پیام را ندارید")
        feedback.status = status.value
        await self.db.commit()
        return await self.get_thread(current_user, feedback_id)

    # ---------- پیام‌های خودِ کاربر ----------

    async def list_my_feedback(self, current_user: User) -> list[MyFeedbackItemOut]:
        """پیام‌های (حذف‌نشده‌ی) خودِ کاربر، جدیدترین اول، با تعداد پاسخ و نشانگر «پاسخ جدید»."""
        result = await self.db.execute(
            select(FeedbackMessage)
            .where(FeedbackMessage.sender_id == current_user.id, FeedbackMessage.is_deleted.is_(False))
            .order_by(desc(FeedbackMessage.created_at))
        )
        messages = list(result.scalars().all())
        stats = await self._reply_stats([m.id for m in messages])
        last_reviewer = await self._last_reviewer_reply_at([m.id for m in messages])
        return [self._my_item_out(m, stats.get(m.id), last_reviewer.get(m.id)) for m in messages]

    async def _last_reviewer_reply_at(self, feedback_ids: list[int]) -> dict[int, datetime]:
        """زمان آخرین پاسخ بازبین برای هر پیام (برای نشانگر «پاسخ جدید» فرستنده)."""
        if not feedback_ids:
            return {}
        result = await self.db.execute(
            select(FeedbackReply.feedback_id, func.max(FeedbackReply.created_at))
            .where(FeedbackReply.feedback_id.in_(feedback_ids), FeedbackReply.is_from_sender.is_(False))
            .group_by(FeedbackReply.feedback_id)
        )
        return dict(result.all())

    @staticmethod
    def _my_item_out(
        feedback: FeedbackMessage, stats: tuple[int, datetime | None, bool] | None, last_reviewer_at: datetime | None
    ) -> MyFeedbackItemOut:
        count, last_at, _ = stats or (0, None, False)
        has_new = last_reviewer_at is not None and (feedback.sender_seen_at is None or last_reviewer_at > feedback.sender_seen_at)
        return MyFeedbackItemOut(
            id=feedback.id,
            category=feedback.category,
            title=feedback.title,
            message=feedback.message,
            is_anonymous_requested=feedback.is_anonymous_requested,
            status=FeedbackStatus(feedback.status),
            created_at=feedback.created_at,
            reply_count=count,
            last_reply_at=last_at,
            has_new_reply=has_new,
        )

    async def my_unread_count(self, current_user: User) -> int:
        """تعداد پیام‌های کاربر که پاسخ بازبینِ دیده‌نشده دارند (برای نشانگر داشبورد)."""
        return sum(1 for item in await self.list_my_feedback(current_user) if item.has_new_reply)

    async def _load_mine(self, current_user: User, feedback_id: int) -> FeedbackMessage:
        feedback = await self.db.get(FeedbackMessage, feedback_id)
        if feedback is None or feedback.is_deleted or feedback.sender_id != current_user.id:
            raise FeedbackNotFound("پیام یافت نشد")
        return feedback

    async def get_my_thread(self, current_user: User, feedback_id: int) -> dict:
        """گفتگوی یکی از پیام‌های خودِ کاربر؛ مشاهده، زمان «دیده شد» را ثبت می‌کند (فقط برای نشانگر خودش)."""
        feedback = await self._load_mine(current_user, feedback_id)
        feedback.sender_seen_at = datetime.now(timezone.utc)
        await self.db.commit()
        stats = await self._reply_stats([feedback.id])
        last_reviewer = await self._last_reviewer_reply_at([feedback.id])
        item = self._my_item_out(feedback, stats.get(feedback.id), last_reviewer.get(feedback.id))
        replies = await self._replies_out(feedback, current_user, True)  # صاحب پیام نام خودش را می‌بیند
        return {"message": item, "replies": replies}

    async def add_my_reply(self, current_user: User, feedback_id: int, body: str) -> dict:
        """
        پاسخ فرستنده در گفتگوی پیام خودش. پیام بسته → FeedbackClosed. محدودیت نرخ مثل ارسال پیام.
        الفاظ نامناسب مثل پیام اصلی تشخیص داده می‌شود و (اگر قابلیت روشن باشد) هویت کل گفتگو را آشکار می‌کند.
        به بازبین‌ها اعلان عمومی می‌رود.
        """
        feedback = await self._load_mine(current_user, feedback_id)
        if feedback.status == FeedbackStatus.closed.value:
            raise FeedbackClosed("این گفتگو بسته شده است و امکان ارسال پاسخ ندارد.")
        await self._check_reply_rate_limit(current_user.id)
        contains_profanity = contains_prohibited_phrase(body, await self._get_prohibited_phrases())
        self.db.add(
            FeedbackReply(
                feedback_id=feedback.id,
                author_user_id=current_user.id,
                is_from_sender=True,
                body=body.strip(),
                contains_profanity=contains_profanity,
            )
        )
        if contains_profanity:
            feedback.contains_profanity = True
        await self.db.commit()
        await self._notify_reviewers_of_new_feedback(current_user, follow_up=True)
        return await self.get_my_thread(current_user, feedback_id)

    async def _check_reply_rate_limit(self, user_id: int) -> None:
        """حداکثر یک پاسخ در هر FEEDBACK_RATE_LIMIT_SECONDS از یک کاربر."""
        window_start = datetime.now(timezone.utc) - timedelta(seconds=FEEDBACK_RATE_LIMIT_SECONDS)
        result = await self.db.execute(
            select(FeedbackReply.id)
            .where(FeedbackReply.author_user_id == user_id, FeedbackReply.created_at >= window_start)
            .limit(1)
        )
        if result.first() is not None:
            raise FeedbackRateLimitExceeded("حداکثر هر یک دقیقه یک پاسخ می‌توانید بفرستید — لطفاً کمی صبر کنید.")

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
