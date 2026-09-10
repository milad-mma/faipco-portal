"""
Endpoint های «درخواست مرخصی/ماموریت» - ثبت (پرسنل)، فهرست خودم، فهرست
در‌انتظار تأیید من، و تصمیم‌گیری (تأییدکننده).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.employee import Employee
from app.models.leave_request import LeaveRequestType
from app.models.user import User
from app.schemas.leave_request import (
    DecideRequestIn,
    LeaveRequestOut,
    LeaveRequestTypeOut,
    SubmitLeaveRequestIn,
    SubmitLeaveRequestOut,
)
from app.services.leave_request_service import LeaveRequestError, LeaveRequestService

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


@router.get("/types", response_model=list[LeaveRequestTypeOut])
async def get_active_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """فهرست نوع‌های فعال درخواست، برای فرم ثبت - بر اساس سایت خودِ کاربر."""
    employee = await _require_employee(db, current_user)
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
    employee = await _require_employee(db, current_user)
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
        )
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/my-requests", response_model=list[LeaveRequestOut])
async def get_my_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    employee = await _require_employee(db, current_user)
    try:
        return await LeaveRequestService(db).list_pending_for_approver(employee)
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{request_id}/decide")
async def decide_request(
    request_id: int,
    payload: DecideRequestIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
