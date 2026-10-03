"""
Endpoint های ماژول «مشخصات خانوادگی» (پیشوند /family).

پرسنل:
  GET    /family/me                          فرم + پرونده‌ی جاری + تنظیمات فیلدها/مدارک
  PUT    /family/me                          ثبت/ویرایش فرم (جایگزینی کامل؛ وضعیت ← در انتظار بررسی)
  POST   /family/me/documents                آپلود مدرک (multipart: file + doc_type)
  DELETE /family/me/documents/{id}           حذف مدرکی که هنوز در فرم ثبت نشده
  GET    /family/documents/{id}              دانلود مدرک (صاحب مدرک یا دارنده‌ی family.view/manage سایت)

منابع انسانی (family.view برای مشاهده، family.manage برای تغییر؛ محدود به سایت‌های مجاز):
  GET    /family/settings | PUT /family/settings     تنظیمات فیلدها، مدارک، قواعد شمول و هشدارها
  GET    /family/profiles                            فهرست پرسنل با شمول محاسبه‌شده
  GET    /family/profiles/{id}                       جزئیات + شمول نسخه‌ی جاری/تأییدشده + تاریخچه
  POST   /family/profiles/{id}/approve               تأیید (با تاریخ اثر)
  POST   /family/profiles/{id}/reject                رد (با دلیل)
  POST   /family/profiles/{id}/return                بازگشت برای ویرایش (حتی پرونده‌ی قفل)
  PUT    /family/employees/{employee_id}/hr-fields   سابقه‌ی قبلی / کل سابقه بیمه و یادداشت داخلی
  POST   /family/insurance-days/import               ورود گروهی سابقه بیمه از Excel (mode=prior|total)
  GET    /family/export                              خروجی Excel
"""
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import family_rules as rules
from app.core.deps import get_current_user, require_permission
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.employee import Employee
from app.models.user import User
from app.schemas.family import (
    FamilyApproveIn,
    FamilyDetailOut,
    FamilyDocumentOut,
    FamilyHrFieldsIn,
    FamilyListOut,
    FamilyMyStatusOut,
    FamilyProfileIn,
    FamilyProfileOut,
    FamilyReviewNoteIn,
    FamilySettingsIn,
)
from app.services.family_service import FamilyError, FamilyForbiddenError, FamilyService, today_jalali
from app.services.notice_service import send_publish_notifications

router = APIRouter()


async def _require_employee(db: AsyncSession, user: User) -> Employee:
    if user.employee_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="این قابلیت فقط برای حساب‌های متصل به پرسنل در دسترس است")
    employee = await db.get(Employee, user.employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل موردنظر یافت نشد")
    return employee


def _raise(e: FamilyError):
    code = status.HTTP_403_FORBIDDEN if isinstance(e, FamilyForbiddenError) else status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=str(e))


def _as_of(value: str | None) -> tuple[int, int, int]:
    if not value:
        return today_jalali()
    parsed = rules.parse_jalali(value)
    if parsed is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="تاریخ مبنا نامعتبر است")
    return parsed


# ---------- پرسنل ----------


@router.get("/me", response_model=FamilyMyStatusOut)
async def my_family(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await db.get(Employee, current_user.employee_id) if current_user.employee_id else None
    return await FamilyService(db).my_status(employee)


@router.put("/me", response_model=FamilyProfileOut)
async def save_my_family(
    payload: FamilyProfileIn, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    employee = await _require_employee(db, current_user)
    try:
        return await FamilyService(db).save(employee, payload.model_dump(), current_user)
    except FamilyError as e:
        _raise(e)


@router.post("/me/documents", response_model=FamilyDocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_my_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = await _require_employee(db, current_user)
    content = await file.read()
    try:
        return await FamilyService(db).upload_document(employee, doc_type, file.filename or "", content)
    except FamilyError as e:
        _raise(e)


@router.delete("/me/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_document(document_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _require_employee(db, current_user)
    try:
        deleted = await FamilyService(db).delete_own_document(document_id, employee)
    except FamilyError as e:
        _raise(e)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مدرک یافت نشد")


async def _union_sites(db: AsyncSession, user: User) -> set[int] | None:
    view_sites = await get_sites_with_permission(db, user, "family.view")
    manage_sites = await get_sites_with_permission(db, user, "family.manage")
    if view_sites is None or manage_sites is None:
        return None
    return view_sites | manage_sites


@router.get("/documents/{document_id}")
async def download_document(
    document_id: int,
    inline: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed = await _union_sites(db, current_user)
    doc = await FamilyService(db).get_document_for_download(document_id, current_user.employee_id, allowed)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مدرک یافت نشد")
    safe_name = doc.file_name.encode("ascii", "ignore").decode() or f"document-{doc.id}"
    return Response(
        content=doc.data,
        media_type=doc.content_type,
        headers={
            "Content-Disposition": f"{'inline' if inline else 'attachment'}; filename=\"{safe_name}\"; filename*=UTF-8''{quote(doc.file_name)}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )


# ---------- منابع انسانی ----------


async def _view_sites(db: AsyncSession, user: User) -> set[int] | None:
    sites = await _union_sites(db, user)
    if sites is not None and not sites:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="اجازه مشاهده مشخصات خانوادگی پرسنل را ندارید")
    return sites


async def _manage_sites(db: AsyncSession, user: User) -> set[int] | None:
    sites = await get_sites_with_permission(db, user, "family.manage")
    if sites is not None and not sites:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="اجازه مدیریت مشخصات خانوادگی را ندارید")
    return sites


@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """تنظیمات کامل + تعریف فیلدها/مدارک/گزینه‌ها؛ برای دارندگان family.view (فقط‌خواندنی) و family.manage."""
    await _view_sites(db, current_user)
    service = FamilyService(db)
    return {"settings": await service.get_settings(), "meta": service.settings_meta()}


@router.put("/settings")
async def update_settings(
    payload: FamilySettingsIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("family.manage")),
):
    service = FamilyService(db)
    return {"settings": await service.update_settings(payload.model_dump(exclude_unset=True)), "meta": service.settings_meta()}


@router.get("/profiles", response_model=FamilyListOut)
async def list_profiles(
    search: str | None = None,
    site_id: int | None = None,
    status_filter: str | None = None,
    flag: str | None = None,
    as_of: str | None = None,
    page: int = 1,
    page_size: int = 25,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sites = await _view_sites(db, current_user)
    if site_id is not None:
        sites = {site_id} if sites is None else (sites & {site_id})
    page_size = min(max(page_size, 1), 200)
    return await FamilyService(db).list_profiles(sites, search, status_filter, flag, max(page, 1), page_size, _as_of(as_of))


@router.get("/profiles/{profile_id}", response_model=FamilyDetailOut)
async def get_profile(
    profile_id: int, as_of: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    sites = await _view_sites(db, current_user)
    detail = await FamilyService(db).detail(profile_id, sites, _as_of(as_of))
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرونده یافت نشد")
    return detail


@router.post("/profiles/{profile_id}/approve")
async def approve_profile(
    profile_id: int,
    payload: FamilyApproveIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sites = await _manage_sites(db, current_user)
    try:
        notice_id = await FamilyService(db).approve(profile_id, sites, current_user, payload.effective_date, payload.note)
    except FamilyError as e:
        _raise(e)
    if notice_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرونده یافت نشد")
    background_tasks.add_task(send_publish_notifications, notice_id)
    return {"ok": True}


async def _reject_or_return(profile_id, payload, background_tasks, db, user, action):
    sites = await _manage_sites(db, user)
    try:
        notice_id = await FamilyService(db).reject(profile_id, sites, user, payload.note, action)
    except FamilyError as e:
        _raise(e)
    if notice_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرونده یافت نشد")
    background_tasks.add_task(send_publish_notifications, notice_id)
    return {"ok": True}


@router.post("/profiles/{profile_id}/reject")
async def reject_profile(
    profile_id: int,
    payload: FamilyReviewNoteIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _reject_or_return(profile_id, payload, background_tasks, db, current_user, "rejected")


@router.post("/profiles/{profile_id}/return")
async def return_profile(
    profile_id: int,
    payload: FamilyReviewNoteIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _reject_or_return(profile_id, payload, background_tasks, db, current_user, "returned")


@router.put("/employees/{employee_id}/hr-fields")
async def update_hr_fields(
    employee_id: int,
    payload: FamilyHrFieldsIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sites = await _manage_sites(db, current_user)
    result = await FamilyService(db).update_hr_fields(employee_id, sites, current_user, payload.model_dump(exclude_unset=True))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    return result


@router.post("/insurance-days/import")
async def import_insurance_days(
    file: UploadFile = File(...),
    mode: str = Form("prior"),
    site_id: int | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ورود گروهی سابقه بیمه از Excel (ستون «کد پرسنلی» و ستون «سابقه (روز)»).
    mode=prior: سابقه‌ی پیش از استخدام (با روزهای پس از استخدام جمع می‌شود)؛ mode=total: کل سابقه.
    """
    sites = await _manage_sites(db, current_user)
    if site_id is not None and sites is not None and site_id not in sites:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="به این سایت دسترسی ندارید")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="حجم فایل نباید بیشتر از ۵ مگابایت باشد.")
    try:
        return await FamilyService(db).import_insurance_days(sites, current_user, content, mode, site_id)
    except FamilyError as e:
        _raise(e)


@router.get("/export")
async def export_profiles(
    site_id: int | None = None,
    as_of: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sites = await _view_sites(db, current_user)
    if site_id is not None:
        sites = {site_id} if sites is None else (sites & {site_id})
    content = await FamilyService(db).export_xlsx(sites, _as_of(as_of))
    filename = f"family_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
