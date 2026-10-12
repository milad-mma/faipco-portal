"""
«معاف از ارزیابی» (Migration 110؛ docs/performance-evaluation-structure.md).

پرسنل این فهرست در «تولید انتساب» ارزیابی نمی‌شوند. نوع معافیت (scope):
- target_only «فقط ارزیابی نشود» (پیش‌فرض): ارزیابی نمی‌شود ولی ارزیابی می‌کند؛
- full «کامل»: نه ارزیابی می‌شود و نه ارزیاب است.
افزودن به فهرست انتساب‌های موجود را تغییر نمی‌دهد؛ remove_pending انتساب‌های انجام‌نشده‌ی او را (متناسب با نوع:
فقط به‌عنوان هدف، یا هدف و ارزیاب) در دوره‌های باز حذف می‌کند — ارزیابی‌های ثبت‌نهایی‌شده دست نمی‌خورند.
"""
from __future__ import annotations

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.evaluation import EvaluationExemption
from app.models.evaluation_content import EvaluationPeriod, EvaluationPeriodStatus
from app.models.evaluation_process import EvaluationAssignment, EvaluationAssignmentStatus
from app.models.user import User

SCOPE_TARGET_ONLY = "target_only"
SCOPE_FULL = "full"
SCOPES = (SCOPE_TARGET_ONLY, SCOPE_FULL)
OPEN_PERIOD_STATUSES = (EvaluationPeriodStatus.draft, EvaluationPeriodStatus.scheduled, EvaluationPeriodStatus.active)


class EvaluationExemptionError(Exception):
    """خطای قابل نمایش (فارسی)."""


async def exemption_sets(db: AsyncSession) -> tuple[set[int], set[int]]:
    """(کسانی که ارزیابی نمی‌شوند = همه‌ی معاف‌ها، کسانی که ارزیاب هم نیستند = معافیت کامل)."""
    rows = (await db.execute(select(EvaluationExemption.employee_id, EvaluationExemption.scope))).all()
    return {eid for eid, _ in rows}, {eid for eid, scope in rows if scope == SCOPE_FULL}


def _pending_filter(employee_id: int, scope: str):
    open_periods = select(EvaluationPeriod.id).where(EvaluationPeriod.status.in_(OPEN_PERIOD_STATUSES))
    who = (
        or_(
            EvaluationAssignment.target_employee_id == employee_id,
            EvaluationAssignment.evaluator_employee_id == employee_id,
        )
        if scope == SCOPE_FULL
        else EvaluationAssignment.target_employee_id == employee_id
    )
    return (
        EvaluationAssignment.status == EvaluationAssignmentStatus.pending,
        EvaluationAssignment.period_id.in_(open_periods),
        who,
    )


async def pending_count(db: AsyncSession, employee_id: int, scope: str) -> int:
    return (
        await db.execute(select(func.count(EvaluationAssignment.id)).where(*_pending_filter(employee_id, scope)))
    ).scalar_one()


def _label(emp: Employee) -> str:
    return f"{emp.first_name} {emp.last_name} ({emp.personnel_code})"


async def list_exemptions(db: AsyncSession, site_id: int) -> list[dict]:
    rows = (
        await db.execute(
            select(EvaluationExemption, Employee)
            .join(Employee, Employee.id == EvaluationExemption.employee_id)
            .where(EvaluationExemption.site_id == site_id)
            .order_by(Employee.last_name, Employee.first_name)
        )
    ).all()
    out = []
    for ex, emp in rows:
        out.append(
            {
                "employee_id": emp.id,
                "employee": _label(emp),
                "reason": ex.reason,
                "scope": ex.scope,
                "created_at": ex.created_at,
                "pending_count": await pending_count(db, emp.id, ex.scope),
            }
        )
    return out


async def add_exemption(
    db: AsyncSession, site_id: int, employee_id: int, reason: str | None, user: User, scope: str = SCOPE_TARGET_ONLY
) -> dict:
    """افزودن یا ویرایش (دلیل/نوع) معافیت یک پرسنل."""
    if scope not in SCOPES:
        raise EvaluationExemptionError("نوع معافیت نامعتبر است")
    emp = await db.get(Employee, employee_id)
    if emp is None or emp.site_id != site_id:
        raise EvaluationExemptionError("پرسنل انتخاب‌شده از این سایت نیست")
    row = (
        await db.execute(select(EvaluationExemption).where(EvaluationExemption.employee_id == employee_id))
    ).scalar_one_or_none()
    if row is None:
        row = EvaluationExemption(site_id=site_id, employee_id=employee_id, created_by_user_id=user.id)
        db.add(row)
    row.reason = (reason or "").strip()[:300] or None
    row.scope = scope
    await db.commit()
    return {
        "employee_id": emp.id,
        "employee": _label(emp),
        "reason": row.reason,
        "scope": row.scope,
        "pending_count": await pending_count(db, emp.id, row.scope),
    }


async def remove_exemption(db: AsyncSession, site_id: int, employee_id: int) -> None:
    await db.execute(
        delete(EvaluationExemption).where(
            EvaluationExemption.site_id == site_id, EvaluationExemption.employee_id == employee_id
        )
    )
    await db.commit()


async def remove_pending(db: AsyncSession, site_id: int, employee_id: int) -> int:
    """
    حذف انتساب‌های انجام‌نشده‌ی پرسنل معاف در دوره‌های باز: «فقط ارزیابی نشود» فقط جایی که هدف است؛ «کامل» هدف یا
    ارزیاب. فقط برای پرسنلِ داخل فهرست معاف.
    """
    scope = (
        await db.execute(
            select(EvaluationExemption.scope).where(
                EvaluationExemption.site_id == site_id, EvaluationExemption.employee_id == employee_id
            )
        )
    ).scalar_one_or_none()
    if scope is None:
        raise EvaluationExemptionError("این پرسنل در فهرست معاف از ارزیابی نیست")
    ids = (
        await db.execute(select(EvaluationAssignment.id).where(*_pending_filter(employee_id, scope)))
    ).scalars().all()
    for aid in ids:
        assignment = await db.get(EvaluationAssignment, aid)
        if assignment is not None:
            await db.delete(assignment)  # CASCADE پیش‌نویس ارزیابی و پاسخ‌ها
    await db.commit()
    return len(ids)
