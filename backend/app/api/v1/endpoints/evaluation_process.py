"""
Endpoint های «جریان انجام ارزیابی».

⚠️ نکته معماری مهم: دیدن/انجام «ارزیابی‌های من» و «نتایج ارزیابی من»
هیچ Permission خاصی نمی‌خواهد - فقط داشتن حساب کاربری متصل به یک
Employee کافی است؛ چون طبق اصل بنیادی این ماژول (نگاه کنید به
evaluation_structure_service.py)، مجاز بودن به ارزیابی از روی همان
جدول‌های ساختار سازمانی (evaluation_*) تعیین می‌شود، نه از روی RBAC.
تنها عملیات سطح Admin («تولید انتساب‌ها برای یک دوره») مجوز
performance.assignments.manage می‌خواهد.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_permission_deps import require_site_permission
from app.db.session import get_db
from app.models.evaluation_content import EvaluationPeriod
from app.models.user import User
from app.schemas.evaluation_process import (
    DashboardSummaryOut,
    EvaluationOut,
    EvaluationResultOut,
    GenerateAssignmentsIn,
    GenerateAssignmentsOut,
    MyEvaluationItemOut,
    SaveAnswersIn,
    YearlyAverageOut,
)
from app.services.evaluation_assignment_service import EvaluationAssignmentError, EvaluationAssignmentService
from app.services.evaluation_process_service import EvaluationProcessError, EvaluationProcessService

router = APIRouter()


def _require_employee(user: User) -> int:
    if user.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="این قابلیت فقط برای حساب‌های متصل به پرسنل در دسترس است"
        )
    return user.employee_id


@router.post("/periods/{period_id}/generate-assignments", response_model=GenerateAssignmentsOut)
async def generate_assignments(
    period_id: int,
    payload: GenerateAssignmentsIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    period = await db.get(EvaluationPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="دوره ارزیابی موردنظر یافت نشد")
    await require_site_permission(db, current_user, period.site_id, "performance.assignments.manage")
    try:
        return await EvaluationAssignmentService(db).generate_assignments(period_id, payload.form_id)
    except EvaluationAssignmentError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/my-evaluations", response_model=list[MyEvaluationItemOut])
async def get_my_evaluations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee_id = _require_employee(current_user)
    return await EvaluationProcessService(db).get_my_evaluations(employee_id)


@router.post("/assignments/{assignment_id}/start", response_model=EvaluationOut)
async def start_evaluation(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee_id = _require_employee(current_user)
    try:
        return await EvaluationProcessService(db).start_evaluation(assignment_id, employee_id)
    except EvaluationProcessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/evaluations/{evaluation_id}/answers", response_model=EvaluationOut)
async def save_answers(
    evaluation_id: int,
    payload: SaveAnswersIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee_id = _require_employee(current_user)
    try:
        return await EvaluationProcessService(db).save_answers(
            evaluation_id, employee_id, [a.model_dump() for a in payload.answers]
        )
    except EvaluationProcessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/evaluations/{evaluation_id}/submit", response_model=EvaluationOut)
async def submit_evaluation(
    evaluation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee_id = _require_employee(current_user)
    try:
        return await EvaluationProcessService(db).submit_evaluation(evaluation_id, employee_id)
    except EvaluationProcessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/evaluations/{evaluation_id}/reopen", response_model=EvaluationOut)
async def reopen_evaluation(
    evaluation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee_id = _require_employee(current_user)
    try:
        return await EvaluationProcessService(db).reopen_for_edit(evaluation_id, employee_id)
    except EvaluationProcessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/my-results", response_model=list[EvaluationResultOut])
async def get_my_results(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee_id = _require_employee(current_user)
    return await EvaluationProcessService(db).get_my_results(employee_id)


@router.get("/my-yearly-average", response_model=YearlyAverageOut)
async def get_my_yearly_average(
    jalali_year: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee_id = _require_employee(current_user)
    return await EvaluationProcessService(db).get_yearly_average(employee_id, jalali_year)


@router.get("/my-dashboard-summary", response_model=DashboardSummaryOut)
async def get_my_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.employee_id is None:
        # کاربران مدیریتی محض (بدون Employee، مثل admin) هیچ ارزیابی‌ای
        # ندارند - نه خطا، فقط یک خلاصه خالی (کارت داشبورد اصلاً برای
        # این حساب‌ها نمایش داده نمی‌شود، ولی این Endpoint نباید ۴۰۰ بدهد)
        return DashboardSummaryOut(
            average_score=None, latest_score=None, results_count=0, pending_to_evaluate_count=0
        )
    return await EvaluationProcessService(db).get_dashboard_summary(current_user.employee_id)
