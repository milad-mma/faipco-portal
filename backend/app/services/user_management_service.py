"""منطق تجاری مدیریت کاربران و انتصاب نقش (Role) — پایه سلسله‌مراتب ارسال اطلاعیه."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Department, Employee
from app.models.site import Site
from app.models.user import Role, User, UserRole
from app.schemas.user_management import AssignRoleIn


class UserManagementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(self) -> list[User]:
        result = await self.db.execute(select(User))
        return list(result.scalars().all())

    async def list_roles(self, exclude_superadmin: bool = True) -> list[Role]:
        stmt = select(Role)
        if exclude_superadmin:
            stmt = stmt.where(Role.name != "superadmin")
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_user_roles(self, user_id: int) -> list[UserRole]:
        result = await self.db.execute(select(UserRole).where(UserRole.user_id == user_id))
        return list(result.scalars().all())

    async def assign_role(self, user_id: int, payload: AssignRoleIn) -> UserRole:
        role = await self.db.get(Role, payload.role_id)
        if role is not None and role.name == "superadmin":
            # نقش superadmin هرگز از طریق UI/API قابل انتصاب نیست — فقط کاربر
            # «admin» که هنگام نصب ساخته می‌شود این دسترسی را دارد.
            raise ValueError("نقش superadmin را نمی‌توان از این طریق اختصاص داد")

        user_role = UserRole(user_id=user_id, role_id=payload.role_id, site_id=payload.site_id)
        self.db.add(user_role)
        await self.db.commit()
        await self.db.refresh(user_role)
        return user_role

    async def remove_role_assignment(self, user_role_id: int) -> bool:
        user_role = await self.db.get(UserRole, user_role_id)
        if user_role is None:
            return False
        await self.db.delete(user_role)
        await self.db.commit()
        return True

    # ---------- نمای کلی دسترسی‌ها ----------

    async def get_access_overview(self) -> list[dict]:
        """
        فهرست کامل همه پرسنلی که هر نوع دسترسی خاصی دارند: نقش سازمانی
        (مدیر سایت / مدیر میانی) و/یا سرپرستی یک یا چند واحد سازمانی.
        برای جدول «نمای کلی دسترسی‌ها» در پنل مدیریت دسترسی استفاده می‌شود.
        """
        # ۱. همه نقش‌های اختصاص‌یافته (به‌جز superadmin)
        result = await self.db.execute(
            select(UserRole.user_id, UserRole.site_id, Role.name)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name != "superadmin")
        )
        roles_by_user: dict[int, list[tuple[int | None, str]]] = {}
        for user_id, site_id, role_name in result.all():
            roles_by_user.setdefault(user_id, []).append((site_id, role_name))

        # ۲. همه واحدهایی که سرپرست دارند
        result = await self.db.execute(
            select(Department.id, Department.name, Department.site_id, Department.supervisor_user_id).where(
                Department.supervisor_user_id.is_not(None)
            )
        )
        depts_by_user: dict[int, list[tuple[int, str, int]]] = {}
        for dept_id, dept_name, dept_site_id, supervisor_id in result.all():
            depts_by_user.setdefault(supervisor_id, []).append((dept_id, dept_name, dept_site_id))

        relevant_user_ids = set(roles_by_user) | set(depts_by_user)
        if not relevant_user_ids:
            return []

        # ۳. اطلاعات پرسنلی مرتبط با هر کاربر
        result = await self.db.execute(
            select(
                User.id,
                Employee.id,
                Employee.first_name,
                Employee.last_name,
                Employee.personnel_code,
                Employee.site_id,
            )
            .join(Employee, Employee.id == User.employee_id)
            .where(User.id.in_(relevant_user_ids))
        )
        rows = result.all()

        # ۴. نام همه سایت‌های موردنیاز (هم سایت خودِ پرسنل، هم سایت نقش‌ها/واحدها)
        site_ids_needed: set[int] = {r[5] for r in rows if r[5] is not None}
        for pairs in roles_by_user.values():
            site_ids_needed.update(sid for sid, _ in pairs if sid is not None)
        for pairs in depts_by_user.values():
            site_ids_needed.update(sid for _, _, sid in pairs)

        site_name_by_id: dict[int, str] = {}
        if site_ids_needed:
            site_result = await self.db.execute(select(Site.id, Site.name).where(Site.id.in_(site_ids_needed)))
            site_name_by_id = dict(site_result.all())

        overview: list[dict] = []
        for user_id, employee_id, first_name, last_name, personnel_code, emp_site_id in rows:
            role_entries = [
                {"role_name": name, "site_name": site_name_by_id.get(sid) if sid else None}
                for sid, name in roles_by_user.get(user_id, [])
            ]
            dept_entries = [
                {"id": did, "name": dname, "site_name": site_name_by_id.get(dsid, "")}
                for did, dname, dsid in depts_by_user.get(user_id, [])
            ]
            overview.append(
                {
                    "employee_id": employee_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "personnel_code": personnel_code,
                    "site_name": site_name_by_id.get(emp_site_id, "—") if emp_site_id else "—",
                    "roles": role_entries,
                    "supervised_departments": dept_entries,
                }
            )

        overview.sort(key=lambda e: (e["first_name"], e["last_name"]))
        return overview
