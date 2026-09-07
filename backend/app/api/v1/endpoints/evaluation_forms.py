"""
Endpoint های «فرم‌های ارزیابی عملکرد» - شامل فرم، دسته‌بندی و سوال.

⚠️ نکته امنیتی مشترک با evaluation_structure.py: چون Endpoint های
دسته‌بندی/سوال بر اساس category_id/question_id کار می‌کنند (نه site_id
مستقیم)، ابتدا site_id واقعی از طریق زنجیره سوال→دسته‌بندی→فرم Resolve
می‌شود، سپس require_site_permission دقیقاً برای همان سایت بررسی می‌شود.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_permission_deps import require_site_permission
from app.db.session import get_db
from app.models.evaluation_content import EvaluationCategory, EvaluationForm, EvaluationQuestion
from app.models.user import User
from app.schemas.evaluation_content import (
    EvaluationCategoryIn,
    EvaluationCategoryOut,
    EvaluationFormFullOut,
    EvaluationFormIn,
    EvaluationFormOut,
    EvaluationPeriodStatusUpdate,
    EvaluationQuestionIn,
    EvaluationQuestionOut,
    TitleUpdateIn,
)
from app.services.evaluation_form_service import EvaluationFormError, EvaluationFormService

router = APIRouter()

PERMISSION_CODE = "performance.forms.manage"


async def _require_form_permission(db: AsyncSession, user: User, form_id: int) -> EvaluationForm:
    form = await db.get(EvaluationForm, form_id)
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="فرم ارزیابی موردنظر یافت نشد")
    await require_site_permission(db, user, form.site_id, PERMISSION_CODE)
    return form


async def _require_category_permission(db: AsyncSession, user: User, category_id: int) -> EvaluationCategory:
    category = await db.get(EvaluationCategory, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="دسته‌بندی موردنظر یافت نشد")
    await _require_form_permission(db, user, category.form_id)
    return category


async def _require_question_permission(db: AsyncSession, user: User, question_id: int) -> EvaluationQuestion:
    question = await db.get(EvaluationQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="سوال موردنظر یافت نشد")
    await _require_category_permission(db, user, question.category_id)
    return question


# ---------- فرم ----------


@router.get("", response_model=list[EvaluationFormOut])
async def list_forms(
    site_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return await EvaluationFormService(db).list_forms(site_id)


@router.get("/{form_id}", response_model=EvaluationFormFullOut)
async def get_form(
    form_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    try:
        return await EvaluationFormService(db).get_full_form(form_id)
    except EvaluationFormError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=EvaluationFormOut)
async def create_form(
    payload: EvaluationFormIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_site_permission(db, current_user, payload.site_id, PERMISSION_CODE)
    return await EvaluationFormService(db).create_form(payload.model_dump(), current_user.id)


@router.put("/{form_id}", response_model=EvaluationFormOut)
async def update_form(
    form_id: int,
    payload: EvaluationFormIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_form_permission(db, current_user, form_id)
    try:
        return await EvaluationFormService(db).update_form(form_id, payload.model_dump())
    except EvaluationFormError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{form_id}/status", response_model=EvaluationFormOut)
async def update_form_status(
    form_id: int,
    payload: EvaluationPeriodStatusUpdate,  # فقط یک فیلد status دارد - قابل استفاده مجدد
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_form_permission(db, current_user, form_id)
    try:
        return await EvaluationFormService(db).update_form_status(form_id, payload.status)
    except EvaluationFormError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{form_id}/title", response_model=EvaluationFormOut)
async def update_form_title(
    form_id: int,
    payload: TitleUpdateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """⚠️ برخلاف ویرایش کامل، عنوان صرف‌نظر از وضعیت فرم همیشه قابل‌تغییر است."""
    await _require_form_permission(db, current_user, form_id)
    try:
        return await EvaluationFormService(db).update_title(form_id, payload.title)
    except EvaluationFormError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{form_id}/duplicate", response_model=EvaluationFormFullOut)
async def duplicate_form(
    form_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_form_permission(db, current_user, form_id)
    try:
        return await EvaluationFormService(db).duplicate_as_new_version(form_id)
    except EvaluationFormError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_form(
    form_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    form = await db.get(EvaluationForm, form_id)
    if form is None:
        return
    await require_site_permission(db, current_user, form.site_id, PERMISSION_CODE)
    try:
        await EvaluationFormService(db).delete_form(form_id)
    except EvaluationFormError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------- دسته‌بندی ----------


@router.post("/{form_id}/categories", response_model=EvaluationCategoryOut)
async def add_category(
    form_id: int,
    payload: EvaluationCategoryIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_form_permission(db, current_user, form_id)
    try:
        return await EvaluationFormService(db).add_category(form_id, payload.model_dump())
    except EvaluationFormError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/categories/{category_id}", response_model=EvaluationCategoryOut)
async def update_category(
    category_id: int,
    payload: EvaluationCategoryIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_category_permission(db, current_user, category_id)
    try:
        return await EvaluationFormService(db).update_category(category_id, payload.model_dump())
    except EvaluationFormError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    category = await db.get(EvaluationCategory, category_id)
    if category is None:
        return
    await _require_form_permission(db, current_user, category.form_id)
    try:
        await EvaluationFormService(db).delete_category(category_id)
    except EvaluationFormError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ---------- سوال ----------


@router.post("/categories/{category_id}/questions", response_model=EvaluationQuestionOut)
async def add_question(
    category_id: int,
    payload: EvaluationQuestionIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_category_permission(db, current_user, category_id)
    dumped = payload.model_dump()
    options = dumped.pop("options")
    try:
        return await EvaluationFormService(db).add_question(category_id, dumped, options)
    except EvaluationFormError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/questions/{question_id}", response_model=EvaluationQuestionOut)
async def update_question(
    question_id: int,
    payload: EvaluationQuestionIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_question_permission(db, current_user, question_id)
    dumped = payload.model_dump()
    options = dumped.pop("options")
    try:
        return await EvaluationFormService(db).update_question(question_id, dumped, options)
    except EvaluationFormError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = await db.get(EvaluationQuestion, question_id)
    if question is None:
        return
    await _require_category_permission(db, current_user, question.category_id)
    await EvaluationFormService(db).delete_question(question_id)
