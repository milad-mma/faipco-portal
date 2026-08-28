"""منطق تجاری مدیریت کاربران و انتصاب نقش (Role) — پایه سلسله‌مراتب ارسال اطلاعیه."""
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.employee import Department, Employee
from app.models.site import Site
from app.models.user import Permission, Role, RolePermission, User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user_management import AssignRoleIn, RoleUpsertIn


class UserManagementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_roles(self, exclude_superadmin: bool = True) -> list[Role]:
        stmt = select(Role)
        if exclude_superadmin:
            stmt = stmt.where(Role.name != "superadmin")
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_user_roles(self, user_id: int) -> list[UserRole]:
        result = await self.db.execute(select(UserRole).where(UserRole.user_id == user_id))
        return list(result.scalars().all())

    async def assign_role(self, user_id: int, payload: AssignRoleIn) -> list[UserRole]:
        role = await self.db.get(Role, payload.role_id)
        if role is not None and role.name == "superadmin":
            # نقش superadmin هرگز از طریق UI/API قابل انتصاب نیست — فقط کاربر
            # «admin» که هنگام نصب ساخته می‌شود این دسترسی را دارد.
            raise ValueError("نقش superadmin را نمی‌توان از این طریق اختصاص داد")

        # کدام سایت‌ها از این فهرست از قبل انتصاب دارند؟ (بی‌صدا نادیده
        # گرفته می‌شوند، نه خطای Unique Constraint) — تا کاربر بتواند
        # هرچند‌بار خواست، فهرست سایت‌ها را ویرایش/دوباره ارسال کند.
        existing_result = await self.db.execute(
            select(UserRole.site_id).where(
                UserRole.user_id == user_id,
                UserRole.role_id == payload.role_id,
                UserRole.site_id.in_(payload.site_ids),
            )
        )
        already_assigned = {row[0] for row in existing_result.all()}

        created: list[UserRole] = []
        for site_id in payload.site_ids:
            if site_id in already_assigned:
                continue
            user_role = UserRole(user_id=user_id, role_id=payload.role_id, site_id=site_id)
            self.db.add(user_role)
            created.append(user_role)

        await self.db.commit()
        for user_role in created:
            await self.db.refresh(user_role)
        return created

    async def remove_role_assignment(self, user_role_id: int) -> bool:
        user_role = await self.db.get(UserRole, user_role_id)
        if user_role is None:
            return False
        await self.db.delete(user_role)
        await self.db.commit()
        return True

    async def bulk_assign_role(
        self,
        *,
        role_id: int,
        employee_ids: list[int] | None = None,
        site_id: int | None = None,
        department_id: int | None = None,
    ) -> dict:
        """
        یک نقش را هم‌زمان به تعداد زیادی پرسنل اختصاص می‌دهد — یا با فهرست
        دقیق employee_id، یا با فیلتر (همه پرسنل یک سایت/واحد سازمانی).
        برای هر پرسنل، اگر حساب User ای هنوز نداشته باشد، همینجا خودکار
        ساخته می‌شود (همان منطق get_or_create_employee_user که هنگام اولین
        ورود موفق هم استفاده می‌شود) — پرسنلی که هنوز هیچ‌وقت وارد پرتال
        نشده هم می‌تواند این‌طور نقش بگیرد.

        ⚠️ رفع یک باگ واقعی: قبلاً این تابع همیشه UserRole را با
        site_id=None (سراسری) می‌ساخت — صرف‌نظر از این‌که site_id فقط
        برای فیلترکردن «کدام پرسنل» استفاده شده بود، نه برای خودِ انتصاب!
        یعنی حتی اگر Admin با فیلتر «فقط پرسنل سایت X» یک نقش را دسته‌جمعی
        اختصاص می‌داد، نتیجه واقعی یک انتصاب *سراسری* بود، نه محدود به
        همان سایت — دقیقاً برخلاف انتظار. حالا: اگر فیلتر site_id داده شده
        باشد، همان site_id روی خودِ انتصاب هم ذخیره می‌شود؛ اگر فهرست
        employee_id مستقیم داده شده (بدون فیلتر سایت مشخص)، سایت خودِ هر
        پرسنل به‌طور جداگانه برای انتصابش استفاده می‌شود — چون هر پرسنل
        ذاتاً متعلق به یک سایت است، انتصاب سراسری دیگر معنا ندارد.
        """
        role = await self.db.get(Role, role_id)
        if role is None:
            raise ValueError("نقش پیدا نشد")
        if role.name == "superadmin":
            raise ValueError("نقش superadmin را نمی‌توان از این طریق اختصاص داد")

        if employee_ids:
            stmt = select(Employee).where(Employee.id.in_(employee_ids))
        elif site_id is not None or department_id is not None:
            stmt = select(Employee).where(Employee.is_active.is_(True))
            if site_id is not None:
                stmt = stmt.where(Employee.site_id == site_id)
            if department_id is not None:
                stmt = stmt.where(Employee.department_id == department_id)
        else:
            raise ValueError("باید یا فهرست پرسنل یا حداقل یک فیلتر (سایت/واحد) داده شود")

        result = await self.db.execute(stmt)
        employees = list(result.scalars().all())

        not_found_count = len(employee_ids) - len(employees) if employee_ids else 0

        # مرحله سریع: چه کاربرانی از قبل همین نقش را دارند؟ (برای گزارش
        # already_had — و برای این‌که مجبور نباشیم به‌ازای هر نفر یک کوئری جدا بزنیم)
        user_repo = UserRepository(self.db)

        assigned_count = 0
        already_had_count = 0
        for employee in employees:
            # اگر Admin یک site_id مشخص برای فیلتر داده، همان برای انتصاب هم
            # استفاده می‌شود؛ وگرنه (فهرست مستقیم employee_id) سایت خودِ
            # همین پرسنل — هرگز سراسری/None نیست.
            effective_site_id = site_id if site_id is not None else employee.site_id
            user = await user_repo.get_or_create_employee_user(employee)
            existing = await self.db.execute(
                select(UserRole).where(
                    UserRole.user_id == user.id,
                    UserRole.role_id == role_id,
                    UserRole.site_id == effective_site_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                already_had_count += 1
                continue
            self.db.add(UserRole(user_id=user.id, role_id=role_id, site_id=effective_site_id))
            assigned_count += 1

        await self.db.commit()
        return {
            "assigned_count": assigned_count,
            "already_had_count": already_had_count,
            "not_found_count": not_found_count,
            "total_matched": len(employees),
        }

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

    # ---------- مدیریت خودِ نقش‌ها و مجوزها (پنل مدیریت نقش/مجوز) ----------

    async def list_permissions(self) -> list[Permission]:
        """همه مجوزهای موجود در سیستم — برای چک‌باکس‌های صفحه ساخت/ویرایش نقش.
        هر مجوز جدید همیشه فقط با یک تغییر کد (جایی که واقعاً همین Code را
        require_permission می‌کند) معنا پیدا می‌کند — این صفحه فقط اجازه
        می‌دهد از مجوزهای *موجود*، ترکیب‌های جدید (نقش‌های تازه) ساخته شود،
        نه ساخت یک مجوز کاملاً بی‌ربط به هیچ کد."""
        result = await self.db.execute(select(Permission).order_by(Permission.code))
        return list(result.scalars().all())

    async def get_role_detail(self, role_id: int) -> Role | None:
        result = await self.db.execute(
            select(Role)
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
            .where(Role.id == role_id)
        )
        return result.scalar_one_or_none()

    async def create_role(self, payload: RoleUpsertIn) -> Role:
        if payload.name == "superadmin":
            raise ValueError("این نام رزرو شده است")
        existing = await self.db.execute(select(Role).where(Role.name == payload.name))
        if existing.scalar_one_or_none() is not None:
            raise ValueError("نقشی با همین نام از قبل وجود دارد")

        role = Role(name=payload.name, description=payload.description, is_system=False)
        self.db.add(role)
        await self.db.flush()  # برای گرفتن role.id، قبل از commit نهایی

        if payload.permission_ids:
            result = await self.db.execute(select(Permission.id).where(Permission.id.in_(payload.permission_ids)))
            valid_ids = {row[0] for row in result.all()}
            for permission_id in valid_ids:
                self.db.add(RolePermission(role_id=role.id, permission_id=permission_id))

        await self.db.commit()
        return await self.get_role_detail(role.id)

    async def update_role(self, role_id: int, payload: RoleUpsertIn) -> Role | None:
        role = await self.db.get(Role, role_id)
        if role is None:
            return None
        # ⚠️ طبق درخواست صریح، is_system دیگر مانع ویرایش نمی‌شود — چون
        # نقش‌هایی که پیش از این پنل (مستقیماً از دیتابیس) ساخته شده‌اند
        # (مثل site_manager، hr-manager) با is_system=True ذخیره شده بودند،
        # و کارفرما نیاز داشت همان‌ها را هم بتواند ویرایش کند. فقط خودِ
        # «superadmin» همچنان مستثناست — چون این یک نام خاص است که جای
        # دیگری از کد (منطق مسدودسازی تخصیص نقش) دقیقاً همین رشته را چک
        # می‌کند؛ تغییرش می‌تواند آن منطق را به‌هم بریزد.
        if role.name == "superadmin":
            raise ValueError("نقش superadmin قابل ویرایش نیست")
        if payload.name != role.name:
            existing = await self.db.execute(select(Role).where(Role.name == payload.name, Role.id != role_id))
            if existing.scalar_one_or_none() is not None:
                raise ValueError("نقشی با همین نام از قبل وجود دارد")

        role.name = payload.name
        role.description = payload.description

        # جایگزینی کامل مجوزهای این نقش با فهرست جدید — ساده‌ترین و
        # مطمئن‌ترین راه برای تطبیق با یک چک‌باکس‌لیست در فرانت‌اند (کاربر
        # هرچه را تیک زده، دقیقاً همان باید نهایی شود؛ نه یک Diff دستی).
        await self.db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        if payload.permission_ids:
            result = await self.db.execute(select(Permission.id).where(Permission.id.in_(payload.permission_ids)))
            valid_ids = {row[0] for row in result.all()}
            for permission_id in valid_ids:
                self.db.add(RolePermission(role_id=role_id, permission_id=permission_id))

        await self.db.commit()
        return await self.get_role_detail(role_id)

    async def delete_role(self, role_id: int) -> bool:
        role = await self.db.get(Role, role_id)
        if role is None:
            return False
        # ⚠️ طبق درخواست صریح، is_system دیگر مانع حذف نیست — نقش‌های
        # سیستمی/پیش‌فرض (که با Migration ساخته شده‌اند) فقط از نظر «چطور
        # به وجود آمدند» متفاوت‌اند، نه اینکه ذاتاً غیرقابل‌حذف باشند. فقط
        # خودِ «superadmin» همچنان کاملاً مستثناست — چون این یک نام خاص
        # است که جای دیگری از کد (منطق مسدودسازی تخصیص نقش) دقیقاً همین
        # رشته را چک می‌کند؛ حذفش می‌تواند آن منطق را به‌هم بریزد.
        if role.name == "superadmin":
            raise ValueError("نقش superadmin قابل حذف نیست")

        # ⚠️ عمداً بررسی می‌شود که این نقش همین الان به کسی اختصاص داده
        # نشده باشد — با این‌که خودِ ForeignKey (ondelete=CASCADE) اجازه
        # می‌داد حذف بی‌سروصدا انجام شود، این یعنی اگر این نقش به ۲۰ نفر
        # اختصاص داشت، همه بی‌هیچ هشداری همان لحظه دسترسی‌شان را از دست
        # می‌دادند. به‌جای این رفتار خاموش و خطرناک، این‌جا صریحاً جلوی حذف
        # گرفته می‌شود تا Admin اول خودش آگاهانه انتصاب‌ها را بردارد.
        in_use = await self.db.execute(select(UserRole.id).where(UserRole.role_id == role_id).limit(1))
        if in_use.scalar_one_or_none() is not None:
            raise ValueError("این نقش هم‌اکنون به حداقل یک کاربر اختصاص دارد — ابتدا آن انتصاب‌ها را بردارید")

        await self.db.delete(role)
        await self.db.commit()
        return True
