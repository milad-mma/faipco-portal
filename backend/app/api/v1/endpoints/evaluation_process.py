"""
Endpoint های «جریان انجام ارزیابی»: تولید انتساب‌ها، فهرست ارزیابی‌های من، شروع/ذخیره/ثبت/بازگشایی
ارزیابی، نتایج و جزئیات نتایج من، میانگین سالانه و خلاصه داشبورد.

دیدن/انجام «ارزیابی‌های من» و «نتایج من» مجوز RBAC نمی‌خواهد؛ فقط حساب کاربری باید به یک
Employee متصل باشد، چون مجاز بودن به ارزیابی از جدول‌های ساختار ارزیابی (evaluation_*) تعیین
می‌شود. تنها عملیات مدیریتی (تولید انتساب‌ها) مجوز performance.assignments.manage می‌خواهد.
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
    MyAnswerOut,
    SaveAnswersIn,
    ShiftLeadEvaluationOut,
    YearlyAverageOut,
)
from app.services.evaluation_assignment_service import EvaluationAssignmentError, EvaluationAssignmentService
from app.services.evaluation_process_service import EvaluationProcessError, EvaluationProcessService
from app.services.access_gate_service import AccessGateBlocked, AccessGateService

router = APIRouter()


def _require_employee(user: User) -> int:
    """employee_id کاربر جاری را برمی‌گرداند؛ اگر حساب به پرسنل متصل نباشد 400 می‌دهد."""
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
    """
    تولید انتساب‌های ارزیابی یک دوره با فرم داده‌شده از روی ساختار ارزیابی.
    نیازمند مجوز performance.assignments.manage روی سایت دوره. خطاها: 404 دوره یافت نشد، 400 خطای سرویس.
    """
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
    """فهرست ارزیابی‌هایی که کاربر جاری باید انجام دهد؛ نیازمند حساب متصل به پرسنل (400)."""
    employee_id = _require_employee(current_user)
    return await EvaluationProcessService(db).get_my_evaluations(employee_id)


@router.get("/my-shift-lead-evaluations", response_model=list[ShiftLeadEvaluationOut])
async def get_my_shift_lead_evaluations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    فهرست ارزیابی‌های انجام‌شده توسط سرشیفت‌های واحدهایی که کاربر جاری سرپرست آن‌هاست،
    تا سرپرست بتواند آن‌ها را ببیند/ویرایش کند. اگر کاربر سرپرست نباشد یا واحد سرشیفت نداشته باشد، خالی است.
    """
    employee_id = _require_employee(current_user)
    return await EvaluationProcessService(db).get_shift_lead_evaluations(employee_id)


@router.post("/assignments/{assignment_id}/start", response_model=EvaluationOut)
async def start_evaluation(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """شروع (یا ادامه) ارزیابی یک انتساب توسط ارزیابِ همان انتساب؛ خروجی ارزیابی کامل. 400 اگر مجاز نباشد."""
    employee_id = _require_employee(current_user)
    try:
        return await EvaluationProcessService(db).start_evaluation(assignment_id, employee_id)
    except EvaluationProcessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationOut)
async def get_evaluation(
    evaluation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    بازکردن ارزیابی با evaluation_id؛ علاوه بر ارزیاب اصلی، سرپرستِ سرشیفت ارزیاب هم مجاز است
    (برای ادامه ویرایش ارزیابی سرشیفت پس از reopen). 400 اگر کاربر دسترسی نداشته باشد.
    """
    employee_id = _require_employee(current_user)
    try:
        return await EvaluationProcessService(db).get_evaluation(evaluation_id, employee_id)
    except EvaluationProcessError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/evaluations/{evaluation_id}/answers", response_model=EvaluationOut)
async def save_answers(
    evaluation_id: int,
    payload: SaveAnswersIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ذخیره پاسخ‌های پیش‌نویس ارزیابی توسط ارزیاب مجاز؛ خروجی ارزیابی به‌روزشده. 400 در خطای اعتبارسنجی/دسترسی."""
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
    """ثبت نهایی ارزیابی و محاسبه امتیاز کل؛ 400 اگر سوال الزامی بی‌پاسخ باشد یا کاربر مجاز نباشد."""
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
    """بازگشایی ارزیابی ثبت‌شده برای ویرایش (ارزیاب یا سرپرستِ سرشیفت)؛ 400 اگر مجاز نباشد."""
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
    """
    فهرست نتایج ارزیابی‌های ثبت‌شده درباره کاربر جاری.
    خطاها: 403 اگر پیش‌نیاز دسترسی (access gate) برقرار نباشد، 400 اگر حساب به پرسنل متصل نباشد.
    """
    # پیش‌نیاز دسترسی: اگر ادمین اجبار را فعال کرده باشد و کاربر اطلاعیه خوانده‌نشده
    # یا ارزیابی انجام‌نشده داشته باشد، ۴۰۳ برمی‌گردد
    try:
        await AccessGateService(db).check(current_user, "evaluation_result")
    except AccessGateBlocked as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    employee_id = _require_employee(current_user)
    return await EvaluationProcessService(db).get_my_results(employee_id)


@router.get("/my-results/{evaluation_id}/answers", response_model=list[MyAnswerOut])
async def get_my_result_answers(
    evaluation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """جزئیات سوال‌به‌سوال یک نتیجه برای خود پرسنل (فقط ارزیابی‌های ثبت‌شده‌ای که هدفش بوده، بدون نظر ارزیاب)؛ 404 در غیر این صورت."""
    employee_id = _require_employee(current_user)
    try:
        return await EvaluationProcessService(db).get_my_result_answers(evaluation_id, employee_id)
    except EvaluationProcessError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/my-yearly-average", response_model=YearlyAverageOut)
async def get_my_yearly_average(
    jalali_year: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """میانگین امتیاز کاربر جاری در یک سال شمسی (پیش‌فرض: سال جاری)؛ نیازمند حساب متصل به پرسنل."""
    employee_id = _require_employee(current_user)
    return await EvaluationProcessService(db).get_yearly_average(employee_id, jalali_year)


@router.get("/my-dashboard-summary", response_model=DashboardSummaryOut)
async def get_my_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """خلاصه ارزیابی کاربر جاری برای کارت داشبورد؛ برای حساب بدون پرسنل خلاصه خالی (بدون خطا) برمی‌گرداند."""
    if current_user.employee_id is None:
        # کاربران مدیریتی بدون Employee (مثل admin) ارزیابی ندارند؛ خلاصه خالی برمی‌گردد نه خطای ۴۰۰
        return DashboardSummaryOut(
            average_score=None, latest_score=None, results_count=0, pending_to_evaluate_count=0
        )
    return await EvaluationProcessService(db).get_dashboard_summary(current_user.employee_id)
