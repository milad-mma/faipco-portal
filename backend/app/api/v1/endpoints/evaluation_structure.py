"""
Endpoint های «ساختار ارزیابی عملکرد» - مدیریت انتساب سرپرست/مدیر سایت/
سایر مدیران/سرشیفت.

⚠️ نکته امنیتی مهم: برخلاف اکثر Endpoint های این پروژه که site_id را
مستقیماً در Path/Query دارند (و می‌توانند از الگوی ساده
require_permission(..., site_scoped=True) استفاده کنند)، بیشتر
Endpoint های این فایل بر اساس department_id/manager_id/shift_lead_id کار
می‌کنند - یعنی site_id باید ابتدا از طریق همان رکورد Resolve شود، سپس
دسترسی Site-محور دقیقاً برای همان Site (نه بر اساس هر سایتی که کاربر
هرجایی این مجوز را دارد) بررسی شود. برای همین از یک تابع کمکی مشترک
(_require_site_permission) استفاده می‌شود، نه require_permission
site_scoped=True (که فقط site_id مستقیم در Path/Query را می‌بیند و
اینجا منجر به دورزدن ایزولاسیون سایت می‌شد).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.employee import Department
from app.models.evaluation import EvaluationOtherManager, EvaluationShiftAssignment, EvaluationShiftLead, EvaluationSiteManager
from app.models.user import User
from app.schemas.evaluation import (
    AddOtherManagerIn,
    AddShiftLeadIn,
    AddSiteManagerIn,
    SetDepartmentSupervisorIn,
    SetShiftAssignmentIn,
)
from app.services.evaluation_structure_service import EvaluationStructureError, EvaluationStructureService

router = APIRouter()

PERMISSION_CODE = "performance.structure.manage"


async def _require_site_permission(db: AsyncSession, user: User, site_id: int) -> None:
    if user.is_superuser:
        return
    sites = await get_sites_with_permission(db, user, PERMISSION_CODE)
    if sites is not None and site_id not in sites:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"دسترسی لازم برای این عملیات را ندارید: {PERMISSION_CODE}"
        )


@router.get("/sites/{site_id}/structure")
async def get_site_structure(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_site_permission(db, current_user, site_id)
    return await EvaluationStructureService(db).get_site_structure(site_id)


@router.put("/departments/{department_id}/supervisor")
async def set_department_supervisor(
    department_id: int,
    payload: SetDepartmentSupervisorIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    department = await db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="واحد سازمانی موردنظر یافت نشد")
    await _require_site_permission(db, current_user, department.site_id)
    try:
        return await EvaluationStructureService(db).set_department_supervisor(department_id, payload.employee_id)
    except EvaluationStructureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/departments/{department_id}/supervisor", status_code=status.HTTP_204_NO_CONTENT)
async def remove_department_supervisor(
    department_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    department = await db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="واحد سازمانی موردنظر یافت نشد")
    await _require_site_permission(db, current_user, department.site_id)
    await EvaluationStructureService(db).remove_department_supervisor(department_id)


@router.post("/sites/{site_id}/managers")
async def add_site_manager(
    site_id: int,
    payload: AddSiteManagerIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_site_permission(db, current_user, site_id)
    try:
        return await EvaluationStructureService(db).add_site_manager(site_id, payload.employee_id)
    except EvaluationStructureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/managers/{manager_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_site_manager(
    manager_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    manager = await db.get(EvaluationSiteManager, manager_id)
    if manager is None:
        return
    await _require_site_permission(db, current_user, manager.site_id)
    await EvaluationStructureService(db).remove_site_manager(manager_id)


@router.post("/sites/{site_id}/other-managers")
async def add_other_manager(
    site_id: int,
    payload: AddOtherManagerIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_site_permission(db, current_user, site_id)
    try:
        return await EvaluationStructureService(db).add_other_manager(site_id, payload.employee_id)
    except EvaluationStructureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/other-managers/{manager_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_other_manager(
    manager_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    manager = await db.get(EvaluationOtherManager, manager_id)
    if manager is None:
        return
    await _require_site_permission(db, current_user, manager.site_id)
    await EvaluationStructureService(db).remove_other_manager(manager_id)


@router.post("/departments/{department_id}/shift-leads")
async def add_shift_lead(
    department_id: int,
    payload: AddShiftLeadIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    department = await db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="واحد سازمانی موردنظر یافت نشد")
    await _require_site_permission(db, current_user, department.site_id)
    try:
        return await EvaluationStructureService(db).add_shift_lead(department_id, payload.employee_id)
    except EvaluationStructureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/shift-leads/{shift_lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_shift_lead(
    shift_lead_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shift_lead = await db.get(EvaluationShiftLead, shift_lead_id)
    if shift_lead is None:
        return
    department = await db.get(Department, shift_lead.department_id)
    await _require_site_permission(db, current_user, department.site_id)
    await EvaluationStructureService(db).remove_shift_lead(shift_lead_id)


@router.put("/shift-assignments")
async def set_shift_assignment(
    payload: SetShiftAssignmentIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shift_lead = await db.get(EvaluationShiftLead, payload.shift_lead_id)
    if shift_lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="سرشیفت موردنظر یافت نشد")
    department = await db.get(Department, shift_lead.department_id)
    await _require_site_permission(db, current_user, department.site_id)
    try:
        return await EvaluationStructureService(db).set_shift_assignment(
            payload.employee_id, payload.shift_lead_id
        )
    except EvaluationStructureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/shift-assignments/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_shift_assignment(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(EvaluationShiftAssignment).where(EvaluationShiftAssignment.employee_id == employee_id)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        return
    shift_lead = await db.get(EvaluationShiftLead, assignment.shift_lead_id)
    department = await db.get(Department, shift_lead.department_id)
    await _require_site_permission(db, current_user, department.site_id)
    await EvaluationStructureService(db).remove_shift_assignment(employee_id)
