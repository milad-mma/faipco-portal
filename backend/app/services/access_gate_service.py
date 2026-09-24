"""
سرویس «پیش‌نیازهای دسترسی» (access gate).
پیش از دسترسی پرسنل به فیش حقوقی/کارکرد، گزارش تردد، درخواست مرخصی/ماموریت یا نتیجه‌ی ارزیابی، بررسی می‌کند که:
    ۱. اطلاعیه‌های خوانده‌نشده‌اش را خوانده باشد.
    ۲. اگر ارزیاب است، ارزیابی‌های انجام‌نشده‌ی دوره‌های بسته‌شده را تکمیل کرده باشد.
هر ترکیب (نوع پیش‌نیاز × قابلیت) جداگانه از پنل ادمین فعال/غیرفعال می‌شود.
اطلاعیه‌های نوع فیش حقوقی و فیش کارکرد در شمارش «خوانده‌نشده» حساب نمی‌شوند تا دیدن فیش به خواندن خودِ فیش وابسته نشود.
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

# نام قابلیت‌ها: همین رشته‌ها در کلید تنظیمات ذخیره می‌شوند و فرانت‌اند هم از آن‌ها استفاده می‌کند؛
# تغییرشان تنظیمات ذخیره‌شده‌ی ادمین را بی‌اثر می‌کند.
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
    """ورودی: نوع پیش‌نیاز و قابلیت. خروجی: کلید تنظیم به شکل access_gate.<gate>.<feature>."""
    return f"access_gate.{gate}.{feature}"


class AccessGateBlocked(Exception):
    """وقتی کاربر پیش‌نیاز را انجام نداده - در لایه Endpoint به ۴۰۳ تبدیل می‌شود."""

    def __init__(self, message: str, gate: str):
        """ورودی: پیام خطا برای کاربر و نوع پیش‌نیازی که مانع شده (gate)."""
        super().__init__(message)
        self.gate = gate


class AccessGateService:
    """بررسی و گزارش وضعیت پیش‌نیازهای دسترسی کاربر؛ ورودی سازنده: نشست دیتابیس."""
    def __init__(self, db: AsyncSession):
        """نشست async دیتابیس را نگه می‌دارد."""
        self.db = db

    async def is_gate_enabled(self, gate: str, feature: str) -> bool:
        """آیا پیش‌نیاز gate برای قابلیت feature فعال است؛ پیش‌فرض خاموش است تا نصب/به‌روزرسانی کسی را قفل نکند."""
        settings = SystemSettingsService(self.db)
        return await settings.get_access_gate(setting_key(gate, feature))

    async def count_unread_notices(self, user: User) -> int:
        """
        تعداد اطلاعیه‌های خوانده‌نشده‌ی کاربر (به‌جز فیش حقوقی/کارکرد) را برمی‌گرداند.
        همان قواعد مخاطب‌یابی list_for_user اعمال می‌شود (هدف‌گذاری، انتشار، انقضا، تاریخ پیوستن پرسنل)
        تا کاربر به‌خاطر اطلاعیه‌ای که نمی‌بیند قفل نشود.
        """
        now = datetime.now(timezone.utc)

        # نقش‌های کاربر (برای اطلاعیه‌های هدف‌گذاری‌شده بر اساس نقش)
        result = await self.db.execute(select(UserRole.role_id).where(UserRole.user_id == user.id))
        role_ids = {row[0] for row in result.all()}

        # ساخت شرط‌های مخاطب: همه، سایت، واحد، خودِ پرسنل و نقش‌ها
        target_conditions = [NoticeTarget.target_type == NoticeTargetType.all]
        joined_at = None  # تاریخ ثبت پرسنل؛ اطلاعیه‌های پیش از آن شمرده نمی‌شوند
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

        # زیرکوئری‌ها: اطلاعیه‌های مخاطب این کاربر و اطلاعیه‌هایی که قبلاً خوانده
        matching_notice_ids = select(NoticeTarget.notice_id).where(or_(*target_conditions))
        read_notice_ids = select(NoticeRead.notice_id).where(NoticeRead.user_id == user.id)

        # فیلترهای اطلاعیه‌ی منتشرشده، حذف‌نشده، در بازه‌ی انتشار، مخاطب کاربر و خوانده‌نشده
        filters = [
            Notice.status == NoticeStatus.published,
            Notice.is_deleted.is_(False),
            or_(Notice.publish_at.is_(None), Notice.publish_at <= now),
            or_(Notice.expire_at.is_(None), Notice.expire_at >= now),
            Notice.id.in_(matching_notice_ids),
            Notice.id.notin_(read_notice_ids),
            # اطلاعیه‌های فیش حقوقی/کارکرد شمرده نمی‌شوند
            Notice.notice_type.notin_([NoticeType.payroll, NoticeType.attendance_card]),
        ]
        if joined_at is not None:
            filters.append(func.coalesce(Notice.publish_at, Notice.created_at) >= joined_at)

        count_result = await self.db.execute(select(func.count()).select_from(Notice).where(and_(*filters)))
        return count_result.scalar_one()

    async def count_pending_evaluations(self, user: User) -> int:
        """
        تعداد ارزیابی‌های انجام‌نشده‌ی کاربر (به‌عنوان ارزیاب) در دوره‌های بسته‌شده/بایگانی‌شده و غیرغیرفعال.
        دوره‌های پیش‌نویس، زمان‌بندی‌شده و فعال اجبار ندارند؛ دوره با پایان مهلت خودکار بسته می‌شود و از آن لحظه قفل اعمال می‌شود.
        ادمین با غیرفعال کردن اجبار، تغییر زمان‌بندی یا برگرداندن دوره به «فعال» قفل را برمی‌دارد. کاربر بدون پرسنل: 0.
        """
        if user.employee_id is None:
            return 0
        # شمارش انتساب‌های pending این ارزیاب در دوره‌های closed/archived
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
        همان شرط count_pending_evaluations، گروه‌بندی‌شده بر اساس دوره تا دیالوگ نام دوره‌ها را نشان دهد.
        خروجی: لیست {"period_title", "count"} مرتب بر اساس عنوان دوره.
        """
        if user.employee_id is None:
            return []
        # شمارش انتساب‌های pending به تفکیک دوره
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
        پیش‌نیازهای فعال برای قابلیت feature را بررسی می‌کند؛ در صورت وجود مانع AccessGateBlocked می‌اندازد، وگرنه چیزی برنمی‌گرداند.
        superuser هرگز قفل نمی‌شود تا همیشه بتواند به تنظیمات دسترسی داشته باشد و اجبار را خاموش کند.
        """
        if user.is_superuser:
            return

        # پیش‌نیاز اول: اطلاعیه‌های خوانده‌نشده
        if await self.is_gate_enabled(GATE_UNREAD_NOTICES, feature):
            unread = await self.count_unread_notices(user)
            if unread > 0:
                raise AccessGateBlocked(
                    f"برای دسترسی به این بخش، ابتدا باید {unread} اطلاعیه خوانده‌نشده خود را مطالعه کنید.",
                    GATE_UNREAD_NOTICES,
                )

        # پیش‌نیاز دوم: ارزیابی‌های انجام‌نشده
        if await self.is_gate_enabled(GATE_PENDING_EVALUATIONS, feature):
            pending = await self.count_pending_evaluations(user)
            if pending > 0:
                # نام دوره‌ها در متن پیام ۴۰۳ می‌آید تا دیالوگی که از پاسخ خطا باز می‌شود هم بتواند آن‌ها را نشان دهد
                by_period = await self.pending_evaluations_by_period(user)
                detail = "، ".join(f"{p['period_title']} ({p['count']} مورد)" for p in by_period)
                message = f"برای دسترسی به این بخش، ابتدا باید {pending} ارزیابی انجام‌نشده خود را تکمیل کنید."
                if detail:
                    message += f" دوره‌های مربوطه: {detail}"
                raise AccessGateBlocked(message, GATE_PENDING_EVALUATIONS)

    async def get_status(self, user: User) -> dict:
        """
        وضعیت کامل قفل‌ها برای فرانت‌اند در یک پاسخ: تعداد اطلاعیه‌های خوانده‌نشده، ارزیابی‌های انجام‌نشده (به تفکیک دوره)
        و blocked_features (نگاشت قابلیت به نوع پیش‌نیاز مانع) تا UI پیش از کلیک هشدار دهد. برای superuser همه‌چیز خالی است.
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

        # برای هر قابلیت، اولین پیش‌نیاز فعالِ برآورده‌نشده (اول اطلاعیه، بعد ارزیابی) ثبت می‌شود
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
