"""سرویس قابلیت «خودروهای من» — ثبت خودشخصی پرسنل + گزارش Admin/حراست."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Department, Employee
from app.models.site import Site
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleAdminOut, VehicleIn


class VehicleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- Self-service (خودِ پرسنل) ----------

    async def list_for_employee(self, employee_id: int) -> list[Vehicle]:
        result = await self.db.execute(
            select(Vehicle).where(Vehicle.employee_id == employee_id).order_by(Vehicle.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_for_employee(self, employee_id: int, payload: VehicleIn) -> Vehicle:
        vehicle = Vehicle(employee_id=employee_id, **payload.model_dump())
        self.db.add(vehicle)
        await self.db.commit()
        await self.db.refresh(vehicle)
        return vehicle

    async def delete_own(self, vehicle_id: int, employee_id: int) -> bool:
        """فقط اگر این خودرو واقعاً متعلق به همین پرسنل باشد حذف می‌شود — برمی‌گرداند آیا پیدا/حذف شد."""
        result = await self.db.execute(
            select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.employee_id == employee_id)
        )
        vehicle = result.scalar_one_or_none()
        if vehicle is None:
            return False
        await self.db.delete(vehicle)
        await self.db.commit()
        return True

    # ---------- گزارش Admin/حراست (فقط‌خواندنی برای حراست، کامل برای Admin) ----------

    async def list_all(self, accessible_site_ids: set[int] | None) -> list[VehicleAdminOut]:
        """
        accessible_site_ids=None یعنی بدون محدودیت (Admin واقعی) — در غیر
        این صورت فقط خودروهای پرسنلِ همان سایت‌ها (ایزوله‌سازی چندسایتی،
        دقیقاً مثل GET /employees).
        """
        stmt = (
            select(Vehicle, Employee, Site.name, Department.name)
            .join(Employee, Employee.id == Vehicle.employee_id)
            .join(Site, Site.id == Employee.site_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .order_by(Vehicle.created_at.desc())
        )
        if accessible_site_ids is not None:
            stmt = stmt.where(Employee.site_id.in_(accessible_site_ids))
        result = await self.db.execute(stmt)

        return [
            VehicleAdminOut(
                id=v.id,
                vehicle_type=v.vehicle_type,
                color=v.color,
                plate_digits1=v.plate_digits1,
                plate_letter=v.plate_letter,
                plate_digits2=v.plate_digits2,
                plate_iran_code=v.plate_iran_code,
                created_at=v.created_at,
                employee_id=employee.id,
                employee_name=f"{employee.first_name} {employee.last_name}",
                personnel_code=employee.personnel_code,
                site_name=site_name,
                department_name=department_name,
            )
            for v, employee, site_name, department_name in result.all()
        ]

    async def admin_update(self, vehicle_id: int, payload: VehicleIn) -> Vehicle | None:
        vehicle = await self.db.get(Vehicle, vehicle_id)
        if vehicle is None:
            return None
        for key, value in payload.model_dump().items():
            setattr(vehicle, key, value)
        await self.db.commit()
        await self.db.refresh(vehicle)
        return vehicle

    async def admin_delete(self, vehicle_id: int) -> bool:
        vehicle = await self.db.get(Vehicle, vehicle_id)
        if vehicle is None:
            return False
        await self.db.delete(vehicle)
        await self.db.commit()
        return True
