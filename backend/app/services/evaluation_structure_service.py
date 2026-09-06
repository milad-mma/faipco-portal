"""
سرویس «ساختار ارزیابی عملکرد» - مدیریت انتساب‌های سرپرست/مدیر سایت/
سایر مدیران/سرشیفت، و منطق Resolve کردن «این پرسنل چه کسانی را می‌تواند
ارزیابی کند» بر اساس همان انتساب‌ها (نه بر اساس نقش/مجوز RBAC).

سلسله‌مراتب (طبق تصمیم صریح کاربر):
    مدیر سایت (چند نفر مجاز)  →  سرپرست‌های واحدهای همان سایت + سایر مدیران همان سایت
    سرپرست واحد               →  اگر آن واحد سرشیفت دارد: فقط سرشیفت‌ها
                                   وگرنه: همه پرسنل آن واحد
    سرشیفت واحد                →  فقط زیرمجموعه‌ی اختصاصی خودش
                                   (پرسنل بین سرشیفت‌های یک واحد تقسیم می‌شوند)

⚠️ یک نفر می‌تواند هم‌زمان چند نقش داشته باشد (مثلاً هم مدیر سایت هم
سرپرست یک واحد در سایت دیگر) - نتیجه نهایی، اجتماع (Union) همه اهداف
همه نقش‌هایش است. هیچ‌کس هرگز جزو اهداف خودش قرار نمی‌گیرد.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.evaluation_rules import resolve_evaluation_target_ids
from app.models.employee import Department, Employee
from app.models.evaluation import (
    EvaluationDepartmentSupervisor,
    EvaluationOtherManager,
    EvaluationShiftAssignment,
    EvaluationShiftLead,
    EvaluationSiteManager,
)
from app.repositories.user_repository import UserRepository


class EvaluationStructureError(Exception):
    pass


class EvaluationStructureService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- کمک‌تابع مشترک: اطمینان از وجود حساب کاربری ----------

    async def _ensure_employee_and_user(self, employee_id: int, expected_site_id: int | None = None) -> Employee:
        """
        پرسنل را برمی‌گرداند و مطمئن می‌شود حساب کاربری دارد (طبق تصمیم
        صریح کاربر: اگر نداشت، خودکار ساخته می‌شود - دقیقاً همان مکانیزم
        اولین ورود با کد پرسنلی/کد ملی).
        """
        employee = await self.db.get(Employee, employee_id)
        if employee is None:
            raise EvaluationStructureError("پرسنل موردنظر یافت نشد")
        if expected_site_id is not None and employee.site_id != expected_site_id:
            raise EvaluationStructureError("این پرسنل متعلق به این سایت نیست")
        await UserRepository(self.db).get_or_create_employee_user(employee)
        return employee

    # ---------- سرپرست واحد ----------

    async def set_department_supervisor(self, department_id: int, employee_id: int) -> EvaluationDepartmentSupervisor:
        department = await self.db.get(Department, department_id)
        if department is None:
            raise EvaluationStructureError("واحد سازمانی موردنظر یافت نشد")
        await self._ensure_employee_and_user(employee_id, expected_site_id=department.site_id)

        result = await self.db.execute(
            select(EvaluationDepartmentSupervisor).where(
                EvaluationDepartmentSupervisor.department_id == department_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.employee_id = employee_id
        else:
            existing = EvaluationDepartmentSupervisor(department_id=department_id, employee_id=employee_id)
            self.db.add(existing)
        await self.db.commit()
        await self.db.refresh(existing)
        return existing

    async def remove_department_supervisor(self, department_id: int) -> None:
        result = await self.db.execute(
            select(EvaluationDepartmentSupervisor).where(
                EvaluationDepartmentSupervisor.department_id == department_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            await self.db.delete(existing)
            await self.db.commit()

    # ---------- مدیر سایت ----------

    async def add_site_manager(self, site_id: int, employee_id: int) -> EvaluationSiteManager:
        await self._ensure_employee_and_user(employee_id, expected_site_id=site_id)

        result = await self.db.execute(
            select(EvaluationSiteManager).where(
                EvaluationSiteManager.site_id == site_id, EvaluationSiteManager.employee_id == employee_id
            )
        )
        if result.scalar_one_or_none() is not None:
            raise EvaluationStructureError("این پرسنل قبلاً به‌عنوان مدیر این سایت ثبت شده است")

        manager = EvaluationSiteManager(site_id=site_id, employee_id=employee_id)
        self.db.add(manager)
        await self.db.commit()
        await self.db.refresh(manager)
        return manager

    async def remove_site_manager(self, manager_id: int) -> None:
        manager = await self.db.get(EvaluationSiteManager, manager_id)
        if manager is not None:
            await self.db.delete(manager)
            await self.db.commit()

    # ---------- سایر مدیران ----------

    async def add_other_manager(self, site_id: int, employee_id: int) -> EvaluationOtherManager:
        await self._ensure_employee_and_user(employee_id, expected_site_id=site_id)

        result = await self.db.execute(
            select(EvaluationOtherManager).where(
                EvaluationOtherManager.site_id == site_id, EvaluationOtherManager.employee_id == employee_id
            )
        )
        if result.scalar_one_or_none() is not None:
            raise EvaluationStructureError("این پرسنل قبلاً به این فهرست اضافه شده است")

        manager = EvaluationOtherManager(site_id=site_id, employee_id=employee_id)
        self.db.add(manager)
        await self.db.commit()
        await self.db.refresh(manager)
        return manager

    async def remove_other_manager(self, manager_id: int) -> None:
        manager = await self.db.get(EvaluationOtherManager, manager_id)
        if manager is not None:
            await self.db.delete(manager)
            await self.db.commit()

    # ---------- سرشیفت واحد ----------

    async def add_shift_lead(self, department_id: int, employee_id: int) -> EvaluationShiftLead:
        department = await self.db.get(Department, department_id)
        if department is None:
            raise EvaluationStructureError("واحد سازمانی موردنظر یافت نشد")

        employee = await self.db.get(Employee, employee_id)
        if employee is None:
            raise EvaluationStructureError("پرسنل موردنظر یافت نشد")
        if employee.department_id != department_id:
            raise EvaluationStructureError("سرشیفت باید از پرسنل همان واحد انتخاب شود")

        # ⚠️ یک پرسنل که خودش زیرمجموعه یک سرشیفت دیگر است، نمی‌تواند
        # هم‌زمان خودش هم سرشیفت باشد - وگرنه می‌شد سرشیفتی که هم‌زمان
        # زیرِ سرشیفت دیگری در همان واحد است (تناقض سلسله‌مراتبی).
        assignment_result = await self.db.execute(
            select(EvaluationShiftAssignment).where(EvaluationShiftAssignment.employee_id == employee_id)
        )
        if assignment_result.scalar_one_or_none() is not None:
            raise EvaluationStructureError(
                "این پرسنل هم‌اکنون زیرمجموعه یک سرشیفت دیگر است - ابتدا آن انتساب را حذف کنید"
            )

        await self._ensure_employee_and_user(employee_id, expected_site_id=department.site_id)

        result = await self.db.execute(
            select(EvaluationShiftLead).where(
                EvaluationShiftLead.department_id == department_id, EvaluationShiftLead.employee_id == employee_id
            )
        )
        if result.scalar_one_or_none() is not None:
            raise EvaluationStructureError("این پرسنل قبلاً سرشیفت همین واحد ثبت شده است")

        shift_lead = EvaluationShiftLead(department_id=department_id, employee_id=employee_id)
        self.db.add(shift_lead)
        await self.db.commit()
        await self.db.refresh(shift_lead)
        return shift_lead

    async def remove_shift_lead(self, shift_lead_id: int) -> None:
        """
        ⚠️ حذف یک سرشیفت، انتساب‌های پرسنل زیرمجموعه‌اش را هم پاک می‌کند
        (ondelete=CASCADE در دیتابیس) - یعنی آن پرسنل تا وقتی به سرشیفت
        دیگری اختصاص داده نشوند، اصلاً کسی ارزیابی‌شان نمی‌کند (نه سرپرست
        مستقیم، چون تا وقتی حداقل یک سرشیفت برای آن واحد باقی مانده،
        سرپرست فقط سرشیفت‌ها را می‌بیند نه پرسنل عادی را).
        """
        shift_lead = await self.db.get(EvaluationShiftLead, shift_lead_id)
        if shift_lead is not None:
            await self.db.delete(shift_lead)
            await self.db.commit()

    # ---------- تعیین زیرمجموعه هر سرشیفت ----------

    async def set_shift_assignment(self, employee_id: int, shift_lead_id: int) -> EvaluationShiftAssignment:
        shift_lead = await self.db.get(EvaluationShiftLead, shift_lead_id)
        if shift_lead is None:
            raise EvaluationStructureError("سرشیفت موردنظر یافت نشد")

        employee = await self.db.get(Employee, employee_id)
        if employee is None:
            raise EvaluationStructureError("پرسنل موردنظر یافت نشد")
        if employee.department_id != shift_lead.department_id:
            raise EvaluationStructureError("این پرسنل عضو همان واحدِ این سرشیفت نیست")
        if employee_id == shift_lead.employee_id:
            raise EvaluationStructureError("سرشیفت نمی‌تواند زیرمجموعه خودش باشد")

        # ⚠️ سرشیفت‌های یک واحد هرگز نباید بتوانند یکدیگر را ارزیابی کنند
        shift_lead_check = await self.db.execute(
            select(EvaluationShiftLead.id).where(
                EvaluationShiftLead.department_id == shift_lead.department_id,
                EvaluationShiftLead.employee_id == employee_id,
            )
        )
        if shift_lead_check.scalar_one_or_none() is not None:
            raise EvaluationStructureError(
                "این پرسنل خودش سرشیفت همین واحد است - سرشیفت‌ها نمی‌توانند زیرمجموعه هم باشند"
            )

        result = await self.db.execute(
            select(EvaluationShiftAssignment).where(EvaluationShiftAssignment.employee_id == employee_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.shift_lead_id = shift_lead_id
        else:
            existing = EvaluationShiftAssignment(employee_id=employee_id, shift_lead_id=shift_lead_id)
            self.db.add(existing)
        await self.db.commit()
        await self.db.refresh(existing)
        return existing

    async def remove_shift_assignment(self, employee_id: int) -> None:
        result = await self.db.execute(
            select(EvaluationShiftAssignment).where(EvaluationShiftAssignment.employee_id == employee_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            await self.db.delete(existing)
            await self.db.commit()

    # ---------- نمایش کامل ساختار یک سایت ----------

    async def get_site_structure(self, site_id: int) -> dict:
        site_managers_result = await self.db.execute(
            select(EvaluationSiteManager).where(EvaluationSiteManager.site_id == site_id)
        )
        site_managers = site_managers_result.scalars().all()

        other_managers_result = await self.db.execute(
            select(EvaluationOtherManager).where(EvaluationOtherManager.site_id == site_id)
        )
        other_managers = other_managers_result.scalars().all()

        departments_result = await self.db.execute(select(Department).where(Department.site_id == site_id))
        departments = departments_result.scalars().all()

        department_entries = []
        for department in departments:
            supervisor_result = await self.db.execute(
                select(EvaluationDepartmentSupervisor).where(
                    EvaluationDepartmentSupervisor.department_id == department.id
                )
            )
            supervisor = supervisor_result.scalar_one_or_none()

            shift_leads_result = await self.db.execute(
                select(EvaluationShiftLead).where(EvaluationShiftLead.department_id == department.id)
            )
            shift_leads = shift_leads_result.scalars().all()

            shift_lead_ids = [sl.id for sl in shift_leads]
            shift_assignments = []
            if shift_lead_ids:
                assignments_result = await self.db.execute(
                    select(EvaluationShiftAssignment).where(
                        EvaluationShiftAssignment.shift_lead_id.in_(shift_lead_ids)
                    )
                )
                shift_assignments = assignments_result.scalars().all()

            department_entries.append(
                {
                    "id": department.id,
                    "name": department.name,
                    "code": department.code,
                    "supervisor": supervisor.employee if supervisor else None,
                    "shift_leads": shift_leads,
                    "shift_assignments": shift_assignments,
                }
            )

        return {
            "site_id": site_id,
            "site_managers": site_managers,
            "other_managers": other_managers,
            "departments": department_entries,
        }

    # ---------- Resolve: این پرسنل چه کسانی را می‌تواند ارزیابی کند ----------

    async def get_evaluation_targets(self, evaluator_employee_id: int) -> dict:
        site_manager_result = await self.db.execute(
            select(EvaluationSiteManager.site_id).where(
                EvaluationSiteManager.employee_id == evaluator_employee_id
            )
        )
        site_ids_as_manager = [row[0] for row in site_manager_result.all()]

        supervisor_result = await self.db.execute(
            select(EvaluationDepartmentSupervisor.department_id).where(
                EvaluationDepartmentSupervisor.employee_id == evaluator_employee_id
            )
        )
        department_ids_as_supervisor = [row[0] for row in supervisor_result.all()]

        shift_lead_result = await self.db.execute(
            select(EvaluationShiftLead.id).where(EvaluationShiftLead.employee_id == evaluator_employee_id)
        )
        shift_lead_ids = [row[0] for row in shift_lead_result.all()]

        # داده خام موردنیاز الگوریتم خالص (resolve_evaluation_target_ids) -
        # فقط برای همان site_id/department_id هایی که واقعاً نیاز است
        # می‌خوانیم، نه کل جدول‌ها.
        department_supervisors_by_site: dict[int, list[int]] = {}
        other_managers_by_site: dict[int, list[int]] = {}
        for site_id in site_ids_as_manager:
            dept_supervisors_result = await self.db.execute(
                select(EvaluationDepartmentSupervisor.employee_id)
                .join(Department, Department.id == EvaluationDepartmentSupervisor.department_id)
                .where(Department.site_id == site_id)
            )
            department_supervisors_by_site[site_id] = [row[0] for row in dept_supervisors_result.all()]

            other_managers_result = await self.db.execute(
                select(EvaluationOtherManager.employee_id).where(EvaluationOtherManager.site_id == site_id)
            )
            other_managers_by_site[site_id] = [row[0] for row in other_managers_result.all()]

        shift_lead_employees_by_department: dict[int, list[int]] = {}
        all_employees_by_department: dict[int, list[int]] = {}
        for department_id in department_ids_as_supervisor:
            shift_lead_employees_result = await self.db.execute(
                select(EvaluationShiftLead.employee_id).where(EvaluationShiftLead.department_id == department_id)
            )
            shift_lead_employees_by_department[department_id] = [
                row[0] for row in shift_lead_employees_result.all()
            ]

            employees_result = await self.db.execute(
                select(Employee.id).where(
                    Employee.department_id == department_id, Employee.id != evaluator_employee_id
                )
            )
            all_employees_by_department[department_id] = [row[0] for row in employees_result.all()]

        shift_assignments_by_shift_lead: dict[int, list[int]] = {}
        for shift_lead_id in shift_lead_ids:
            assignments_result = await self.db.execute(
                select(EvaluationShiftAssignment.employee_id).where(
                    EvaluationShiftAssignment.shift_lead_id == shift_lead_id
                )
            )
            shift_assignments_by_shift_lead[shift_lead_id] = [row[0] for row in assignments_result.all()]

        target_ids = resolve_evaluation_target_ids(
            evaluator_employee_id=evaluator_employee_id,
            site_manager_of_sites=site_ids_as_manager,
            department_supervisor_of_departments=department_ids_as_supervisor,
            shift_lead_of_shift_lead_ids=shift_lead_ids,
            department_supervisors_by_site=department_supervisors_by_site,
            other_managers_by_site=other_managers_by_site,
            shift_lead_employees_by_department=shift_lead_employees_by_department,
            all_employees_by_department=all_employees_by_department,
            shift_assignments_by_shift_lead=shift_assignments_by_shift_lead,
        )

        targets: list[Employee] = []
        if target_ids:
            targets_result = await self.db.execute(select(Employee).where(Employee.id.in_(target_ids)))
            targets = list(targets_result.scalars().all())

        return {
            "is_site_manager": bool(site_ids_as_manager),
            "is_department_supervisor": bool(department_ids_as_supervisor),
            "is_shift_lead": bool(shift_lead_ids),
            "targets": targets,
        }
