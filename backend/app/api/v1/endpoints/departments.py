"""
Endpoint های مدیریت واحدهای سازمانی (Department).

انتصاب سرپرست هر واحد دقیقاً همان چیزی است که سلسله‌مراتب ارسال اطلاعیه را
می‌سازد: سرپرست هر واحد به‌صورت خودکار اجازه ارسال اطلاعیه به همان واحد
(و پرسنل همان واحد) را پیدا می‌کند — بدون نیاز به تعریف هیچ Role جداگانه‌ای.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.department import AssignSupervisorIn, DepartmentCreate, DepartmentOut
from app.services.department_service import DepartmentService

router = APIRouter()


@router.get("", response_model=list[DepartmentOut])
async def list_departments(
    site_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    # لیست واحدها فقط اطلاعات سازمانی است (نه داده حساس)؛ هر کاربر لاگین‌شده
    # برای پر کردن فرم ارسال اطلاعیه به آن نیاز دارد.
    return await DepartmentService(db).list_departments(site_id=site_id)


@router.post("", response_model=DepartmentOut)
async def create_department(
    payload: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage")),
):
    return await DepartmentService(db).create_department(payload)


@router.put("/{department_id}/supervisor", response_model=DepartmentOut)
async def assign_supervisor(
    department_id: int,
    payload: AssignSupervisorIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    try:
        department = await DepartmentService(db).assign_supervisor(department_id, payload.employee_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="واحد سازمانی یافت نشد")
    return department
