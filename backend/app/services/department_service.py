"""منطق تجاری مدیریت Department ها و انتصاب سرپرست هر واحد."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Department, Employee
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.department import DepartmentCreate, DepartmentOut


class DepartmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _to_out(self, department: Department, name_by_user_id: dict[int, str] | None = None) -> DepartmentOut:
        supervisor_name = None
        if department.supervisor_user_id is not None:
            if name_by_user_id is not None:
                supervisor_name = name_by_user_id.get(department.supervisor_user_id)
            else:
                supervisor_name = await self._resolve_single_supervisor_name(department.supervisor_user_id)

        return DepartmentOut(
            id=department.id,
            site_id=department.site_id,
            name=department.name,
            code=department.code,
            supervisor_user_id=department.supervisor_user_id,
            supervisor_name=supervisor_name,
        )

    async def _resolve_single_supervisor_name(self, user_id: int) -> str | None:
        result = await self.db.execute(
            select(Employee.first_name, Employee.last_name)
            .join(User, User.employee_id == Employee.id)
            .where(User.id == user_id)
        )
        row = result.first()
        return f"{row[0]} {row[1]}" if row else None

    async def list_departments(self, site_id: int | None = None) -> list[DepartmentOut]:
        stmt = select(Department)
        if site_id is not None:
            stmt = stmt.where(Department.site_id == site_id)
        result = await self.db.execute(stmt)
        departments = list(result.scalars().all())

        # نام سرپرست‌ها را در یک Query جمعی می‌خوانیم تا N+1 Query نداشته باشیم
        supervisor_ids = {d.supervisor_user_id for d in departments if d.supervisor_user_id}
        name_by_user_id: dict[int, str] = {}
        if supervisor_ids:
            result = await self.db.execute(
                select(User.id, Employee.first_name, Employee.last_name)
                .join(Employee, Employee.id == User.employee_id)
                .where(User.id.in_(supervisor_ids))
            )
            for user_id, first_name, last_name in result.all():
                name_by_user_id[user_id] = f"{first_name} {last_name}"

        return [await self._to_out(d, name_by_user_id) for d in departments]

    async def create_department(self, payload: DepartmentCreate) -> DepartmentOut:
        department = Department(site_id=payload.site_id, name=payload.name, code=payload.code)
        self.db.add(department)
        await self.db.commit()
        await self.db.refresh(department)
        return await self._to_out(department)

    async def assign_supervisor(self, department_id: int, employee_id: int | None) -> DepartmentOut | None:
        """
        سرپرست واحد را از روی یک پرسنل واقعی (که از Sync آمده) تعیین می‌کند.
        اگر آن پرسنل هنوز حساب کاربری نداشته باشد، خودکار ساخته می‌شود.
        یک نفر می‌تواند هم‌زمان سرپرست چند واحد مختلف باشد — همین متد برای
        هر واحد جداگانه صدا زده می‌شود.
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
        return await self._to_out(department)
