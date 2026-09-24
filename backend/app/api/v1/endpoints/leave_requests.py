"""
Endpoint های سمت پرسنل و تأییدکننده برای «درخواست مرخصی/ماموریت» (پیشوند /leave-requests).

    - پرسنل: فهرست نوع‌های فعال، ثبت درخواست، فهرست درخواست‌های خودم، حذف درخواست تصمیم‌گیری‌نشده
    - تأییدکننده: فهرست در انتظار من، سوابق تصمیم‌های من، شمارنده داشبورد، تأیید/رد
همه‌ی این مسیرها به حساب متصل به پرسنل نیاز دارند (به‌جز pending-count که صفر برمی‌گرداند).
خطاهای منطقی LeaveRequestService به 400 تبدیل می‌شوند.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.employee import Employee
from app.models.leave_request import LeaveRequestMapping, LeaveRequestType
from app.models.user import User
from app.schemas.leave_request import (
    DecidedLeaveRequestsPage,
    DecideRequestIn,
    LeaveRequestOut,
    LeaveRequestTypeOut,
    SubmitLeaveRequestIn,
    SubmitLeaveRequestOut,
)
from app.services.leave_request_service import LeaveRequestError, LeaveRequestService
from app.services.access_gate_service import AccessGateBlocked, AccessGateService

router = APIRouter()


async def _require_employee(db: AsyncSession, current_user: User) -> Employee:
    """پرسنل متصل به کاربر فعلی را برمی‌گرداند؛ حساب بدون پرسنل 400 و پرسنل حذف‌شده 404 می‌دهد."""
    if current_user.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="این قابلیت فقط برای حساب‌های متصل به پرسنل در دسترس است"
        )
    employee = await db.get(Employee, current_user.employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل موردنظر یافت نشد")
    return employee


@router.get("/types", response_model=list[LeaveRequestTypeOut])
async def get_active_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    فهرست نوع‌های فعال درخواست برای فرم ثبت، بر اساس سایت پرسنل کاربر.
    اگر ماژول برای سایت غیرفعال شده باشد، لیست خالی برمی‌گرداند.
    """
    employee = await _require_employee(db, current_user)
    # ماژول غیرفعال‌شده از پنل: فرم پرسنل هیچ نوعی نمی‌بیند
    mapping_disabled = await db.scalar(
        select(LeaveRequestMapping.is_disabled).where(LeaveRequestMapping.site_id == employee.site_id)
    )
    if mapping_disabled:
        return []
    # فقط نوع‌های فعال همین سایت
    result = await db.execute(
        select(LeaveRequestType).where(
            LeaveRequestType.site_id == employee.site_id, LeaveRequestType.is_active.is_(True)
        )
    )
    return list(result.scalars().all())


@router.post("/submit", response_model=SubmitLeaveRequestOut)
async def submit_request(
    payload: SubmitLeaveRequestIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ثبت یک درخواست جدید در WF_Requests کاراوب توسط پرسنل.
    ورودی SubmitLeaveRequestIn؛ خروجی شناسه ردیف(های) ساخته‌شده.
    خطاها: 403 اگر پیش‌نیاز دسترسی (اطلاعیه/ارزیابی) رد شود، 400 برای خطای اعتبارسنجی سرویس.
    """
    # پیش‌نیاز دسترسی: اگر ادمین آن را فعال کرده باشد و کاربر اطلاعیه خوانده‌نشده یا
    # ارزیابی انجام‌نشده داشته باشد، 403 می‌گیرد
    try:
        await AccessGateService(db).check(current_user, "leave_request")
    except AccessGateBlocked as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    employee = await _require_employee(db, current_user)
    # اعتبارسنجی نوع/تاریخ‌ها و نوشتن در کاراوب داخل سرویس انجام می‌شود
    try:
        return await LeaveRequestService(db).submit_request(
            employee=employee,
            leave_type_id=payload.leave_type_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            start_hour=payload.start_hour,
            end_hour=payload.end_hour,
            description=payload.description,
            source=payload.source,
            destination=payload.destination,
            punches=payload.punches,
        )
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/my-requests", response_model=list[LeaveRequestOut])
async def get_my_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """فهرست درخواست‌های خودِ پرسنل (همه وضعیت‌ها) از کاراوب؛ 400 اگر سایت نگاشت نداشته باشد."""
    employee = await _require_employee(db, current_user)
    try:
        return await LeaveRequestService(db).list_my_requests(employee)
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/pending-for-me", response_model=list[LeaveRequestOut])
async def get_pending_for_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """درخواست‌های در انتظار تصمیم کاربر فعلی به‌عنوان تأییدکننده (سرپرست یا مسئول نیروی انسانی)."""
    employee = await _require_employee(db, current_user)
    try:
        return await LeaveRequestService(db).list_pending_for_approver(employee)
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/decided-by-me", response_model=DecidedLeaveRequestsPage)
async def get_decided_by_me(
    page: int = 0,
    page_size: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """سوابق درخواست‌هایی که کاربر فعلی تأیید/رد کرده است؛ صفحه‌بندی با page/page_size، جدیدترین تصمیم بالا."""
    employee = await _require_employee(db, current_user)
    try:
        return await LeaveRequestService(db).list_decided_by_approver(employee, page, page_size)
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/pending-count")
async def get_pending_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    تعداد درخواست‌های در انتظار تصمیم کاربر فعلی، برای شمارنده کارت داشبورد.
    هرگز خطا نمی‌دهد: کاربر بدون پرسنل یا سایت بدون نگاشت، صفر می‌گیرد.
    """
    # بدون پرسنل متصل، شمارنده صفر است (کارت داشبورد برای همه نمایش داده می‌شود)
    if current_user.employee_id is None:
        return {"pending_count": 0}
    employee = await db.get(Employee, current_user.employee_id)
    if employee is None:
        return {"pending_count": 0}
    return {"pending_count": await LeaveRequestService(db).get_pending_count_for_approver(employee)}


@router.delete("/{request_id}")
async def delete_my_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """حذف یک درخواست توسط خودِ پرسنل؛ فقط درخواست خودش و فقط تا وقتی تصمیم‌گیری نشده (وگرنه 400)."""
    employee = await _require_employee(db, current_user)
    try:
        await LeaveRequestService(db).delete_request(request_id, employee)
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"ok": True}


@router.post("/{request_id}/decide")
async def decide_request(
    request_id: int,
    payload: DecideRequestIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    تأیید یا رد یک درخواست توسط تأییدکننده فعلی آن (ورودی DecideRequestIn).
    سرویس بررسی می‌کند که کاربر واقعاً تأییدکننده این درخواست باشد؛ در غیر این صورت 400.
    """
    employee = await _require_employee(db, current_user)
    try:
        await LeaveRequestService(db).decide_request(
            site_id=employee.site_id,
            request_id=request_id,
            approver_employee=employee,
            approved=payload.approved,
            manager_idea=payload.manager_idea,
        )
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"ok": True}
