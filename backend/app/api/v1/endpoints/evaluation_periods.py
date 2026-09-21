"""Endpoint های «دوره‌های ارزیابی عملکرد»."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_permission_deps import require_site_permission
from app.db.session import get_db
from app.models.evaluation_content import EvaluationPeriod
from app.models.user import User
from app.schemas.evaluation_content import (
    EvaluationPeriodDeleteIn,
    EvaluationPeriodDisabledUpdate,
    EvaluationPeriodIn,
    EvaluationPeriodOut,
    EvaluationPeriodStatusUpdate,
    PublishedEvaluationOut,
    TitleUpdateIn,
)
from app.services.evaluation_period_service import EvaluationPeriodError, EvaluationPeriodService

router = APIRouter()

PERMISSION_CODE = "performance.periods.manage"


@router.get("", response_model=list[EvaluationPeriodOut])
async def list_periods(
    site_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await EvaluationPeriodService(db).list_periods(site_id)


@router.post("", response_model=EvaluationPeriodOut)
async def create_period(
    payload: EvaluationPeriodIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_site_permission(db, current_user, payload.site_id, PERMISSION_CODE)
    return await EvaluationPeriodService(db).create_period(payload.model_dump(), current_user.id)


@router.put("/{period_id}", response_model=EvaluationPeriodOut)
async def update_period(
    period_id: int,
    payload: EvaluationPeriodIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    period = await db.get(EvaluationPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="دوره ارزیابی موردنظر یافت نشد")
    await require_site_permission(db, current_user, period.site_id, PERMISSION_CODE)
    try:
        return await EvaluationPeriodService(db).update_period(period_id, payload.model_dump())
    except EvaluationPeriodError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{period_id}/status", response_model=EvaluationPeriodOut)
async def update_period_status(
    period_id: int,
    payload: EvaluationPeriodStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    period = await db.get(EvaluationPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="دوره ارزیابی موردنظر یافت نشد")
    await require_site_permission(db, current_user, period.site_id, PERMISSION_CODE)
    try:
        return await EvaluationPeriodService(db).update_status(period_id, payload.status)
    except EvaluationPeriodError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{period_id}/title", response_model=EvaluationPeriodOut)
async def update_period_title(
    period_id: int,
    payload: TitleUpdateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """⚠️ برخلاف ویرایش کامل، عنوان صرف‌نظر از وضعیت دوره همیشه قابل‌تغییر است."""
    period = await db.get(EvaluationPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="دوره ارزیابی موردنظر یافت نشد")
    await require_site_permission(db, current_user, period.site_id, PERMISSION_CODE)
    try:
        return await EvaluationPeriodService(db).update_title(period_id, payload.title)
    except EvaluationPeriodError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def _get_managed_period(db: AsyncSession, current_user: User, period_id: int) -> EvaluationPeriod:
    period = await db.get(EvaluationPeriod, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="دوره ارزیابی موردنظر یافت نشد")
    await require_site_permission(db, current_user, period.site_id, PERMISSION_CODE)
    return period


@router.delete("/{period_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_period(
    period_id: int,
    confirm_title: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ⚠️ دوره‌ای که ارزیابی منتشرشده دارد فقط با confirm_title (عنوان دقیق دوره)
    حذف می‌شود - همراه همه ارزیابی‌ها و نتایجش (برگشت‌ناپذیر).
    """
    period = await db.get(EvaluationPeriod, period_id)
    if period is None:
        return
    await require_site_permission(db, current_user, period.site_id, PERMISSION_CODE)
    try:
        await EvaluationPeriodService(db).delete_period(period_id, confirm_title)
    except EvaluationPeriodError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{period_id}/disabled", response_model=EvaluationPeriodOut)
async def set_period_disabled(
    period_id: int,
    payload: EvaluationPeriodDisabledUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """غیرفعال/فعال‌کردن دسترسی پرسنل به ارزیابی‌های این دوره (برگشت‌پذیر)."""
    await _get_managed_period(db, current_user, period_id)
    try:
        return await EvaluationPeriodService(db).set_disabled(period_id, payload.is_disabled)
    except EvaluationPeriodError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{period_id}/assignments", response_model=list[PublishedEvaluationOut])
async def list_published_evaluations(
    period_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ارزیابی‌های منتشرشده (انتساب‌های) یک دوره."""
    await _get_managed_period(db, current_user, period_id)
    return await EvaluationPeriodService(db).list_assignments(period_id)


@router.delete("/{period_id}/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_published_evaluation(
    period_id: int,
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """حذف یک ارزیابی منتشرشده (همراه پاسخ‌ها و نتیجه‌اش - برگشت‌ناپذیر)."""
    await _get_managed_period(db, current_user, period_id)
    try:
        await EvaluationPeriodService(db).delete_assignment(period_id, assignment_id)
    except EvaluationPeriodError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
