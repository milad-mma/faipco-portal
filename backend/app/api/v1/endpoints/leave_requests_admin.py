"""
Endpoint های مدیریتی «درخواست مرخصی/ماموریت»:
    - تنظیمات ادمین (Mapping/نوع‌ها/تأییدکننده) - مجوز sites.manage
    - مشاهده همه درخواست‌های یک سایت - مجوز leave_requests.view یا leave_requests.manage
    - ویرایش مدیریتی - فقط leave_requests.manage
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_access import get_sites_with_permission, get_sites_with_permission_prefix
from app.core.site_permission_deps import require_site_permission
from app.db.session import get_db
from app.models.employee import Department
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
    LeaveRequestOut,
    LeaveRequestTypeIn,
    LeaveRequestTypeOut,
    LeaveRequestTypeUpdateIn,
    OperationLookupItemOut,
    SetApproverIn,
    SetHrOfficerIn,
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

SITES_MANAGE = "sites.manage"


@router.get("/sites/{site_id}/mapping", response_model=LeaveRequestMappingOut | None)
async def get_mapping(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    return await LeaveRequestStructureService(db).get_mapping(site_id)


@router.get("/kara-schema-defaults")
async def get_kara_schema_defaults(current_user: User = Depends(get_current_user)):
    """
    نام‌های پیش‌فرض کاراوب - فقط برای دکمه «پر کردن با نام‌های کاراوب» در
    تب‌های نگاشت تردد و مرخصی/ماموریت. تا ادمین ذخیره نکند، استفاده نمی‌شوند.
    """
    return {"attendance": ATTENDANCE_SCHEMA_DEFAULTS, "leave": LEAVE_SCHEMA_DEFAULTS}


@router.put("/sites/{site_id}/mapping", response_model=LeaveRequestMappingOut)
async def upsert_mapping(
    site_id: int,
    payload: LeaveRequestMappingIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    return await LeaveRequestStructureService(db).upsert_mapping(site_id, payload.model_dump())


@router.delete("/sites/{site_id}/mapping", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mapping(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    await LeaveRequestStructureService(db).delete_mapping(site_id)


@router.get("/sites/{site_id}/action-lookup", response_model=list[ActionLookupItemOut])
async def get_action_lookup(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    فهرست رسمی WF_Action (ActionId + عنوان فارسی) - برای کمک به فرم
    «افزودن نوع درخواست» تا ادمین به‌جای حدس‌زدن، از فهرست واقعی انتخاب
    کند.
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
    """فهرست رسمی WF_OperationTypes (OperationId + عنوان فارسی) - برای کمک به فرم «افزودن نوع درخواست»."""
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
    """فهرست رسمی Cards (Card_No + عنوان فارسی) - برای کمک به فرم «افزودن نوع درخواست»."""
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
    ⚠️ رفع باگ واقعی: این Endpoint قبلاً فقط sites.manage را می‌پذیرفت،
    برای همین کاربر منابع انسانی (leave_requests.manage) فهرست نوع‌ها را
    نمی‌گرفت و دراپ‌داون «نوع درخواست» در صفحه گزارش برایش اصلاً نمایش
    داده نمی‌شد - یعنی نمی‌توانست نوع را ویرایش کند، در حالی که ادمین
    می‌توانست. حالا دارندگان مجوز ویرایش درخواست‌ها هم می‌توانند فهرست
    نوع‌ها را بخوانند (خواندن فهرست نوع‌ها اطلاعات حساسی نیست و برای
    ویرایش/فیلتر لازم است).
    """
    if not current_user.is_superuser:
        manage_sites = await get_sites_with_permission(db, current_user, "leave_requests.manage")
        has_leave_manage = manage_sites is None or site_id in manage_sites
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
    leave_type = await db.get(LeaveRequestType, type_id)
    if leave_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="نوع درخواست موردنظر یافت نشد")
    await require_site_permission(db, current_user, leave_type.site_id, SITES_MANAGE)
    try:
        return await LeaveRequestStructureService(db).update_type(
            type_id, {k: v for k, v in payload.model_dump().items() if v is not None}
        )
    except LeaveRequestStructureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_type(
    type_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    return await LeaveRequestStructureService(db).list_approvers(site_id)


@router.put("/departments/{department_id}/approver", response_model=LeaveRequestApproverOut)
async def set_approver(
    department_id: int,
    payload: SetApproverIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    department = await db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="واحد سازمانی موردنظر یافت نشد")
    await require_site_permission(db, current_user, department.site_id, SITES_MANAGE)
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
    department = await db.get(Department, department_id)
    if department is None:
        return
    await require_site_permission(db, current_user, department.site_id, SITES_MANAGE)
    await LeaveRequestStructureService(db).remove_approver(department_id)


@router.get("/sites/{site_id}/hr-officer", response_model=LeaveRequestHrOfficerOut | None)
async def get_hr_officer(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """مسئول نیروی انسانی سایت - تأییدکننده نهایی «تردد فراموش‌شده» (بعد از سرپرست)."""
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    return await LeaveRequestStructureService(db).get_hr_officer(site_id)


@router.put("/sites/{site_id}/hr-officer", response_model=LeaveRequestHrOfficerOut)
async def set_hr_officer(
    site_id: int,
    payload: SetHrOfficerIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    await require_site_permission(db, current_user, site_id, SITES_MANAGE)
    await LeaveRequestStructureService(db).remove_hr_officer(site_id)


# ---------- مشاهده/ویرایش مدیریتی (حراست/منابع انسانی) ----------


async def _get_view_access(db: AsyncSession, user: User, site_id: int) -> list | None:
    """
    ⚠️ طبق تصمیم صریح کاربر: مجوز به‌تفکیک نوع از طریق همان سیستم
    نقش/مجوز (RBAC) موجود پروژه انجام می‌شود - نه یک جدول اختصاصی جدا.
    هر «عنوان» نوع (نه هر ردیف/سایت) یک Permission مشترک دارد
    (leave_requests.view.type.<عنوان‌با‌زیرخط>) - سایت‌بندی از طریق
    UserRole.site_id هنگام تخصیص نقش انجام می‌شود، نه از طریق خودِ کد
    مجوز (دقیقاً مثل leave_requests.view/leave_requests.manage).

    خروجی: None یعنی دسترسی کامل و بی‌قید (سراسری)؛ یک لیست یعنی فقط
    همین شناسه‌های نوع (برای این سایت خاص)؛ اگر هیچ دسترسی‌ای نباشد (نه
    سراسری، نه محدود به حداقل یک نوع)، خطای 403 می‌دهد.
    """
    if user.is_superuser:
        return None
    view_sites = await get_sites_with_permission(db, user, "leave_requests.view")
    manage_sites = await get_sites_with_permission(db, user, "leave_requests.manage")
    has_view = view_sites is None or site_id in view_sites
    has_manage = manage_sites is None or site_id in manage_sites
    if has_view or has_manage:
        return None

    type_permission_map = await get_sites_with_permission_prefix(db, user, "leave_requests.view.type.")
    allowed_codes = {code for code, sites in type_permission_map.items() if sites is None or site_id in sites}
    if not allowed_codes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دسترسی لازم برای مشاهده درخواست‌های این سایت را ندارید",
        )

    site_types = await db.execute(select(LeaveRequestType).where(LeaveRequestType.site_id == site_id))
    allowed_type_ids = [t.id for t in site_types.scalars().all() if permission_code_for_type_title(t.title) in allowed_codes]
    if allowed_type_ids:
        return allowed_type_ids

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
    allowed_type_ids = await _get_view_access(db, current_user, site_id)
    # ⚠️ طبق تصمیم صریح کاربر: کسی که فقط مجوز به‌تفکیک نوع دارد (نقشی
    # مثل «حراست» - یعنی allowed_type_ids لیست است نه None) حق دیدن
    # درخواست‌های «در حال بررسی» را ندارد؛ فقط تصمیم‌گیری‌شده‌ها. همچنین
    # اجازه فیلتر بر اساس بازه تاریخ را هم ندارد (پارامترهای تاریخ
    # نادیده گرفته می‌شوند، نه اینکه خطا بدهند).
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
    if is_type_restricted:
        # ⚠️ طبق تصمیم صریح و دقیق‌شده کاربر: نقش محدود به نوع (حراست)
        # درخواست‌های «در حال بررسی» را فقط برای انواع **ساعتی** نباید
        # ببیند؛ برای انواع **روزانه** دیدن در حال بررسی اشکالی ندارد.
        # ملاک ساعتی‌بودن، پرشدن start_hour است (دقیقاً همان چیزی که در
        # WF_Requests برای انواع ساعتی مقدار می‌گیرد و برای روزانه NULL است).
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
    """⚠️ خروجی Excel - دقیقاً همان فیلترهای لیست را می‌پذیرد، تا آنچه کاربر می‌بیند همان چیزی باشد که خروجی می‌گیرد."""
    allowed_type_ids = await _get_view_access(db, current_user, site_id)
    # ⚠️ طبق تصمیم صریح کاربر: کسی که فقط مجوز به‌تفکیک نوع دارد (نقشی
    # مثل «حراست») اصلاً حق خروجی Excel ندارد - دکمه‌اش در UI هم پنهان
    # است، ولی این بررسی سمت سرور تضمین می‌کند حتی با فراخوانی مستقیم
    # Endpoint هم نتواند خروجی بگیرد.
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
    ⚠️ حذف مدیریتی - هر درخواستی در هر مرحله‌ای (برخلاف حذف پرسنلی که فقط
    درخواست خودِ فرد و فقط تا قبل از تصمیم‌گیری را حذف می‌کند). ردیف
    متناظر در WF_Reviews هم حذف می‌شود.
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
    await require_site_permission(db, current_user, site_id, "leave_requests.manage")
    # ⚠️ رفع باگ واقعی (گزارش کاربر: «وضعیت و نظر تأییدکننده تغییر
    # نمی‌کند»): قبلاً هر مقدار None از payload حذف می‌شد. اما None اینجا
    # یک مقدار معنادار است، نه «داده نشده» - برگرداندن وضعیت به «در حال
    # بررسی» یعنی is_final_approved=None، که دقیقاً همان چیزی بود که
    # فیلتر حذفش می‌کرد و در نتیجه هیچ تغییری اعمال نمی‌شد.
    #
    # exclude_unset=True فقط فیلدهایی را نگه می‌دارد که کلاینت واقعاً
    # فرستاده - پس None عمدی حفظ می‌شود، ولی فیلدهای دست‌نخورده هم
    # بی‌دلیل بازنویسی نمی‌شوند.
    try:
        await LeaveRequestService(db).admin_update_request(
            site_id, request_id, payload.model_dump(exclude_unset=True)
        )
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"ok": True}
