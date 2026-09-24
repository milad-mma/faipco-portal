"""
منطق تجاری مدیریت کاربران و نقش‌ها (UserManagementService).
- فهرست نقش‌ها و انتصاب‌ها، انتصاب تکی/چندسایتی و گروهی نقش، حذف انتصاب.
- نمای کلی دسترسی‌ها (نقش‌ها و سرپرستی واحدها) برای پنل مدیریت دسترسی.
- ساخت/ویرایش/حذف تعریف نقش‌ها و فهرست مجوزها. انتصاب نقش پایه‌ی سلسله‌مراتب ارسال اطلاعیه است.
نقش «superadmin» هیچ‌گاه از این سرویس قابل انتصاب، ویرایش یا حذف نیست.
"""
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.employee import Department, Employee
from app.models.site import Site
from app.models.site_transfer import SiteTransfer
from app.models.user import Permission, Role, RolePermission, User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user_management import AssignRoleIn, RoleUpsertIn


class UserManagementService:
    """عملیات مدیریت نقش، مجوز و انتصاب؛ ورودی سازنده: نشست دیتابیس."""
    def __init__(self, db: AsyncSession):
        """نشست async دیتابیس را نگه می‌دارد."""
        self.db = db

    async def list_roles(self, exclude_superadmin: bool = True) -> list[Role]:
        """فهرست نقش‌ها را برمی‌گرداند؛ به‌طور پیش‌فرض superadmin حذف می‌شود."""
        stmt = select(Role)
        if exclude_superadmin:
            stmt = stmt.where(Role.name != "superadmin")
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_user_roles(self, user_id: int) -> list[UserRole]:
        """همه‌ی انتصاب‌های نقش (ردیف‌های user_roles) یک کاربر را برمی‌گرداند."""
        result = await self.db.execute(select(UserRole).where(UserRole.user_id == user_id))
        return list(result.scalars().all())

    async def assign_role(self, user_id: int, payload: AssignRoleIn) -> list[UserRole]:
        """
        نقش payload.role_id را برای هر سایت در payload.site_ids به کاربر می‌دهد (یک ردیف به ازای هر سایت).
        سایت‌هایی که از قبل همین انتصاب را دارند نادیده گرفته می‌شوند. خروجی: انتصاب‌های تازه‌ساخته‌شده.
        خطا: ValueError برای نقش superadmin.
        """
        role = await self.db.get(Role, payload.role_id)
        if role is not None and role.name == "superadmin":
            # نقش superadmin هرگز از طریق UI/API قابل انتصاب نیست — فقط کاربر
            # «admin» که هنگام نصب ساخته می‌شود این دسترسی را دارد.
            raise ValueError("نقش superadmin را نمی‌توان از این طریق اختصاص داد")

        # سایت‌هایی از فهرست که از قبل همین انتصاب را دارند (بی‌صدا نادیده گرفته می‌شوند، نه خطای
        # Unique Constraint) تا ارسال دوباره‌ی فهرست سایت‌ها بی‌خطر باشد
        existing_result = await self.db.execute(
            select(UserRole.site_id).where(
                UserRole.user_id == user_id,
                UserRole.role_id == payload.role_id,
                UserRole.site_id.in_(payload.site_ids),
            )
        )
        already_assigned = {row[0] for row in existing_result.all()}

        # ساخت یک ردیف UserRole برای هر سایت جدید
        created: list[UserRole] = []
        for site_id in payload.site_ids:
            if site_id in already_assigned:
                continue
            user_role = UserRole(user_id=user_id, role_id=payload.role_id, site_id=site_id)
            self.db.add(user_role)
            created.append(user_role)

        await self.db.commit()
        for user_role in created:
            await self.db.refresh(user_role)  # بارگذاری id و مقادیر نهایی پس از commit
        return created

    async def remove_role_assignment(self, user_role_id: int) -> bool:
        """یک انتصاب نقش را حذف می‌کند؛ خروجی: True در صورت حذف، False اگر وجود نداشت."""
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
        نقش را به فهرست employee_ids یا همه‌ی پرسنل فعال یک سایت/واحد اختصاص می‌دهد؛ حساب User پرسنل در صورت نبود ساخته می‌شود.
        انتصاب هرگز سراسری نیست: site_id فیلتر (در صورت وجود) یا سایت خودِ هر پرسنل روی انتصاب ذخیره می‌شود.
        خروجی: dict شامل assigned_count، already_had_count، not_found_count و total_matched. خطا: ValueError.
        """
        role = await self.db.get(Role, role_id)
        if role is None:
            raise ValueError("نقش پیدا نشد")
        if role.name == "superadmin":
            raise ValueError("نقش superadmin را نمی‌توان از این طریق اختصاص داد")

        # انتخاب پرسنل هدف: فهرست مستقیم یا فیلتر سایت/واحد (فقط پرسنل فعال)
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

        not_found_count = len(employee_ids) - len(employees) if employee_ids else 0  # idهایی که پرسنلی برایشان پیدا نشد

        user_repo = UserRepository(self.db)

        assigned_count = 0
        already_had_count = 0
        # برای هر پرسنل: ساخت/یافتن حساب، بررسی انتصاب تکراری و افزودن انتصاب جدید
        for employee in employees:
            # سایت انتصاب: site_id فیلتر در صورت وجود، وگرنه سایت خودِ پرسنل (هرگز None/سراسری)
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

    async def get_access_overview(self, accessible_site_ids: set[int] | None = None) -> list[dict]:
        """
        فهرست پرسنلی که نقش سازمانی (به‌جز superadmin) و/یا سرپرستی واحد دارند، برای جدول «نمای کلی دسترسی‌ها».
        accessible_site_ids: اگر داده شود، فقط پرسنلی که سایتشان در این مجموعه است برگردانده می‌شوند (None = همه).
        خروجی: لیست dict مطابق AccessOverviewEntry، مرتب بر اساس نام و نام خانوادگی.
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

        relevant_user_ids = set(roles_by_user) | set(depts_by_user)  # کاربرانی که حداقل یک نقش یا سرپرستی دارند
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

        # ۵. ساخت ردیف خروجی برای هر پرسنل (با اعمال محدودیت سایت)
        overview: list[dict] = []
        for user_id, employee_id, first_name, last_name, personnel_code, emp_site_id in rows:
            if accessible_site_ids is not None and emp_site_id not in accessible_site_ids:
                continue
            # نقش‌ها و سرپرستی‌هایی که به سایت‌های خارج از اختیار بیننده مربوط‌اند نمایش داده نمی‌شوند
            role_entries = [
                {"role_name": name, "site_name": site_name_by_id.get(sid) if sid else None}
                for sid, name in roles_by_user.get(user_id, [])
                if accessible_site_ids is None or sid is None or sid in accessible_site_ids
            ]
            dept_entries = [
                {"id": did, "name": dname, "site_name": site_name_by_id.get(dsid, "")}
                for did, dname, dsid in depts_by_user.get(user_id, [])
                if accessible_site_ids is None or dsid in accessible_site_ids
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

    # ---------- جابه‌جایی پرسنل بین سایت‌ها ----------

    async def list_site_transfers(
        self, accessible_site_ids: set[int] | None, pending_only: bool = True
    ) -> list[dict]:
        """
        جابه‌جایی‌های ثبت‌شده توسط Sync را با نقش‌ها و سرپرستی‌های فعلی هر نفر برمی‌گرداند (جدیدترین اول).
        accessible_site_ids: فقط جابه‌جایی‌هایی که سایت مبدأ یا مقصدشان در این مجموعه است (None = همه).
        pending_only: فقط موارد بازبینی‌نشده. خروجی: لیست dict مطابق SiteTransferOut.
        """
        query = (
            select(SiteTransfer, Employee)
            .join(Employee, Employee.id == SiteTransfer.employee_id)
            .order_by(SiteTransfer.transferred_at.desc())
        )
        if pending_only:
            query = query.where(SiteTransfer.reviewed_at.is_(None))
        pairs = (await self.db.execute(query)).all()
        if accessible_site_ids is not None:
            pairs = [
                (t, e) for t, e in pairs if t.from_site_id in accessible_site_ids or t.to_site_id in accessible_site_ids
            ]
        if not pairs:
            return []

        # حساب کاربری فعلی هر پرسنل
        employee_ids = {e.id for _, e in pairs}
        user_rows = await self.db.execute(select(User.employee_id, User.id).where(User.employee_id.in_(employee_ids)))
        user_by_employee = dict(user_rows.all())
        user_ids = set(user_by_employee.values())

        # نقش‌ها و سرپرستی‌های فعلی این کاربران
        roles_by_user: dict[int, list[tuple[int | None, str]]] = {}
        depts_by_user: dict[int, list[tuple[str, int]]] = {}
        if user_ids:
            role_rows = await self.db.execute(
                select(UserRole.user_id, UserRole.site_id, Role.name)
                .join(Role, Role.id == UserRole.role_id)
                .where(UserRole.user_id.in_(user_ids), Role.name != "superadmin")
            )
            for uid, sid, name in role_rows.all():
                roles_by_user.setdefault(uid, []).append((sid, name))
            dept_rows = await self.db.execute(
                select(Department.supervisor_user_id, Department.name, Department.site_id).where(
                    Department.supervisor_user_id.in_(user_ids)
                )
            )
            for uid, dname, dsid in dept_rows.all():
                depts_by_user.setdefault(uid, []).append((dname, dsid))

        # نام سایت‌ها
        site_rows = await self.db.execute(select(Site.id, Site.name))
        site_name = dict(site_rows.all())

        # مسئولیت‌های غیرنقشی که به پرسنل (نه حساب کاربری) وصل‌اند
        other_by_employee = await self._other_site_assignments(employee_ids)

        out: list[dict] = []
        for transfer, employee in pairs:
            uid = user_by_employee.get(employee.id)
            # نقش‌ها و سرپرستی‌های سایت‌های خارج از اختیار بیننده نمایش داده نمی‌شوند
            roles = [
                {
                    "role_name": name,
                    "site_name": site_name.get(sid) if sid else None,
                    "is_old_site": sid is not None and sid == transfer.from_site_id,
                }
                for sid, name in roles_by_user.get(uid, [])
                if accessible_site_ids is None or sid is None or sid in accessible_site_ids
            ]
            out.append(
                {
                    "id": transfer.id,
                    "employee_id": employee.id,
                    "personnel_code": transfer.personnel_code,
                    "first_name": employee.first_name,
                    "last_name": employee.last_name,
                    "site_id": employee.site_id,
                    "from_site_name": site_name.get(transfer.from_site_id),
                    "to_site_name": site_name.get(transfer.to_site_id),
                    "transferred_at": transfer.transferred_at,
                    "reviewed_at": transfer.reviewed_at,
                    "has_user": uid is not None,
                    "roles": roles,
                    "old_site_departments": [
                        dname for dname, dsid in depts_by_user.get(uid, []) if dsid == transfer.from_site_id
                    ],
                    "other_assignments": [
                        label for label, sid in other_by_employee.get(employee.id, []) if sid == transfer.from_site_id
                    ],
                }
            )
        return out

    async def _other_site_assignments(self, employee_ids: set[int]) -> dict[int, list[tuple[str, int]]]:
        """
        مسئولیت‌های وابسته به سایت که مستقیماً به پرسنل وصل‌اند (نه به نقش): مسئول نیروی انسانی مرخصی،
        تأییدکننده دستی مرخصی یک واحد، مدیر ارزیابی و سرشیفت. خروجی: «شناسه پرسنل → [(برچسب، شناسه سایت)]».
        """
        from app.models.evaluation import EvaluationManager, EvaluationShiftLead
        from app.models.leave_request import LeaveRequestApprover, LeaveRequestHrOfficer

        found: dict[int, list[tuple[str, int]]] = {}
        if not employee_ids:
            return found
        rows = await self.db.execute(
            select(LeaveRequestHrOfficer.employee_id, LeaveRequestHrOfficer.site_id).where(
                LeaveRequestHrOfficer.employee_id.in_(employee_ids)
            )
        )
        for eid, sid in rows.all():
            found.setdefault(eid, []).append(("مسئول نیروی انسانی (مرخصی)", sid))
        rows = await self.db.execute(
            select(LeaveRequestApprover.approver_employee_id, Department.name, Department.site_id)
            .join(Department, Department.id == LeaveRequestApprover.department_id)
            .where(LeaveRequestApprover.approver_employee_id.in_(employee_ids))
        )
        for eid, dname, sid in rows.all():
            found.setdefault(eid, []).append((f"تأییدکننده مرخصی واحد {dname}", sid))
        rows = await self.db.execute(
            select(EvaluationManager.employee_id, EvaluationManager.site_id).where(
                EvaluationManager.employee_id.in_(employee_ids)
            )
        )
        for eid, sid in rows.all():
            found.setdefault(eid, []).append(("مدیر ارزیابی عملکرد", sid))
        rows = await self.db.execute(
            select(EvaluationShiftLead.employee_id, Department.name, Department.site_id)
            .join(Department, Department.id == EvaluationShiftLead.department_id)
            .where(EvaluationShiftLead.employee_id.in_(employee_ids))
        )
        for eid, dname, sid in rows.all():
            found.setdefault(eid, []).append((f"سرشیفت واحد {dname}", sid))
        return found

    async def mark_site_transfer_reviewed(
        self, transfer_id: int, reviewer_id: int, accessible_site_ids: set[int] | None
    ) -> bool:
        """
        یک جابه‌جایی را «بازبینی‌شده» علامت می‌زند تا از فهرست موارد نیازمند بررسی خارج شود.
        خروجی False یعنی مورد پیدا نشد یا خارج از سایت‌های مجاز کاربر است.
        """
        transfer = await self.db.get(SiteTransfer, transfer_id)
        if transfer is None:
            return False
        if accessible_site_ids is not None and not (
            transfer.from_site_id in accessible_site_ids or transfer.to_site_id in accessible_site_ids
        ):
            return False
        if transfer.reviewed_at is None:
            transfer.reviewed_at = datetime.now(timezone.utc)
            transfer.reviewed_by_user_id = reviewer_id
            await self.db.commit()
        return True

    # ---------- مدیریت خودِ نقش‌ها و مجوزها (پنل مدیریت نقش/مجوز) ----------

    async def list_permissions(self) -> list[Permission]:
        """
        همه‌ی مجوزهای موجود مرتب بر اساس code، برای چک‌باکس‌های صفحه‌ی ساخت/ویرایش نقش.
        مجوزها در کد تعریف می‌شوند (require_permission)؛ پنل فقط از مجوزهای موجود نقش جدید می‌سازد.
        """
        result = await self.db.execute(select(Permission).order_by(Permission.code))
        return list(result.scalars().all())

    async def get_role_detail(self, role_id: int) -> Role | None:
        """نقش را همراه با RolePermissionها و Permission هر کدام (eager load) برمی‌گرداند؛ اگر نبود None."""
        result = await self.db.execute(
            select(Role)
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
            .where(Role.id == role_id)
        )
        return result.scalar_one_or_none()

    async def create_role(self, payload: RoleUpsertIn) -> Role:
        """
        نقش غیرسیستمی جدید با مجوزهای معتبر از payload.permission_ids می‌سازد (idهای نامعتبر نادیده گرفته می‌شوند).
        خروجی: جزئیات نقش. خطا: ValueError برای نام رزرو «superadmin» یا نام تکراری.
        """
        if payload.name == "superadmin":
            raise ValueError("این نام رزرو شده است")
        existing = await self.db.execute(select(Role).where(Role.name == payload.name))
        if existing.scalar_one_or_none() is not None:
            raise ValueError("نقشی با همین نام از قبل وجود دارد")

        role = Role(name=payload.name, description=payload.description, is_system=False)
        self.db.add(role)
        await self.db.flush()  # برای گرفتن role.id، قبل از commit نهایی

        # افزودن فقط مجوزهایی که واقعاً در جدول permissions وجود دارند
        if payload.permission_ids:
            result = await self.db.execute(select(Permission.id).where(Permission.id.in_(payload.permission_ids)))
            valid_ids = {row[0] for row in result.all()}
            for permission_id in valid_ids:
                self.db.add(RolePermission(role_id=role.id, permission_id=permission_id))

        await self.db.commit()
        return await self.get_role_detail(role.id)

    async def update_role(self, role_id: int, payload: RoleUpsertIn) -> Role | None:
        """
        نام، توضیح و مجوزهای نقش را به‌روزرسانی می‌کند (نقش‌های is_system هم قابل ویرایش‌اند).
        خروجی: جزئیات نقش، یا None اگر نقش نبود. خطا: ValueError برای superadmin یا نام تکراری.
        """
        role = await self.db.get(Role, role_id)
        if role is None:
            return None
        # superadmin قابل ویرایش نیست، چون منطق منع انتصاب نقش همین نام را چک می‌کند
        if role.name == "superadmin":
            raise ValueError("نقش superadmin قابل ویرایش نیست")
        if payload.name != role.name:
            existing = await self.db.execute(select(Role).where(Role.name == payload.name, Role.id != role_id))
            if existing.scalar_one_or_none() is not None:
                raise ValueError("نقشی با همین نام از قبل وجود دارد")

        role.name = payload.name
        role.description = payload.description

        # جایگزینی کامل مجوزهای نقش با فهرست جدید (مطابق چک‌باکس‌های تیک‌خورده در فرانت‌اند)
        await self.db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        if payload.permission_ids:
            result = await self.db.execute(select(Permission.id).where(Permission.id.in_(payload.permission_ids)))
            valid_ids = {row[0] for row in result.all()}
            for permission_id in valid_ids:
                self.db.add(RolePermission(role_id=role_id, permission_id=permission_id))

        await self.db.commit()
        return await self.get_role_detail(role_id)

    async def delete_role(self, role_id: int) -> bool:
        """
        تعریف نقش را حذف می‌کند (نقش‌های is_system هم قابل حذف‌اند). خروجی: True در صورت حذف، False اگر نقش نبود.
        خطا: ValueError برای superadmin یا نقشی که هنوز به کاربری اختصاص دارد.
        """
        role = await self.db.get(Role, role_id)
        if role is None:
            return False
        # superadmin قابل حذف نیست، چون منطق منع انتصاب نقش همین نام را چک می‌کند
        if role.name == "superadmin":
            raise ValueError("نقش superadmin قابل حذف نیست")

        # نقشی که هنوز انتصاب دارد حذف نمی‌شود (با وجود ondelete=CASCADE) تا دسترسی کاربران بی‌صدا
        # از بین نرود؛ Admin باید ابتدا انتصاب‌ها را بردارد
        in_use = await self.db.execute(select(UserRole.id).where(UserRole.role_id == role_id).limit(1))
        if in_use.scalar_one_or_none() is not None:
            raise ValueError("این نقش هم‌اکنون به حداقل یک کاربر اختصاص دارد — ابتدا آن انتصاب‌ها را بردارید")

        await self.db.delete(role)
        await self.db.commit()
        return True
