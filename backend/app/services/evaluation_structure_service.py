"""
سرویس «ساختار ارزیابی عملکرد» - مدیریت انتساب‌های سرپرست/مدیر/سرشیفت،
و منطق Resolve کردن «این پرسنل چه کسانی را می‌تواند ارزیابی کند» بر
اساس همان انتساب‌ها (نه بر اساس نقش/مجوز RBAC).

سلسله‌مراتب (بازطراحی‌شده، منعطف - طبق بازخورد صریح کاربر):
    مدیر (هر تعداد، هر عنوانی مثل «مدیر سایت»/«مدیر تولید»)
                                →  ارزیابی: هر لیستی از افراد که صریحاً
                                   به او تخصیص داده شده - نه یک قانون
                                   خودکار؛ چون چارت سازمانی واقعی ممکن
                                   است چندسطحی باشد (مثلاً یک مدیر میانی
                                   فقط بخشی از سرپرست‌ها را ارزیابی کند)،
                                   یا نیاز باشد یک فرد خاص از هر واحد/سایتی
                                   مستقیم به یک مدیر تخصیص داده شود.
    سرپرست واحد                 →  اگر آن واحد سرشیفت دارد: فقط سرشیفت‌ها
                                   وگرنه: همه پرسنل آن واحد
    سرشیفت واحد                  →  فقط زیرمجموعه‌ی اختصاصی خودش
                                   (پرسنل بین سرشیفت‌های یک واحد تقسیم می‌شوند)

⚠️ یک نفر می‌تواند هم‌زمان چند نقش داشته باشد (مثلاً هم مدیر هم سرپرست
یک واحد) - نتیجه نهایی، اجتماع (Union) همه اهداف همه نقش‌هایش است.
هیچ‌کس هرگز جزو اهداف خودش قرار نمی‌گیرد.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.evaluation_rules import resolve_evaluation_target_ids
from app.models.employee import Department, Employee
from app.models.evaluation import (
    EvaluationDepartmentSupervisor,
    EvaluationManager,
    EvaluationManagerAssignment,
    EvaluationShiftAssignment,
    EvaluationShiftLead,
)
from app.models.site import Site
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
        result = await self.db.execute(
            select(EvaluationDepartmentSupervisor)
            .options(selectinload(EvaluationDepartmentSupervisor.employee))
            .where(EvaluationDepartmentSupervisor.department_id == department_id)
        )
        return result.scalar_one()

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

    # ---------- مدیر (عمومی - سایت، تولید، فنی، هرچی) ----------

    async def add_manager(self, site_id: int, employee_id: int, title: str | None) -> EvaluationManager:
        await self._ensure_employee_and_user(employee_id, expected_site_id=site_id)

        result = await self.db.execute(
            select(EvaluationManager).where(
                EvaluationManager.site_id == site_id, EvaluationManager.employee_id == employee_id
            )
        )
        if result.scalar_one_or_none() is not None:
            raise EvaluationStructureError("این پرسنل قبلاً به‌عنوان مدیر این سایت ثبت شده است")

        manager = EvaluationManager(site_id=site_id, employee_id=employee_id, title=title)
        self.db.add(manager)
        await self.db.flush()  # برای پرشدن manager.id بدون Expire شدن (برخلاف commit)
        manager_id = manager.id
        await self.db.commit()
        return await self._get_manager_with_targets(manager_id)

    async def update_manager_title(self, manager_id: int, title: str | None) -> EvaluationManager:
        manager = await self.db.get(EvaluationManager, manager_id)
        if manager is None:
            raise EvaluationStructureError("مدیر موردنظر یافت نشد")
        manager.title = title
        await self.db.commit()
        return await self._get_manager_with_targets(manager_id)

    async def remove_manager(self, manager_id: int) -> None:
        manager = await self.db.get(EvaluationManager, manager_id)
        if manager is not None:
            await self.db.delete(manager)  # CASCADE - انتساب‌های اهداف این مدیر هم پاک می‌شوند
            await self.db.commit()

    async def _get_manager_with_targets(self, manager_id: int) -> EvaluationManager:
        result = await self.db.execute(
            select(EvaluationManager)
            .options(
                selectinload(EvaluationManager.employee),
                selectinload(EvaluationManager.assignments).selectinload(EvaluationManagerAssignment.target_employee),
            )
            .where(EvaluationManager.id == manager_id)
        )
        return result.scalar_one()

    # ---------- اهداف هر مدیر (کاملاً دستی - جایگزین «سرپرست‌های خودکار» و «سایر مدیران») ----------

    async def add_manager_target(self, manager_id: int, target_employee_id: int) -> EvaluationManager:
        """
        ⚠️ برخلاف طراحی قبلی، هدف می‌تواند *هر* پرسنلی باشد - سرپرست یک
        واحد، مدیر دیگر، یا حتی یک فرد عادی از هر واحد/سایتی (طبق درخواست
        صریح کاربر) - هیچ محدودیتی روی site_id هدف اعمال نمی‌شود، چون
        ممکن است لازم باشد یک فرد از سایت دیگر هم مستقیم به این مدیر
        تخصیص داده شود.
        """
        manager = await self.db.get(EvaluationManager, manager_id)
        if manager is None:
            raise EvaluationStructureError("مدیر موردنظر یافت نشد")
        target_employee = await self.db.get(Employee, target_employee_id)
        if target_employee is None:
            raise EvaluationStructureError("پرسنل هدف یافت نشد")
        if target_employee_id == manager.employee_id:
            raise EvaluationStructureError("یک مدیر نمی‌تواند خودش را هدف بگیرد")

        result = await self.db.execute(
            select(EvaluationManagerAssignment).where(
                EvaluationManagerAssignment.manager_id == manager_id,
                EvaluationManagerAssignment.target_employee_id == target_employee_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise EvaluationStructureError("این فرد قبلاً به این مدیر تخصیص داده شده است")

        # ⚠️ طبق درخواست صریح: هر فرد فقط می‌تواند هم‌زمان زیر ارزیابی
        # یک مدیر باشد - اگر از قبل به مدیر دیگری تخصیص داده شده، ابتدا
        # باید از همان‌جا حذف شود.
        existing_elsewhere_result = await self.db.execute(
            select(EvaluationManagerAssignment)
            .options(selectinload(EvaluationManagerAssignment.manager).selectinload(EvaluationManager.employee))
            .where(EvaluationManagerAssignment.target_employee_id == target_employee_id)
        )
        existing_elsewhere = existing_elsewhere_result.scalars().first()
        if existing_elsewhere is not None:
            other_manager_employee = existing_elsewhere.manager.employee
            raise EvaluationStructureError(
                f"این فرد هم‌اکنون تحت ارزیابی «{other_manager_employee.first_name} "
                f"{other_manager_employee.last_name}» است - ابتدا باید از فهرست آن مدیر حذف شود"
            )

        self.db.add(EvaluationManagerAssignment(manager_id=manager_id, target_employee_id=target_employee_id))
        await self.db.commit()
        return await self._get_manager_with_targets(manager_id)

    async def remove_manager_target(self, manager_id: int, target_employee_id: int) -> EvaluationManager:
        result = await self.db.execute(
            select(EvaluationManagerAssignment).where(
                EvaluationManagerAssignment.manager_id == manager_id,
                EvaluationManagerAssignment.target_employee_id == target_employee_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            await self.db.delete(existing)
            await self.db.commit()
        return await self._get_manager_with_targets(manager_id)

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
        await self.db.flush()
        shift_lead_id = shift_lead.id
        await self.db.commit()
        result = await self.db.execute(
            select(EvaluationShiftLead)
            .options(selectinload(EvaluationShiftLead.employee))
            .where(EvaluationShiftLead.id == shift_lead_id)
        )
        return result.scalar_one()

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
        refreshed_result = await self.db.execute(
            select(EvaluationShiftAssignment)
            .options(selectinload(EvaluationShiftAssignment.employee))
            .where(EvaluationShiftAssignment.employee_id == employee_id)
        )
        return refreshed_result.scalar_one()

    async def remove_shift_assignment(self, employee_id: int) -> None:
        result = await self.db.execute(
            select(EvaluationShiftAssignment).where(EvaluationShiftAssignment.employee_id == employee_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            await self.db.delete(existing)
            await self.db.commit()

    # ---------- نمایش کامل ساختار یک سایت ----------

    # ---------- کاندیدهای انتخاب برای «افزودن به فهرست یک مدیر» ----------

    async def get_manager_candidates(self, site_id: int) -> list[dict]:
        """
        فهرست همه پرسنل این سایت، به‌همراه دو اطلاعه کمکی برای انتخابگر
        فرانت‌اند:
            - آیا سرپرست یک واحد است (و کدام واحد) - برای بخش «سرپرستان
              بدون مدیر»
            - اگر از قبل زیر ارزیابی یک مدیر دیگر است، نام آن مدیر - تا
              فرانت‌اند بتواند این افراد را غیرفعال/برچسب‌گذاری کند
              («تحت ارزیابی فلانی») به‌جای اینکه کاملاً پنهانشان کند.
        """
        employees_result = await self.db.execute(select(Employee).where(Employee.site_id == site_id))
        employees = employees_result.scalars().all()

        supervisors_result = await self.db.execute(
            select(EvaluationDepartmentSupervisor.employee_id, Department.name)
            .join(Department, Department.id == EvaluationDepartmentSupervisor.department_id)
            .where(Department.site_id == site_id)
        )
        supervisor_department_name_by_employee_id = {row[0]: row[1] for row in supervisors_result.all()}

        assignments_result = await self.db.execute(
            select(EvaluationManagerAssignment.target_employee_id, Employee.first_name, Employee.last_name)
            .join(EvaluationManager, EvaluationManager.id == EvaluationManagerAssignment.manager_id)
            .join(Employee, Employee.id == EvaluationManager.employee_id)
        )
        evaluated_by_name_by_employee_id = {
            row[0]: f"{row[1]} {row[2]}" for row in assignments_result.all()
        }

        return [
            {
                "id": employee.id,
                "personnel_code": employee.personnel_code,
                "first_name": employee.first_name,
                "last_name": employee.last_name,
                "department_id": employee.department_id,
                "supervisor_department_name": supervisor_department_name_by_employee_id.get(employee.id),
                "evaluated_by_name": evaluated_by_name_by_employee_id.get(employee.id),
            }
            for employee in employees
        ]

    async def get_site_structure(self, site_id: int) -> dict:
        """
        ⚠️ همه Query های این متد عمداً با selectinload(...) رابطه‌ی
        employee (و مشابه) را از قبل بار می‌کنند - دسترسی به یک رابطه
        Lazy-load نشده در یک Session ناهمگام (Async)، بدون Greenlet فعال،
        خطای MissingGreenlet می‌دهد.
        """
        site = await self.db.get(Site, site_id)
        if site is None:
            raise EvaluationStructureError("سایت موردنظر یافت نشد")

        managers_result = await self.db.execute(
            select(EvaluationManager)
            .options(
                selectinload(EvaluationManager.employee),
                selectinload(EvaluationManager.assignments).selectinload(EvaluationManagerAssignment.target_employee),
            )
            .where(EvaluationManager.site_id == site_id)
        )
        managers = managers_result.scalars().all()

        departments_result = await self.db.execute(select(Department).where(Department.site_id == site_id))
        departments = departments_result.scalars().all()

        department_entries = []
        for department in departments:
            supervisor_result = await self.db.execute(
                select(EvaluationDepartmentSupervisor)
                .options(selectinload(EvaluationDepartmentSupervisor.employee))
                .where(EvaluationDepartmentSupervisor.department_id == department.id)
            )
            supervisor = supervisor_result.scalar_one_or_none()

            shift_leads_result = await self.db.execute(
                select(EvaluationShiftLead)
                .options(selectinload(EvaluationShiftLead.employee))
                .where(EvaluationShiftLead.department_id == department.id)
            )
            shift_leads = shift_leads_result.scalars().all()

            shift_lead_ids = [sl.id for sl in shift_leads]
            shift_assignments = []
            if shift_lead_ids:
                assignments_result = await self.db.execute(
                    select(EvaluationShiftAssignment)
                    .options(selectinload(EvaluationShiftAssignment.employee))
                    .where(EvaluationShiftAssignment.shift_lead_id.in_(shift_lead_ids))
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
            "site_name": site.name,
            "managers": managers,
            "departments": department_entries,
        }

    # ---------- Resolve: این پرسنل چه کسانی را می‌تواند ارزیابی کند ----------

    async def get_evaluation_targets(self, evaluator_employee_id: int) -> dict:
        manager_result = await self.db.execute(
            select(EvaluationManager.id).where(EvaluationManager.employee_id == evaluator_employee_id)
        )
        manager_ids = [row[0] for row in manager_result.all()]

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
        # فقط برای همان manager_id/department_id هایی که واقعاً نیاز است
        # می‌خوانیم، نه کل جدول‌ها.
        manager_targets_by_manager_id: dict[int, list[int]] = {}
        for manager_id in manager_ids:
            targets_result = await self.db.execute(
                select(EvaluationManagerAssignment.target_employee_id).where(
                    EvaluationManagerAssignment.manager_id == manager_id
                )
            )
            manager_targets_by_manager_id[manager_id] = [row[0] for row in targets_result.all()]

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
            manager_ids_of_evaluator=manager_ids,
            manager_targets_by_manager_id=manager_targets_by_manager_id,
            department_supervisor_of_departments=department_ids_as_supervisor,
            shift_lead_of_shift_lead_ids=shift_lead_ids,
            shift_lead_employees_by_department=shift_lead_employees_by_department,
            all_employees_by_department=all_employees_by_department,
            shift_assignments_by_shift_lead=shift_assignments_by_shift_lead,
        )

        targets: list[Employee] = []
        if target_ids:
            targets_result = await self.db.execute(select(Employee).where(Employee.id.in_(target_ids)))
            targets = list(targets_result.scalars().all())

        return {
            "is_manager": bool(manager_ids),
            "is_department_supervisor": bool(department_ids_as_supervisor),
            "is_shift_lead": bool(shift_lead_ids),
            "targets": targets,
        }
