"""
سرویس «پیش‌نیازهای دسترسی» — طبق درخواست صریح کاربر، قبل از اینکه
پرسنل بتواند فیش حقوقی/کارکرد، گزارش تردد، درخواست مرخصی/ماموریت یا
نتیجه ارزیابی خود را ببیند، باید:

    ۱. اطلاعیه‌های خوانده‌نشده‌اش را خوانده باشد.
    ۲. اگر خودش ارزیاب است، ارزیابی‌های انجام‌نشده‌اش را تکمیل کرده باشد.

⚠️ هر قابلیت به‌تفکیک از پنل ادمین قابل فعال/غیرفعال‌سازی است - اگر
ادمین نخواست این اجبار باشد، می‌تواند خاموشش کند.

⚠️ استثنای مهم (طبق تصمیم صریح کاربر): خودِ اطلاعیه‌های فیش حقوقی و
فیش کارکرد از شمارش «خوانده‌نشده» کنار گذاشته می‌شوند - وگرنه حلقه
می‌شد: برای دیدن فیش باید اطلاعیه‌اش را می‌خواند، ولی خودِ آن اطلاعیه
همان فیش بود.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.evaluation_content import EvaluationPeriod, EvaluationPeriodStatus
from app.models.evaluation_process import (
    EvaluationAssignment,
    EvaluationAssignmentStatus,
)
from app.models.notice import Notice, NoticeStatus, NoticeTarget, NoticeTargetType, NoticeType
from app.models.notice_read import NoticeRead
from app.models.user import User, UserRole
from app.services.system_settings_service import SystemSettingsService

# ⚠️ نام هر قابلیت - همان رشته‌ای که هم در تنظیمات ذخیره می‌شود، هم
# فرانت‌اند برای تشخیص استفاده می‌کند. تغییرشان یعنی از دست رفتن تنظیم
# قبلی ادمین، پس ثابت نگه داشته می‌شوند.
FEATURE_PAYROLL = "payroll_receipt"
FEATURE_ATTENDANCE_CARD = "attendance_card"
FEATURE_ATTENDANCE_REPORT = "attendance_report"
FEATURE_LEAVE_REQUEST = "leave_request"
FEATURE_EVALUATION_RESULT = "evaluation_result"

ALL_FEATURES = [
    FEATURE_PAYROLL,
    FEATURE_ATTENDANCE_CARD,
    FEATURE_ATTENDANCE_REPORT,
    FEATURE_LEAVE_REQUEST,
    FEATURE_EVALUATION_RESULT,
]

# دو نوع اجبار، مستقل از هم
GATE_UNREAD_NOTICES = "unread_notices"
GATE_PENDING_EVALUATIONS = "pending_evaluations"

ALL_GATES = [GATE_UNREAD_NOTICES, GATE_PENDING_EVALUATIONS]


def setting_key(gate: str, feature: str) -> str:
    return f"access_gate.{gate}.{feature}"


class AccessGateBlocked(Exception):
    """وقتی کاربر پیش‌نیاز را انجام نداده - در لایه Endpoint به ۴۰۳ تبدیل می‌شود."""

    def __init__(self, message: str, gate: str):
        super().__init__(message)
        self.gate = gate


class AccessGateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def is_gate_enabled(self, gate: str, feature: str) -> bool:
        """⚠️ پیش‌فرض **خاموش** است - این یک محدودیت است و نباید با نصب/به‌روزرسانی ناگهان همه را قفل کند."""
        settings = SystemSettingsService(self.db)
        return await settings.get_access_gate(setting_key(gate, feature))

    async def count_unread_notices(self, user: User) -> int:
        """
        تعداد اطلاعیه‌های خوانده‌نشده‌ی این کاربر.

        ⚠️ اطلاعیه‌های نوع فیش حقوقی/کارکرد عمداً شمرده نمی‌شوند - طبق
        تصمیم صریح کاربر، از این محدودیت معاف‌اند تا حلقه ایجاد نشود.

        ⚠️ همان قواعد مخاطب‌یابی list_for_user اینجا هم اعمال می‌شود
        (هدف‌گذاری، انتشار، انقضا، و تاریخ پیوستن پرسنل) - وگرنه کاربر
        ممکن بود به‌خاطر اطلاعیه‌ای که اصلاً نمی‌بیند قفل شود.
        """
        now = datetime.now(timezone.utc)

        result = await self.db.execute(select(UserRole.role_id).where(UserRole.user_id == user.id))
        role_ids = {row[0] for row in result.all()}

        target_conditions = [NoticeTarget.target_type == NoticeTargetType.all]
        joined_at = None
        if user.employee_id is not None:
            employee = await self.db.get(Employee, user.employee_id)
            if employee is not None:
                joined_at = employee.created_at
                target_conditions.append(
                    and_(
                        NoticeTarget.target_type == NoticeTargetType.site,
                        NoticeTarget.target_id == employee.site_id,
                    )
                )
                if employee.department_id is not None:
                    target_conditions.append(
                        and_(
                            NoticeTarget.target_type == NoticeTargetType.department,
                            NoticeTarget.target_id == employee.department_id,
                        )
                    )
            target_conditions.append(
                and_(
                    NoticeTarget.target_type == NoticeTargetType.employee,
                    NoticeTarget.target_id == user.employee_id,
                )
            )
        if role_ids:
            target_conditions.append(
                and_(
                    NoticeTarget.target_type == NoticeTargetType.role,
                    NoticeTarget.target_id.in_(role_ids),
                )
            )

        matching_notice_ids = select(NoticeTarget.notice_id).where(or_(*target_conditions))
        read_notice_ids = select(NoticeRead.notice_id).where(NoticeRead.user_id == user.id)

        filters = [
            Notice.status == NoticeStatus.published,
            Notice.is_deleted.is_(False),
            or_(Notice.publish_at.is_(None), Notice.publish_at <= now),
            or_(Notice.expire_at.is_(None), Notice.expire_at >= now),
            Notice.id.in_(matching_notice_ids),
            Notice.id.notin_(read_notice_ids),
            # ⚠️ معافیت فیش‌ها - جلوگیری از حلقه
            Notice.notice_type.notin_([NoticeType.payroll, NoticeType.attendance_card]),
        ]
        if joined_at is not None:
            filters.append(func.coalesce(Notice.publish_at, Notice.created_at) >= joined_at)

        count_result = await self.db.execute(select(func.count()).select_from(Notice).where(and_(*filters)))
        return count_result.scalar_one()

    async def count_pending_evaluations(self, user: User) -> int:
        """
        ⚠️ طبق تصمیم صریح کاربر: اجبار به وضعیت **بسته‌شده/بایگانی‌شده**
        دوره گره خورده است - نه به «فعالِ منقضی».

        منطق: تا وقتی دوره در جریان است (زمان‌بندی‌شده یا فعال)، ارزیاب
        فرصت دارد و آزاد است. دوره با پایان مهلت **خودکار** بسته می‌شود؛
        از همان لحظه، اگر ارزیابی ناتمامی مانده باشد، ارزیاب قفل می‌شود.

            پیش‌نویس        → اجبار ندارد (دوره هنوز واقعی نشده)
            زمان‌بندی‌شده   → اجبار ندارد (هنوز شروع نشده)
            فعال            → اجبار ندارد (هنوز در مهلت)
            بسته‌شده        → **اجبار فعال**
            بایگانی‌شده     → **اجبار فعال**

        سه راه خروج برای ادمین: غیرفعال‌کردن اجبار از تنظیمات، تغییر
        زمان‌بندی دوره، یا برگرداندن دستی وضعیت دوره به «فعال».
        """
        if user.employee_id is None:
            return 0
        result = await self.db.execute(
            select(func.count())
            .select_from(EvaluationAssignment)
            .join(EvaluationPeriod, EvaluationPeriod.id == EvaluationAssignment.period_id)
            .where(
                EvaluationAssignment.evaluator_employee_id == user.employee_id,
                EvaluationAssignment.status == EvaluationAssignmentStatus.pending,
                EvaluationPeriod.status.in_(
                    [EvaluationPeriodStatus.closed, EvaluationPeriodStatus.archived]
                ),
                EvaluationPeriod.is_disabled.is_(False),
            )
        )
        return result.scalar_one()

    async def pending_evaluations_by_period(self, user: User) -> list[dict]:
        """
        ⚠️ طبق درخواست صریح کاربر: دیالوگ باید بگوید آن ارزیابی‌های
        انجام‌نشده مربوط به **کدام دوره** هستند - نه فقط یک عدد کل.

        همان شرط count_pending_evaluations، ولی گروه‌بندی‌شده بر اساس دوره.
        """
        if user.employee_id is None:
            return []
        result = await self.db.execute(
            select(EvaluationPeriod.title, func.count(EvaluationAssignment.id))
            .select_from(EvaluationAssignment)
            .join(EvaluationPeriod, EvaluationPeriod.id == EvaluationAssignment.period_id)
            .where(
                EvaluationAssignment.evaluator_employee_id == user.employee_id,
                EvaluationAssignment.status == EvaluationAssignmentStatus.pending,
                EvaluationPeriod.status.in_(
                    [EvaluationPeriodStatus.closed, EvaluationPeriodStatus.archived]
                ),
                EvaluationPeriod.is_disabled.is_(False),
            )
            .group_by(EvaluationPeriod.id, EvaluationPeriod.title)
            .order_by(EvaluationPeriod.title)
        )
        return [{"period_title": title, "count": count} for title, count in result.all()]

    async def check(self, user: User, feature: str) -> None:
        """
        بررسی پیش‌نیازها برای یک قابلیت. اگر مانعی باشد AccessGateBlocked
        می‌اندازد؛ وگرنه بی‌صدا برمی‌گردد.

        ⚠️ Admin واقعی هرگز قفل نمی‌شود - وگرنه اگر ادمین خودش اطلاعیه
        نخوانده داشت، نمی‌توانست وارد تنظیمات شود و این قابلیت را خاموش
        کند؛ یک بن‌بست کامل.
        """
        if user.is_superuser:
            return

        if await self.is_gate_enabled(GATE_UNREAD_NOTICES, feature):
            unread = await self.count_unread_notices(user)
            if unread > 0:
                raise AccessGateBlocked(
                    f"برای دسترسی به این بخش، ابتدا باید {unread} اطلاعیه خوانده‌نشده خود را مطالعه کنید.",
                    GATE_UNREAD_NOTICES,
                )

        if await self.is_gate_enabled(GATE_PENDING_EVALUATIONS, feature):
            pending = await self.count_pending_evaluations(user)
            if pending > 0:
                # ⚠️ نام دوره‌ها در خودِ پیام ۴۰۳ می‌آید تا دیالوگی که از
                # یک پاسخ خطا باز می‌شود (نه از وضعیت پیش‌بارگذاری‌شده) هم
                # بتواند بگوید ارزیابی‌ها مربوط به کدام دوره‌اند.
                by_period = await self.pending_evaluations_by_period(user)
                detail = "، ".join(f"{p['period_title']} ({p['count']} مورد)" for p in by_period)
                message = f"برای دسترسی به این بخش، ابتدا باید {pending} ارزیابی انجام‌نشده خود را تکمیل کنید."
                if detail:
                    message += f" دوره‌های مربوطه: {detail}"
                raise AccessGateBlocked(message, GATE_PENDING_EVALUATIONS)

    async def get_status(self, user: User) -> dict:
        """
        ⚠️ برای فرانت‌اند - یک درخواست، همه‌چیز: کدام قابلیت‌ها قفل‌اند و
        چرا. تا UI بتواند قبل از کلیک هم هشدار نشان دهد (نه اینکه کاربر
        کلیک کند و ۴۰۳ بگیرد).
        """
        if user.is_superuser:
            return {
                "unread_notices": 0,
                "pending_evaluations": 0,
                "pending_by_period": [],
                "blocked_features": {},
            }

        unread = await self.count_unread_notices(user)
        pending = await self.count_pending_evaluations(user)

        blocked: dict[str, str] = {}
        for feature in ALL_FEATURES:
            if unread > 0 and await self.is_gate_enabled(GATE_UNREAD_NOTICES, feature):
                blocked[feature] = GATE_UNREAD_NOTICES
            elif pending > 0 and await self.is_gate_enabled(GATE_PENDING_EVALUATIONS, feature):
                blocked[feature] = GATE_PENDING_EVALUATIONS

        return {
            "unread_notices": unread,
            "pending_evaluations": pending,
            "pending_by_period": await self.pending_evaluations_by_period(user) if pending else [],
            "blocked_features": blocked,
        }
