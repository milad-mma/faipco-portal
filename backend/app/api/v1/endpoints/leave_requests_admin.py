"""
Endpoint های مدیریتی «درخواست مرخصی/ماموریت»:
    - تنظیمات ادمین (Mapping/نوع‌ها/تأییدکننده) - مجوز sites.manage
    - مشاهده همه درخواست‌های یک سایت - مجوز leave_requests.view یا leave_requests.manage
    - ویرایش مدیریتی - فقط leave_requests.manage
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_access import get_sites_with_permission
from app.core.site_permission_deps import require_site_permission
from app.db.session import get_db
from app.models.employee import Department
from app.models.leave_request import LeaveRequestType
from app.models.user import User
from app.schemas.leave_request import (
    AdminUpdateRequestIn,
    LeaveRequestApproverOut,
    LeaveRequestMappingIn,
    LeaveRequestMappingOut,
    LeaveRequestOut,
    LeaveRequestTypeIn,
    LeaveRequestTypeOut,
    LeaveRequestTypeUpdateIn,
    SetApproverIn,
)
from app.services.leave_request_service import LeaveRequestError, LeaveRequestService
from app.services.leave_request_structure_service import LeaveRequestStructureError, LeaveRequestStructureService

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


@router.get("/sites/{site_id}/types", response_model=list[LeaveRequestTypeOut])
async def list_types(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
        site_id, payload.title, payload.is_mission, payload.is_hourly, payload.action_id
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


# ---------- مشاهده/ویرایش مدیریتی (حراست/منابع انسانی) ----------


async def _require_view_or_manage(db: AsyncSession, user: User, site_id: int) -> None:
    """⚠️ کاربر باید یکی از دو مجوز (فقط‌مشاهده یا مدیریت‌کامل) را داشته باشد - نه لزوماً هر دو."""
    if user.is_superuser:
        return
    view_sites = await get_sites_with_permission(db, user, "leave_requests.view")
    manage_sites = await get_sites_with_permission(db, user, "leave_requests.manage")
    has_view = view_sites is None or site_id in view_sites
    has_manage = manage_sites is None or site_id in manage_sites
    if not (has_view or has_manage):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دسترسی لازم برای مشاهده درخواست‌های این سایت را ندارید",
        )


@router.get("/sites/{site_id}/all", response_model=list[LeaveRequestOut])
async def list_all_for_site(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_view_or_manage(db, current_user, site_id)
    try:
        return await LeaveRequestService(db).list_all_for_site(site_id)
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
    try:
        await LeaveRequestService(db).admin_update_request(
            site_id, request_id, {k: v for k, v in payload.model_dump().items() if v is not None}
        )
    except LeaveRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"ok": True}
