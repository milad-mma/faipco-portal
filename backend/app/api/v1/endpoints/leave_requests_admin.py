"""
Endpoint های مدیریتی «درخواست مرخصی/ماموریت» (پیشوند /leave-requests-admin).

    - تنظیمات ادمین سایت (نگاشت کاراوب، نوع‌ها، فهرست‌های مرجع، تأییدکننده واحد، مسئول نیروی
      انسانی، وضعیت ماژول): مجوز sites.manage روی همان سایت
    - گزارش همه درخواست‌های یک سایت و خروجی Excel: leave_requests.view یا leave_requests.manage،
      یا مجوز به‌تفکیک نوع (leave_requests.view.type.<عنوان>) با محدودیت‌های خاص
    - ویرایش/حذف مدیریتی یک درخواست: فقط leave_requests.manage
خطاهای منطقی سرویس‌ها به 400 و نبود مجوز به 403 تبدیل می‌شوند.
"""
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_access import get_sites_with_permission, get_sites_with_permission_prefix
from app.core.site_permission_deps import require_site_permission
from app.db.session import get_db
from app.models.employee import Department, Employee
from app.models.leave_request import LeaveRequestType
from app.models.site import Site
from app.models.user import User
from app.schemas.leave_request import (
    ActionLookupItemOut,
    AdminUpdateRequestIn,
    CardLookupItemOut,
    LeaveRequestApproverOut,
    LeaveRequestHrOfficerOut,
    LeaveRequestMappingIn,
    LeaveRequestMappingOut,
    LeaveRequestModuleStatusOut,
    LeaveRequestOut,
    LeaveRequestTypeIn,
    LeaveRequestTypeOut,
    LeaveRequestTypeUpdateIn,
    OperationLookupItemOut,
    SetApproverIn,
    SetHrOfficerIn,
    SetModuleDisabledIn,
)
from app.services.kara_schema import ATTENDANCE_SCHEMA_DEFAULTS, LEAVE_SCHEMA_DEFAULTS
from app.services.leave_request_service import LeaveRequestError, LeaveRequestService
from app.services.leave_request_xlsx import build_leave_requests_xlsx
from app.services.leave_request_structure_service import (
    LeaveRequestStructureError,
    LeaveRequestStructureService,
    permission_code_for_type_title,
)

router = APIRouter()
logger = logging.getLogger(__name__)

SITES_MANAGE = "sites.manage"  # مجوز لازم برای همه‌ی endpoint های تنظیمات سایت


@router.get("/sites/{site_id}/mapping", response_model=LeaveRequestMappingOut | None)
async def get_mapping(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """نگاشت کاراوب یک سایت (null اگر تنظیم نشده). مجوز: sites.manage."""
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    return await LeaveRequestStructureService(db).get_mapping(site_id)


@router.get("/kara-schema-defaults")
async def get_kara_schema_defaults(current_user: User = Depends(get_current_user)):
    """
    نام‌های پیش‌فرض جدول/ستون‌های کاراوب برای تردد و مرخصی/ماموریت.
    فقط برای دکمه «پر کردن با نام‌های کاراوب» در فرم نگاشت؛ هر کاربر واردشده می‌تواند بخواند.
    """
    return {"attendance": ATTENDANCE_SCHEMA_DEFAULTS, "leave": LEAVE_SCHEMA_DEFAULTS}


@router.put("/sites/{site_id}/mapping", response_model=LeaveRequestMappingOut)
async def upsert_mapping(
    site_id: int,
    payload: LeaveRequestMappingIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ساخت یا به‌روزرسانی نگاشت کاراوب سایت (اولین ساخت، نوع‌های پیش‌فرض را هم می‌سازد). مجوز: sites.manage."""
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    return await LeaveRequestStructureService(db).upsert_mapping(site_id, payload.model_dump())


@router.delete("/sites/{site_id}/mapping", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mapping(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """حذف نگاشت سایت (ماژول برای سایت غیرفعال می‌شود). مجوز: sites.manage."""
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    await LeaveRequestStructureService(db).delete_mapping(site_id)


@router.get("/sites/{site_id}/action-lookup", response_model=list[ActionLookupItemOut])
async def get_action_lookup(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    فهرست WF_Action کاراوب (ActionId + عنوان فارسی) برای فهرست کمکی فرم «افزودن نوع درخواست».
    مجوز: sites.manage. 400 اگر نگاشت یا اتصال کاراوب سایت مشکل داشته باشد.
    """
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    try:
        return await LeaveRequestService(db).list_action_lookup(site_id)
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/sites/{site_id}/operation-lookup", response_model=list[OperationLookupItemOut])
async def get_operation_lookup(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """فهرست WF_OperationTypes کاراوب (OperationId + عنوان) برای فرم «افزودن نوع درخواست». مجوز: sites.manage."""
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    try:
        return await LeaveRequestService(db).list_operation_lookup(site_id)
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/sites/{site_id}/card-lookup", response_model=list[CardLookupItemOut])
async def get_card_lookup(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """فهرست کارت‌های کاراوب (Card_No + عنوان + ActionId کارت) برای فرم «افزودن نوع درخواست». مجوز: sites.manage."""
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    try:
        return await LeaveRequestService(db).list_card_lookup(site_id)
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/sites/{site_id}/types", response_model=list[LeaveRequestTypeOut])
async def list_types(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    همه نوع‌های درخواست یک سایت (فعال و غیرفعال).
    مجوز: sites.manage یا leave_requests.manage (منابع انسانی برای فیلتر/ویرایش نوع در صفحه گزارش به آن نیاز دارد).
    """
    # دارنده leave_requests.manage روی این سایت (یا سراسری) بدون sites.manage هم می‌تواند بخواند
    if not current_user.is_superuser:
        manage_sites = await get_sites_with_permission(db, current_user, "leave_requests.manage")
        has_leave_manage = manage_sites is None or site_id in manage_sites  # None = مجوز سراسری
        if not has_leave_manage:
            await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    return await LeaveRequestStructureService(db).list_types(site_id)


@router.post("/sites/{site_id}/types", response_model=LeaveRequestTypeOut)
async def add_type(
    site_id: int,
    payload: LeaveRequestTypeIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ساخت یک نوع درخواست جدید برای سایت (مجوز مشاهده‌ی عنوانش هم ساخته می‌شود). مجوز: sites.manage."""
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    return await LeaveRequestStructureService(db).add_type(
        site_id, payload.title, payload.is_mission, payload.is_hourly, payload.action_id, payload.operation_id, payload.card_no,
        payload.is_forgotten_punch,
    )


@router.put("/types/{type_id}", response_model=LeaveRequestTypeOut)
async def update_type(
    type_id: int,
    payload: LeaveRequestTypeUpdateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ویرایش جزئی یک نوع درخواست (فقط فیلدهای غیر None). مجوز: sites.manage روی سایتِ نوع. 404 اگر نوع نباشد."""
    # سایت از روی خودِ نوع تعیین می‌شود چون مسیر site_id ندارد
    leave_type = await db.get(LeaveRequestType, type_id)
    if leave_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="نوع درخواست موردنظر یافت نشد")
    await require_site_permission(db, current_user, leave_type.site_id, SITES_MANAGE)
    try:
        return await LeaveRequestStructureService(db).update_type(
            type_id, {k: v for k, v in payload.model_dump().items() if v is not None}  # فیلدهای خالی اعمال نمی‌شوند
        )
    except LeaveRequestStructureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_type(
    type_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """حذف یک نوع درخواست (نوع ناموجود بی‌صدا 204 می‌دهد). مجوز: sites.manage روی سایتِ نوع."""
    leave_type = await db.get(LeaveRequestType, type_id)
    if leave_type is None:
        return
    await require_site_permission(db, current_user, leave_type.site_id, SITES_MANAGE)
    await LeaveRequestStructureService(db).delete_type(type_id)


@router.get("/sites/{site_id}/approvers", response_model=list[LeaveRequestApproverOut])
async def list_approvers(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """تأییدکننده‌های دستی واحدهای یک سایت. مجوز: sites.manage."""
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    return await LeaveRequestStructureService(db).list_approvers(site_id)


@router.put("/departments/{department_id}/approver", response_model=LeaveRequestApproverOut)
async def set_approver(
    department_id: int,
    payload: SetApproverIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    تعیین/جایگزینی تأییدکننده دستی یک واحد. مجوز: sites.manage روی سایتِ واحد، و اگر تأییدکننده از پرسنل
    سایت دیگری است روی سایت او هم. 404 اگر واحد نباشد، 403 سایت غیرمجاز، 400 اگر پرسنل نباشد.
    """
    # سایت از روی واحد تعیین می‌شود چون مسیر site_id ندارد
    department = await db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="واحد سازمانی موردنظر یافت نشد")
    await require_site_permission(db, current_user, department.site_id, SITES_MANAGE)
    approver = await db.get(Employee, payload.approver_employee_id)
    if approver is not None and approver.site_id != department.site_id:
        await require_site_permission(db, current_user, approver.site_id, SITES_MANAGE)
    try:
        return await LeaveRequestStructureService(db).set_approver(department_id, payload.approver_employee_id)
    except LeaveRequestStructureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/departments/{department_id}/approver", status_code=status.HTTP_204_NO_CONTENT)
async def remove_approver(
    department_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """حذف تأییدکننده دستی یک واحد (واحد ناموجود بی‌صدا 204 می‌دهد). مجوز: sites.manage روی سایتِ واحد."""
    department = await db.get(Department, department_id)
    if department is None:
        return
    await require_site_permission(db, current_user, department.site_id, SITES_MANAGE)
    await LeaveRequestStructureService(db).remove_approver(department_id)


@router.get("/sites/{site_id}/module-status", response_model=LeaveRequestModuleStatusOut)
async def get_module_status(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """وضعیت ماژول برای سایت: نگاشت دارد؟ از پنل غیرفعال شده؟ مجوز: sites.manage."""
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    return await LeaveRequestStructureService(db).get_module_status(site_id)


@router.put("/sites/{site_id}/module-status", response_model=LeaveRequestModuleStatusOut)
async def set_module_status(
    site_id: int,
    payload: SetModuleDisabledIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """فعال/غیرفعال‌کردن موقت ماژول برای سایت. مجوز: sites.manage. 400 اگر سایت نگاشت نداشته باشد."""
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    try:
        return await LeaveRequestStructureService(db).set_module_disabled(site_id, payload.is_disabled)
    except LeaveRequestStructureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/sites/{site_id}/hr-officer", response_model=LeaveRequestHrOfficerOut | None)
async def get_hr_officer(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """مسئول نیروی انسانی سایت (تأییدکننده نهایی «تردد فراموش‌شده»)؛ null اگر تعیین نشده. مجوز: sites.manage."""
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    return await LeaveRequestStructureService(db).get_hr_officer(site_id)


@router.put("/sites/{site_id}/hr-officer", response_model=LeaveRequestHrOfficerOut)
async def set_hr_officer(
    site_id: int,
    payload: SetHrOfficerIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """تعیین/جایگزینی مسئول نیروی انسانی سایت. مجوز: sites.manage. 400 اگر پرسنل از این سایت نباشد یا کد پرسنلی عددی نداشته باشد."""
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    try:
        return await LeaveRequestStructureService(db).set_hr_officer(site_id, payload.employee_id)
    except LeaveRequestStructureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/sites/{site_id}/hr-officer", status_code=status.HTTP_204_NO_CONTENT)
async def remove_hr_officer(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """حذف مسئول نیروی انسانی سایت. مجوز: sites.manage."""
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    await LeaveRequestStructureService(db).remove_hr_officer(site_id)


# ---------- مشاهده/ویرایش مدیریتی (حراست/منابع انسانی) ----------


async def _get_view_access(db: AsyncSession, user: User, site_id: int) -> list | None:
    """
    سطح دسترسی کاربر به گزارش درخواست‌های یک سایت را تعیین می‌کند.
    خروجی: None = دسترسی کامل (superuser یا leave_requests.view/manage روی سایت)؛
    لیست شناسه نوع = فقط همین نوع‌ها (مجوزهای leave_requests.view.type.<عنوان>)؛ بدون هیچ دسترسی، 403.
    """
    if user.is_superuser:
        return None
    # مجوز کامل مشاهده یا مدیریت روی این سایت (None = مجوز سراسری روی همه سایت‌ها)
    view_sites = await get_sites_with_permission(db, user, "leave_requests.view")
    manage_sites = await get_sites_with_permission(db, user, "leave_requests.manage")
    has_view = view_sites is None or site_id in view_sites
    has_manage = manage_sites is None or site_id in manage_sites
    if has_view or has_manage:
        return None

    # مجوزهای به‌تفکیک نوع که برای این سایت معتبرند
    type_permission_map = await get_sites_with_permission_prefix(db, user, "leave_requests.view.type.")
    allowed_codes = {code for code, sites in type_permission_map.items() if sites is None or site_id in sites}
    if not allowed_codes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دسترسی لازم برای مشاهده درخواست‌های این سایت را ندارید",
        )

    # تبدیل کد مجوز (بر اساس عنوان) به شناسه نوع‌های همین سایت
    site_types = await db.execute(select(LeaveRequestType).where(LeaveRequestType.site_id == site_id))
    allowed_type_ids = [t.id for t in site_types.scalars().all() if permission_code_for_type_title(t.title) in allowed_codes]
    if allowed_type_ids:
        return allowed_type_ids

    # مجوز نوع دارد ولی هیچ نوعی با آن عنوان در این سایت نیست
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="دسترسی لازم برای مشاهده درخواست‌های این سایت را ندارید",
    )


@router.get("/sites/{site_id}/all", response_model=list[LeaveRequestOut])
async def list_all_for_site(
    site_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    status_filter: str | None = None,
    type_id: int | None = None,
    department: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    گزارش همه درخواست‌های یک سایت با فیلترهای اختیاری (بازه تاریخ، وضعیت، نوع، واحد).
    مجوز: leave_requests.view/manage یا مجوز به‌تفکیک نوع (با محدودیت‌های زیر)؛ وگرنه 403.
    خطاها: 400 برای خطای منطقی سرویس، 500 با متن خطا برای مشکل دیتابیس کاراوب.
    """
    allowed_type_ids = await _get_view_access(db, current_user, site_id)
    # نقش محدود به نوع (مثل «حراست»): فیلتر بازه تاریخ نادیده گرفته می‌شود (بدون خطا)
    is_type_restricted = allowed_type_ids is not None
    if is_type_restricted:
        date_from = None
        date_to = None
    try:
        items = await LeaveRequestService(db).list_all_for_site(
            site_id, allowed_type_ids, date_from, date_to, status_filter, type_id, department
        )
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:  # noqa: BLE001
        # خطای دیتابیس کاراوب (ستون/جدول نگاشت‌شده ناموجود، قطع اتصال و ...): چون این صفحه
        # فقط برای ادمین/منابع انسانی است، متن خطا برای عیب‌یابی در پاسخ برگردانده می‌شود
        logger.exception("دریافت فهرست درخواست‌های مرخصی/ماموریت سایت %s با خطا مواجه شد", site_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در خواندن درخواست‌ها از کاراوب: {str(e)[:400]}",
        )
    if is_type_restricted:
        # نقش محدود به نوع، درخواست‌های «در حال بررسی» انواع ساعتی را نمی‌بیند (روزانه اشکالی ندارد).
        # ملاک ساعتی‌بودن، پربودن start_hour است که برای انواع روزانه در WF_Requests خالی است.
        items = [
            item
            for item in items
            if not (item["status"] == "pending" and item["start_hour"] is not None)
        ]
    return items


@router.get("/sites/{site_id}/export")
async def export_leave_requests(
    site_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    status_filter: str | None = None,
    type_id: int | None = None,
    department: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    خروجی Excel گزارش درخواست‌های سایت با همان فیلترهای list_all_for_site (آنچه کاربر می‌بیند، همان را می‌گیرد).
    مجوز: فقط دسترسی کامل (leave_requests.view/manage)؛ نقش محدود به نوع 403 می‌گیرد.
    """
    allowed_type_ids = await _get_view_access(db, current_user, site_id)
    # نقش محدود به نوع حق خروجی Excel ندارد؛ این بررسی سمت سرور جلوی فراخوانی مستقیم را می‌گیرد
    if allowed_type_ids is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="شما مجاز به تهیه خروجی Excel نیستید"
        )
    try:
        items = await LeaveRequestService(db).list_all_for_site(
            site_id, allowed_type_ids, date_from, date_to, status_filter, type_id, department
        )
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # ساخت فایل و برگرداندن به‌صورت دانلود
    site = await db.get(Site, site_id)
    content = build_leave_requests_xlsx(items, site.name if site else "")
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="leave-requests-{site_id}.xlsx"'},
    )


@router.delete("/sites/{site_id}/requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_request(
    site_id: int,
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    حذف مدیریتی یک درخواست در هر مرحله‌ای (برخلاف حذف پرسنلی که فقط درخواست خودِ فرد و
    قبل از تصمیم‌گیری است)؛ ردیف‌های وابسته در WF_Reviews و جدول‌های فرزند هم حذف می‌شوند.
    مجوز: leave_requests.manage. 400 اگر درخواست پیدا نشود.
    """
    await require_site_permission(db, current_user, site_id, "leave_requests.manage")
    try:
        await LeaveRequestService(db).admin_delete_request(site_id, request_id)
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/sites/{site_id}/requests/{request_id}")
async def admin_update_request(
    site_id: int,
    request_id: int,
    payload: AdminUpdateRequestIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ویرایش مدیریتی فیلدهای یک درخواست (وضعیت نهایی، تاریخ/ساعت، نوع، نظر تأییدکننده، توضیحات).
    مجوز: leave_requests.manage. 400 برای خطای منطقی سرویس.
    """
    await require_site_permission(db, current_user, site_id, "leave_requests.manage")
    # exclude_unset فقط فیلدهایی را می‌فرستد که کلاینت واقعاً داده؛ None عمدی معنادار است
    # (is_final_approved=None یعنی برگرداندن به «در حال بررسی») و نباید فیلتر شود
    try:
        await LeaveRequestService(db).admin_update_request(
            site_id, request_id, payload.model_dump(exclude_unset=True)
        )
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"ok": True}
