"""
Endpoint های ماژول «بیمه تکمیلی» (بازسازی سامانه insurance.faipco.ir داخل پرتال).

پرسنل (بدون مجوز - مثل درخواست مرخصی):
  GET    /insurance/me                    وضعیت + فرم (اطلاعات پرسنل، ثبت‌نام قبلی، نرخ‌ها، توضیحات)
  PUT    /insurance/me                    ثبت / ویرایش ثبت‌نام (جایگزینی کامل)
  POST   /insurance/me/documents          آپلود مدرک کفالت (قبل از ثبت نهایی)
  DELETE /insurance/me/documents/{id}     حذف مدرک خودم
  GET    /insurance/documents/{id}        دانلود مدرک (صاحبش یا insurance.view)

مدیریت (insurance.view / insurance.manage):
  GET    /insurance/settings              تنظیمات (بدون احراز هویت لازم نیست - فقط مدیریت)
  PUT    /insurance/settings              فعال/غیرفعال، جدول نرخ، توضیحات
  GET    /insurance/registrations         فهرست (جستجو/صفحه‌بندی، محدود به سایت‌های مجاز)
  GET    /insurance/registrations/{id}    جزئیات + اعضا + مدارک
  DELETE /insurance/registrations/{id}    حذف (insurance.manage)
  GET    /insurance/export                خروجی Excel (۲۹ ستون سامانه قدیمی)
"""
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.employee import Employee
from app.models.user import User
from app.schemas.insurance import (
    InsuranceDocumentOut,
    InsuranceListOut,
    InsuranceMyStatusOut,
    InsuranceRegistrationIn,
    InsuranceRegistrationOut,
    InsuranceSettingsIn,
    InsuranceSettingsOut,
)
from app.services.insurance_service import InsuranceDisabledError, InsuranceError, InsuranceService

router = APIRouter()


async def _require_employee(db: AsyncSession, current_user: User) -> Employee:
    if current_user.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="این قابلیت فقط برای حساب‌های متصل به پرسنل در دسترس است"
        )
    employee = await db.get(Employee, current_user.employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل موردنظر یافت نشد")
    return employee


# ---------- پرسنل ----------


@router.get("/me", response_model=InsuranceMyStatusOut)
async def my_insurance(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await db.get(Employee, current_user.employee_id) if current_user.employee_id else None
    return await InsuranceService(db).my_status(employee)


@router.put("/me", response_model=InsuranceRegistrationOut)
async def save_my_insurance(
    payload: InsuranceRegistrationIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = await _require_employee(db, current_user)
    try:
        return await InsuranceService(db).save(employee, payload)
    except InsuranceDisabledError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (InsuranceError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/me/documents", response_model=InsuranceDocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_my_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = await _require_employee(db, current_user)
    content = await file.read()
    try:
        return await InsuranceService(db).upload_document(employee, file.filename or "", file.content_type or "", content)
    except InsuranceDisabledError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except InsuranceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/me/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_document(
    document_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    employee = await _require_employee(db, current_user)
    if not await InsuranceService(db).delete_own_document(document_id, employee.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مدرک یافت نشد")


@router.get("/documents/{document_id}")
async def download_document(
    document_id: int,
    inline: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # صاحب مدرک همیشه؛ دارندگان insurance.view / insurance.manage (در هر سایتی) هم
    can_view_all = current_user.is_superuser
    if not can_view_all:
        for code in ("insurance.view", "insurance.manage"):
            sites = await get_sites_with_permission(db, current_user, code)
            if sites is None or sites:
                can_view_all = True
                break
    doc = await InsuranceService(db).get_document_for_download(document_id, current_user.employee_id, can_view_all)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مدرک یافت نشد")
    disposition = "inline" if inline else "attachment"
    safe_name = doc.file_name.encode("ascii", "ignore").decode() or f"document-{doc.id}"
    return Response(
        content=doc.data,
        media_type=doc.content_type,
        headers={
            "Content-Disposition": f"{disposition}; filename=\"{safe_name}\"; filename*=UTF-8''{_url_quote(doc.file_name)}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )


def _url_quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value)


# ---------- مدیریت ----------


@router.get("/settings", response_model=InsuranceSettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db), _user=Depends(require_permission("insurance.manage"))):
    return await InsuranceService(db).get_settings()


@router.put("/settings", response_model=InsuranceSettingsOut)
async def update_settings(
    payload: InsuranceSettingsIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("insurance.manage")),
):
    try:
        return await InsuranceService(db).update_settings(payload.model_dump(exclude_unset=True))
    except InsuranceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def _accessible_sites(db: AsyncSession, user: User) -> set[int] | None:
    """سایت‌های مجاز برای فهرست/خروجی - insurance.view یا insurance.manage (ایزوله‌سازی چندسایتی)."""
    view_sites = await get_sites_with_permission(db, user, "insurance.view")
    manage_sites = await get_sites_with_permission(db, user, "insurance.manage")
    if view_sites is None or manage_sites is None:
        return None
    sites = view_sites | manage_sites
    if not sites:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="اجازه مشاهده ثبت‌نام‌های بیمه را ندارید")
    return sites


@router.get("/registrations", response_model=InsuranceListOut)
async def list_registrations(
    search: str | None = None,
    site_id: int | None = None,
    page: int = 1,
    page_size: int = 25,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sites = await _accessible_sites(db, current_user)
    if site_id is not None:
        sites = {site_id} if sites is None else (sites & {site_id})
    page_size = min(max(page_size, 1), 200)
    return await InsuranceService(db).list_registrations(sites, search, max(page, 1), page_size)


@router.get("/registrations/{registration_id}", response_model=InsuranceRegistrationOut)
async def get_registration(
    registration_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    sites = await _accessible_sites(db, current_user)
    registration = await InsuranceService(db).get_registration_by_id(registration_id, sites)
    if registration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ثبت‌نام یافت نشد")
    return registration


@router.delete("/registrations/{registration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_registration(
    registration_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("insurance.manage")),
):
    sites = await get_sites_with_permission(db, current_user, "insurance.manage")
    registration = await InsuranceService(db).get_registration_by_id(registration_id, sites)
    if registration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ثبت‌نام یافت نشد")
    await InsuranceService(db).delete_registration(registration.employee_id)


@router.get("/export")
async def export_registrations(
    site_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sites = await _accessible_sites(db, current_user)
    if site_id is not None:
        sites = {site_id} if sites is None else (sites & {site_id})
    content = await InsuranceService(db).export_xlsx(sites)
    filename = f"insurance_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
