"""
Endpoint های قابلیت «خودروهای من».

/vehicles/me            (GET)     خودروهای خودِ کاربر جاری
/vehicles/me            (POST)    ثبت یک خودروی جدید برای خودِ کاربر جاری
/vehicles/me/{id}       (DELETE)  حذف یکی از خودروهای خودِ کاربر جاری (فقط اگر واقعاً مال خودش باشد)

/vehicles               (GET)     گزارش همه خودروها — Admin (کامل) یا نقش «حراست» (فقط‌خواندنی)
/vehicles/{id}          (PATCH)   ویرایش هر خودرویی — فقط Admin
/vehicles/{id}          (DELETE)  حذف هر خودرویی — فقط Admin
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.vehicle import VehicleAdminOut, VehicleIn, VehicleOut
from app.services.vehicle_service import VehicleService

router = APIRouter()


@router.get("/me", response_model=list[VehicleOut])
async def list_my_vehicles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="حساب شما به هیچ رکورد پرسنلی وصل نیست",
        )
    return await VehicleService(db).list_for_employee(current_user.employee_id)


@router.post("/me", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
async def create_my_vehicle(
    payload: VehicleIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="حساب شما به هیچ رکورد پرسنلی وصل نیست",
        )
    return await VehicleService(db).create_for_employee(current_user.employee_id, payload)


@router.delete("/me/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_vehicle(
    vehicle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="حساب شما به هیچ رکورد پرسنلی وصل نیست",
        )
    found = await VehicleService(db).delete_own(vehicle_id, current_user.employee_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="خودرو یافت نشد")


@router.get("", response_model=list[VehicleAdminOut])
async def list_all_vehicles(
    site_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    گزارش همه خودروها — برای Admin واقعی بدون محدودیت؛ برای نقش «حراست»
    (یا هر نقش دیگری با مجوز vehicles.view_all) فقط خواندنی و محدود به
    سایت‌هایی که آن نقش برایشان تعریف شده (ایزوله‌سازی چندسایتی، دقیقاً
    مثل GET /employees).

    site_id (اختیاری): فیلتر «سایت-محور» برای Admin/کاربر چندسایته که
    می‌خواهد فقط یک سایت را ببیند — با سایت‌های مجاز بالا تقاطع گرفته
    می‌شود؛ نمی‌تواند سایتی خارج از دسترسش را انتخاب کند.
    """
    accessible_site_ids = await get_sites_with_permission(db, current_user, "vehicles.view_all")
    if accessible_site_ids is not None and len(accessible_site_ids) == 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="اجازه مشاهده این گزارش را ندارید")

    if site_id is not None:
        effective_site_ids = {site_id} if accessible_site_ids is None else (accessible_site_ids & {site_id})
    else:
        effective_site_ids = accessible_site_ids

    return await VehicleService(db).list_all(effective_site_ids)


@router.patch("/{vehicle_id}", response_model=VehicleOut)
async def update_vehicle(
    vehicle_id: int,
    payload: VehicleIn,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("vehicles.manage")),
):
    vehicle = await VehicleService(db).admin_update(vehicle_id, payload)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="خودرو یافت نشد")
    return vehicle


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_permission("vehicles.manage")),
):
    found = await VehicleService(db).admin_delete(vehicle_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="خودرو یافت نشد")
