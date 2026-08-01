"""منطق تجاری مدیریت Department ها و انتصاب سرپرست هر واحد."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Department, Employee
from app.repositories.user_repository import UserRepository
from app.schemas.department import DepartmentCreate


class DepartmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_departments(self, site_id: int | None = None) -> list[Department]:
        stmt = select(Department)
        if site_id is not None:
            stmt = stmt.where(Department.site_id == site_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_department(self, payload: DepartmentCreate) -> Department:
        department = Department(site_id=payload.site_id, name=payload.name, code=payload.code)
        self.db.add(department)
        await self.db.commit()
        await self.db.refresh(department)
        return department

    async def assign_supervisor(self, department_id: int, employee_id: int | None) -> Department | None:
        """
        سرپرست واحد را از روی یک پرسنل واقعی (که از Sync آمده) تعیین می‌کند.
        اگر آن پرسنل هنوز حساب کاربری نداشته باشد، خودکار ساخته می‌شود.
        """
        department = await self.db.get(Department, department_id)
        if department is None:
            return None

        if employee_id is None:
            department.supervisor_user_id = None
        else:
            employee = await self.db.get(Employee, employee_id)
            if employee is None:
                raise ValueError("پرسنل انتخاب‌شده یافت نشد")
            user = await UserRepository(self.db).get_or_create_employee_user(employee)
            department.supervisor_user_id = user.id

        await self.db.commit()
        await self.db.refresh(department)
        return department
