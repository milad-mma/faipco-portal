"""
Endpoint های ماژول «بیمه تکمیلی» (پیشوند /insurance).

پرسنل (هر کاربر واردشده که به پرسنلی متصل است):
  GET    /insurance/me                    وضعیت + داده‌ی فرم (اطلاعات پرسنل، ثبت‌نام قبلی، نرخ‌ها، نکات)
  PUT    /insurance/me                    ثبت / ویرایش ثبت‌نام (جایگزینی کامل اعضا)
  POST   /insurance/me/documents          آپلود مدرک کفالت (قبل از ثبت نهایی)
  DELETE /insurance/me/documents/{id}     حذف مدرک خودم
  GET    /insurance/documents/{id}        دانلود مدرک (صاحب مدرک یا دارنده‌ی insurance.view)

مدیریت (مجوز insurance.view برای مشاهده، insurance.manage برای تغییر):
  GET    /insurance/settings              خواندن تنظیمات ماژول
  PUT    /insurance/settings              فعال/غیرفعال، جدول نرخ، نکات
  GET    /insurance/registrations         فهرست (جستجو/صفحه‌بندی، محدود به سایت‌های مجاز)
  GET    /insurance/registrations/{id}    جزئیات + اعضا + مدارک
  DELETE /insurance/registrations/{id}    حذف ثبت‌نام
  GET    /insurance/export                خروجی Excel

منطق اصلی در services/insurance_service.py است؛ اینجا فقط احراز هویت، تعیین
سایت‌های مجاز و تبدیل خطاهای سرویس به کد HTTP انجام می‌شود.
"""
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile, status
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
    InsuranceRejectDocumentIn,
    InsuranceRejectDocumentOut,
    InsuranceSettingsIn,
    InsuranceSettingsOut,
)
from app.services.insurance_service import InsuranceDisabledError, InsuranceError, InsuranceService
from app.services.notice_service import send_publish_notifications

router = APIRouter()


async def _require_employee(db: AsyncSession, current_user: User) -> Employee:
    """
    رکورد پرسنل متصل به کاربر جاری را برمی‌گرداند.
    اگر کاربر به پرسنلی وصل نباشد 400 و اگر رکورد پرسنل پیدا نشود 404 می‌دهد.
    """
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
    """داده‌ی کامل صفحه‌ی بیمه برای کاربر جاری (کاربر بدون پرسنل هم پاسخ می‌گیرد، با employee=null)."""
    employee = await db.get(Employee, current_user.employee_id) if current_user.employee_id else None
    return await InsuranceService(db).my_status(employee)


@router.put("/me", response_model=InsuranceRegistrationOut)
async def save_my_insurance(
    payload: InsuranceRegistrationIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """فرم ثبت‌نام را ذخیره می‌کند؛ ماژول غیرفعال → 403، خطای اعتبارسنجی → 400."""
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
    """یک فایل مدرک (multipart) را برای پرسنل جاری ذخیره می‌کند و رکورد مدرک را برمی‌گرداند."""
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
    """مدرک متعلق به پرسنل جاری را حذف می‌کند؛ اگر مدرک مال او نباشد 404."""
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
    """
    بایت‌های مدرک را با MIME واقعی آن برمی‌گرداند.
    inline=true برای نمایش در مرورگر (پیش‌نمایش)، وگرنه دانلود.
    دسترسی: صاحب مدرک، مدیر کل، یا کسی که insurance.view/manage در حداقل یک سایت دارد.
    """
    # تعیین اینکه کاربر حق دیدن مدارک همه را دارد یا فقط مدارک خودش
    can_view_all = current_user.is_superuser
    if not can_view_all:
        for code in ("insurance.view", "insurance.manage"):
            sites = await get_sites_with_permission(db, current_user, code)
            if sites is None or sites:  # None = همه سایت‌ها، مجموعه غیرخالی = حداقل یک سایت
                can_view_all = True
                break
    doc = await InsuranceService(db).get_document_for_download(document_id, current_user.employee_id, can_view_all)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مدرک یافت نشد")
    disposition = "inline" if inline else "attachment"
    # نام ASCII برای مرورگرهای قدیمی؛ نام کامل UTF-8 در filename*
    safe_name = doc.file_name.encode("ascii", "ignore").decode() or f"document-{doc.id}"
    return Response(
        content=doc.data,
        media_type=doc.content_type,
        headers={
            "Content-Disposition": f"{disposition}; filename=\"{safe_name}\"; filename*=UTF-8''{_url_quote(doc.file_name)}",
            "X-Content-Type-Options": "nosniff",  # مرورگر نوع فایل را حدس نزند
            "Content-Security-Policy": "sandbox",  # اجرای اسکریپت داخل PDF/SVG نمایش‌داده‌شده مسدود شود
        },
    )


def _url_quote(value: str) -> str:
    """رشته را برای استفاده در هدر filename* درصدی (percent-encoding) می‌کند."""
    from urllib.parse import quote

    return quote(value)


# ---------- مدیریت ----------


@router.get("/settings", response_model=InsuranceSettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db), _user=Depends(require_permission("insurance.manage"))):
    """تنظیمات ماژول (فعال بودن، جدول نرخ، نکات) برای صفحه‌ی مدیریت."""
    return await InsuranceService(db).get_settings()


@router.put("/settings", response_model=InsuranceSettingsOut)
async def update_settings(
    payload: InsuranceSettingsIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("insurance.manage")),
):
    """فقط فیلدهای ارسال‌شده در بدنه را تغییر می‌دهد و تنظیمات کامل جدید را برمی‌گرداند."""
    try:
        return await InsuranceService(db).update_settings(payload.model_dump(exclude_unset=True))
    except InsuranceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def _accessible_sites(db: AsyncSession, user: User) -> set[int] | None:
    """
    مجموعه سایت‌هایی که کاربر در آن‌ها insurance.view یا insurance.manage دارد.
    None یعنی همه‌ی سایت‌ها (مدیر کل یا مجوز سراسری)؛ مجموعه خالی → 403.
    """
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
    member_filter: str | None = None,
    page: int = 1,
    page_size: int = 25,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    فهرست ثبت‌نام‌ها با جستجو و صفحه‌بندی، محدود به سایت‌های مجاز و فیلتر اختیاری site_id.
    member_filter: non_dependent (دارای عضو غیر تحت کفالت) / with_documents / rejected (مدرک ردشده).
    """
    sites = await _accessible_sites(db, current_user)
    # فیلتر سایت درخواستی فقط داخل سایت‌های مجاز اعمال می‌شود
    if site_id is not None:
        sites = {site_id} if sites is None else (sites & {site_id})
    page_size = min(max(page_size, 1), 200)  # اندازه صفحه بین ۱ تا ۲۰۰
    return await InsuranceService(db).list_registrations(sites, search, max(page, 1), page_size, member_filter)


@router.get("/registrations/{registration_id}", response_model=InsuranceRegistrationOut)
async def get_registration(
    registration_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """جزئیات یک ثبت‌نام با اعضا و مدارک؛ خارج از سایت‌های مجاز → 404."""
    sites = await _accessible_sites(db, current_user)
    registration = await InsuranceService(db).get_registration_by_id(registration_id, sites)
    if registration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ثبت‌نام یافت نشد")
    return registration


@router.post(
    "/registrations/{registration_id}/members/{member_id}/reject-document",
    response_model=InsuranceRejectDocumentOut,
)
async def reject_member_document(
    registration_id: int,
    member_id: int,
    background_tasks: BackgroundTasks,
    payload: InsuranceRejectDocumentIn | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("insurance.manage")),
):
    """
    مدرک کفالت یک عضو را رد می‌کند: فایل حذف و اطلاعیه («مدرک ارائه‌شده برای ... مورد تأیید نیست») همراه
    Push برای ثبت‌نام‌کننده فرستاده می‌شود. مجوز: insurance.manage برای سایت آن پرسنل.
    خطاها: 404 ثبت‌نام/عضو یافت نشد یا خارج از سایت‌ها، 400 عضو مدرک ندارد.
    """
    sites = await get_sites_with_permission(db, current_user, "insurance.manage")
    try:
        result = await InsuranceService(db).reject_document(
            registration_id,
            member_id,
            sites,
            current_user,
            title=payload.title if payload else None,
            body=payload.body if payload else None,
        )
    except InsuranceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ثبت‌نام یا عضو یافت نشد")
    member_name, notice_id = result
    background_tasks.add_task(send_publish_notifications, notice_id)  # Push بعد از پاسخ
    return InsuranceRejectDocumentOut(member_name=member_name, notice_id=notice_id)


@router.delete("/registrations/{registration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_registration(
    registration_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("insurance.manage")),
):
    """ثبت‌نام را با همه‌ی اعضا و مدارکش حذف می‌کند (فقط در سایت‌هایی که insurance.manage دارد)."""
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
    """فایل Excel ثبت‌نام‌های سایت‌های مجاز را با نام زمان‌دار برای دانلود برمی‌گرداند."""
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
