"""
Endpoint های «ساختار ارزیابی عملکرد»: مدیریت سرپرست ارزیابی واحد، مدیران و اهدافشان،
سرشیفت‌ها و زیرمجموعه‌های آن‌ها، و دریافت ساختار کامل یک سایت.

همه endpointها نیازمند مجوز performance.structure.manage برای سایت مربوطه‌اند. چون بیشتر آن‌ها
با department_id/manager_id/shift_lead_id کار می‌کنند، site_id ابتدا از همان رکورد استخراج
می‌شود و سپس دسترسی دقیقاً برای همان سایت با _require_site_permission بررسی می‌شود
(require_permission با site_scoped=True فقط site_id مستقیم در Path/Query را می‌بیند).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.employee import Department, Employee
from app.models.evaluation import EvaluationManager, EvaluationShiftAssignment, EvaluationShiftLead
from app.models.user import User
from app.schemas.evaluation import (
    AddManagerIn,
    AddManagerTargetIn,
    AddShiftLeadIn,
    DepartmentSupervisorOut,
    ManagerCandidateOut,
    ManagerOut,
    SetDepartmentSupervisorIn,
    SetShiftAssignmentIn,
    ShiftAssignmentOut,
    ShiftLeadOut,
    SiteStructureOut,
    UpdateManagerTitleIn,
)
from app.services.evaluation_structure_service import EvaluationStructureError, EvaluationStructureService

router = APIRouter()

PERMISSION_CODE = "performance.structure.manage"


async def _require_site_permission(db: AsyncSession, user: User, site_id: int) -> None:
    """بررسی می‌کند کاربر مجوز مدیریت ساختار را برای این سایت دارد؛ superuser همیشه مجاز، در غیر این صورت 403."""
    if user.is_superuser:
        return
    sites = await get_sites_with_permission(db, user, PERMISSION_CODE)
    if sites is not None and site_id not in sites:  # sites=None یعنی مجوز روی همه سایت‌ها
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"دسترسی لازم برای این عملیات را ندارید: {PERMISSION_CODE}"
        )


@router.get("/sites/{site_id}/structure", response_model=SiteStructureOut)
async def get_site_structure(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ساختار کامل ارزیابی سایت (مدیران، واحدها، سرپرستان، سرشیفت‌ها)؛ نیازمند مجوز ساختار، 404 اگر سایت نباشد."""
    await _require_site_permission(db, current_user, site_id)
    try:
        return await EvaluationStructureService(db).get_site_structure(site_id)
    except EvaluationStructureError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/sites/{site_id}/manager-candidates", response_model=list[ManagerCandidateOut])
async def get_manager_candidates(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """فهرست گزینه‌های قابل افزودن به فهرست یک مدیر، همراه برچسب‌های وضعیت؛ نیازمند مجوز ساختار سایت."""
    await _require_site_permission(db, current_user, site_id)
    return await EvaluationStructureService(db).get_manager_candidates(site_id)


@router.put("/departments/{department_id}/supervisor", response_model=DepartmentSupervisorOut)
async def set_department_supervisor(
    department_id: int,
    payload: SetDepartmentSupervisorIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """تعیین/تغییر سرپرست ارزیابی یک واحد؛ نیازمند مجوز ساختار سایت واحد. خطاها: 404 واحد یافت نشد، 400 خطای سرویس."""
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
    """حذف سرپرست ارزیابی یک واحد؛ نیازمند مجوز ساختار سایت واحد، 404 اگر واحد نباشد."""
    department = await db.get(Department, department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="واحد سازمانی موردنظر یافت نشد")
    await _require_site_permission(db, current_user, department.site_id)
    await EvaluationStructureService(db).remove_department_supervisor(department_id)


@router.post("/sites/{site_id}/managers", response_model=ManagerOut)
async def add_manager(
    site_id: int,
    payload: AddManagerIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """افزودن یک پرسنل به‌عنوان مدیر ارزیابی سایت؛ نیازمند مجوز ساختار سایت، 400 در خطای سرویس (مثلاً تکراری)."""
    await _require_site_permission(db, current_user, site_id)
    try:
        return await EvaluationStructureService(db).add_manager(site_id, payload.employee_id, payload.title)
    except EvaluationStructureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/managers/{manager_id}/title", response_model=ManagerOut)
async def update_manager_title(
    manager_id: int,
    payload: UpdateManagerTitleIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """تغییر عنوان نمایشی مدیر؛ نیازمند مجوز ساختار سایت مدیر. خطاها: 404 مدیر یافت نشد، 400 خطای سرویس."""
    manager = await db.get(EvaluationManager, manager_id)
    if manager is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مدیر موردنظر یافت نشد")
    await _require_site_permission(db, current_user, manager.site_id)
    try:
        return await EvaluationStructureService(db).update_manager_title(manager_id, payload.title)
    except EvaluationStructureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/managers/{manager_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_manager(
    manager_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """حذف مدیر همراه همه اهدافش؛ نیازمند مجوز ساختار سایت مدیر. مدیر ناموجود: 204 بی‌اثر."""
    manager = await db.get(EvaluationManager, manager_id)
    if manager is None:
        return
    await _require_site_permission(db, current_user, manager.site_id)
    await EvaluationStructureService(db).remove_manager(manager_id)


@router.post("/managers/{manager_id}/targets", response_model=ManagerOut)
async def add_manager_target(
    manager_id: int,
    payload: AddManagerTargetIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    افزودن یک پرسنل به فهرست ارزیابی‌شوندگان مدیر؛ نیازمند مجوز ساختار برای سایت مدیر و، اگر هدف
    از سایت دیگری است، برای سایت هدف هم. خطاها: 404 مدیر یافت نشد، 403 سایت غیرمجاز، 400 هدف نامعتبر.
    """
    manager = await db.get(EvaluationManager, manager_id)
    if manager is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مدیر موردنظر یافت نشد")
    await _require_site_permission(db, current_user, manager.site_id)
    # هدفِ سایت دیگر فقط با مجوز ساختار روی همان سایت (جلوگیری از دیدن ارزیابی پرسنل سایت دیگر)
    target = await db.get(Employee, payload.target_employee_id)
    if target is not None and target.site_id != manager.site_id:
        await _require_site_permission(db, current_user, target.site_id)
    try:
        return await EvaluationStructureService(db).add_manager_target(manager_id, payload.target_employee_id)
    except EvaluationStructureError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/managers/{manager_id}/targets/{target_employee_id}", response_model=ManagerOut)
async def remove_manager_target(
    manager_id: int,
    target_employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """حذف یک پرسنل از فهرست مدیر و برگرداندن مدیر به‌روزشده؛ نیازمند مجوز ساختار، 404 اگر مدیر نباشد."""
    manager = await db.get(EvaluationManager, manager_id)
    if manager is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مدیر موردنظر یافت نشد")
    await _require_site_permission(db, current_user, manager.site_id)
    return await EvaluationStructureService(db).remove_manager_target(manager_id, target_employee_id)


@router.post("/departments/{department_id}/shift-leads", response_model=ShiftLeadOut)
async def add_shift_lead(
    department_id: int,
    payload: AddShiftLeadIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """افزودن سرشیفت به یک واحد؛ نیازمند مجوز ساختار سایت واحد. خطاها: 404 واحد یافت نشد، 400 خطای سرویس."""
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
    """حذف یک سرشیفت؛ نیازمند مجوز ساختار سایت واحد آن. سرشیفت ناموجود: 204 بی‌اثر."""
    shift_lead = await db.get(EvaluationShiftLead, shift_lead_id)
    if shift_lead is None:
        return
    # site_id از طریق واحدِ سرشیفت به دست می‌آید
    department = await db.get(Department, shift_lead.department_id)
    await _require_site_permission(db, current_user, department.site_id)
    await EvaluationStructureService(db).remove_shift_lead(shift_lead_id)


@router.put("/shift-assignments", response_model=ShiftAssignmentOut)
async def set_shift_assignment(
    payload: SetShiftAssignmentIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """قراردادن (یا جابه‌جایی) یک پرسنل زیر یک سرشیفت؛ نیازمند مجوز ساختار. خطاها: 404 سرشیفت یافت نشد، 400 خطای سرویس."""
    shift_lead = await db.get(EvaluationShiftLead, payload.shift_lead_id)
    if shift_lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="سرشیفت موردنظر یافت نشد")
    # site_id از طریق واحدِ سرشیفت به دست می‌آید
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
    """خارج‌کردن یک پرسنل از زیرمجموعه سرشیفتش؛ نیازمند مجوز ساختار. اگر تخصیصی نباشد: 204 بی‌اثر."""
    # پیداکردن تخصیص فعلی پرسنل
    result = await db.execute(
        select(EvaluationShiftAssignment).where(EvaluationShiftAssignment.employee_id == employee_id)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        return
    # site_id از زنجیره تخصیص → سرشیفت → واحد به دست می‌آید
    shift_lead = await db.get(EvaluationShiftLead, assignment.shift_lead_id)
    department = await db.get(Department, shift_lead.department_id)
    await _require_site_permission(db, current_user, department.site_id)
    await EvaluationStructureService(db).remove_shift_assignment(employee_id)
