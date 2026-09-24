"""
Endpoint های «فرم‌های ارزیابی عملکرد»: فرم، دسته‌بندی و سوال (فرم‌ساز).
عملیات تغییر نیازمند مجوز سایتیِ performance.forms.manage است. چون endpointهای دسته‌بندی/سوال
با category_id/question_id کار می‌کنند، ابتدا site_id واقعی از زنجیره سوال→دسته‌بندی→فرم
به دست می‌آید و سپس require_site_permission برای همان سایت بررسی می‌شود.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_permission_deps import require_site_permission
from app.core.site_access import get_accessible_site_ids
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
    """فرم را می‌خواند و مجوز مدیریت فرم را روی سایت آن بررسی می‌کند؛ 404 اگر فرم نباشد."""
    form = await db.get(EvaluationForm, form_id)
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="فرم ارزیابی موردنظر یافت نشد")
    await require_site_permission(db, user, form.site_id, PERMISSION_CODE)
    return form


async def _require_category_permission(db: AsyncSession, user: User, category_id: int) -> EvaluationCategory:
    """دسته‌بندی را می‌خواند و مجوز را از طریق فرم والد بررسی می‌کند؛ 404 اگر دسته‌بندی نباشد."""
    category = await db.get(EvaluationCategory, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="دسته‌بندی موردنظر یافت نشد")
    await _require_form_permission(db, user, category.form_id)
    return category


async def _require_question_permission(db: AsyncSession, user: User, question_id: int) -> EvaluationQuestion:
    """سوال را می‌خواند و مجوز را از طریق دسته‌بندی و فرم والد بررسی می‌کند؛ 404 اگر سوال نباشد."""
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
    current_user: User = Depends(get_current_user),
):
    """فهرست فرم‌ها (اختیاری فیلتر بر اساس سایت)؛ فقط فرم‌های سایت‌های در دسترس کاربر و فرم‌های سراسری."""
    allowed = await get_accessible_site_ids(db, current_user)
    return await EvaluationFormService(db).list_forms(site_id, allowed)


@router.get("/{form_id}", response_model=EvaluationFormFullOut)
async def get_form(
    form_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """فرم کامل همراه دسته‌بندی‌ها، سوالات و گزینه‌ها؛ فرم سایت خارج از دسترس کاربر یا ناموجود → 404."""
    try:
        form = await EvaluationFormService(db).get_full_form(form_id)
    except EvaluationFormError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    allowed = await get_accessible_site_ids(db, current_user)
    if form.site_id is not None and allowed is not None and form.site_id not in allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="فرم یافت نشد")
    return form


@router.post("", response_model=EvaluationFormOut)
async def create_form(
    payload: EvaluationFormIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ایجاد فرم جدید (draft)؛ نیازمند مجوز performance.forms.manage روی سایت فرم."""
    await require_site_permission(db, current_user, payload.site_id, PERMISSION_CODE)
    return await EvaluationFormService(db).create_form(payload.model_dump(), current_user.id)


@router.put("/{form_id}", response_model=EvaluationFormOut)
async def update_form(
    form_id: int,
    payload: EvaluationFormIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ویرایش مشخصات فرم؛ نیازمند مجوز مدیریت فرم. خطاها: 404 فرم یافت نشد، 400 اگر فرم draft نباشد."""
    await _require_form_permission(db, current_user, form_id)
    try:
        return await EvaluationFormService(db).update_form(form_id, payload.model_dump())
    except EvaluationFormError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{form_id}/status", response_model=EvaluationFormOut)
async def update_form_status(
    form_id: int,
    payload: EvaluationPeriodStatusUpdate,  # فقط یک فیلد status دارد؛ برای فرم هم استفاده می‌شود
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    تغییر وضعیت فرم (مثلاً فعال‌سازی که مجموع وزن‌ها را بررسی می‌کند)؛ نیازمند مجوز مدیریت فرم.
    خطاها: 404 فرم یافت نشد، 400 وضعیت نامعتبر یا فرم ناقص.
    """
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
    """تغییر عنوان فرم؛ برخلاف ویرایش کامل، در هر وضعیتی مجاز است. نیازمند مجوز مدیریت فرم؛ 404/400."""
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
    """ساخت نسخه جدید (کپی کامل) از فرم و برگرداندن آن؛ نیازمند مجوز مدیریت فرم؛ 404/400."""
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
    """حذف فرم؛ نیازمند مجوز مدیریت فرم. 400 اگر فرم draft نباشد (باید بایگانی شود). فرم ناموجود: 204 بی‌اثر."""
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
    """افزودن دسته‌بندی به فرم؛ نیازمند مجوز مدیریت فرم؛ 404 فرم یافت نشد، 400 خطای اعتبارسنجی."""
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
    """ویرایش دسته‌بندی؛ نیازمند مجوز مدیریت فرم والد؛ 404 دسته‌بندی یافت نشد، 400 خطای اعتبارسنجی."""
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
    """حذف دسته‌بندی همراه سوالاتش؛ نیازمند مجوز مدیریت فرم والد؛ 400 اگر فرم draft نباشد. ناموجود: 204 بی‌اثر."""
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
    """افزودن سوال همراه گزینه‌ها به دسته‌بندی؛ نیازمند مجوز مدیریت فرم؛ 404/400."""
    await _require_category_permission(db, current_user, category_id)
    # گزینه‌ها جدا از فیلدهای سوال به سرویس داده می‌شوند
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
    """ویرایش سوال و جایگزینی گزینه‌هایش؛ نیازمند مجوز مدیریت فرم؛ 404/400."""
    await _require_question_permission(db, current_user, question_id)
    # گزینه‌ها جدا از فیلدهای سوال به سرویس داده می‌شوند
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
    """حذف سوال همراه گزینه‌هایش؛ نیازمند مجوز مدیریت فرم. سوال ناموجود: 204 بی‌اثر."""
    question = await db.get(EvaluationQuestion, question_id)
    if question is None:
        return
    await _require_category_permission(db, current_user, question.category_id)
    await EvaluationFormService(db).delete_question(question_id)
