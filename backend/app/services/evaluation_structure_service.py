"""
سرویس «ساختار ارزیابی عملکرد»: مدیریت انتساب‌های سرپرست/مدیر/سرشیفت، فهرست کاندیدها و
ساختار کامل سایت، و Resolve کردن «این پرسنل چه کسانی را می‌تواند ارزیابی کند» بر اساس همین
انتساب‌ها (نه نقش/مجوز RBAC).

سلسله‌مراتب:
    مدیر (هر تعداد، با هر عنوانی مثل «مدیر سایت»/«مدیر تولید»)
                                →  هر پرسنلی که صریحاً به او تخصیص داده شده
                                   (از هر واحد/سایتی؛ برای چارت‌های چندسطحی)
    سرپرست واحد                 →  اگر واحد سرشیفت دارد: سرشیفت‌ها + پرسنلِ بدون سرشیفت
                                   وگرنه: همه پرسنل آن واحد
    سرشیفت واحد                  →  فقط زیرمجموعه‌ی اختصاصی خودش
                                   (پرسنل بین سرشیفت‌های یک واحد تقسیم می‌شوند)

یک نفر می‌تواند هم‌زمان چند نقش داشته باشد؛ نتیجه نهایی اجتماع (Union) اهداف همه نقش‌هایش است.
هیچ‌کس جزو اهداف خودش قرار نمی‌گیرد.
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
    """خطای قابل نمایش به کاربر در عملیات ساختار ارزیابی."""
    pass


class EvaluationStructureService:
    """سرویس مدیریت ساختار ارزیابی و تعیین اهداف ارزیابی هر پرسنل."""

    def __init__(self, db: AsyncSession):
        """ورودی: نشست async دیتابیس."""
        self.db = db

    # ---------- کمک‌تابع مشترک: اطمینان از وجود حساب کاربری ----------

    async def _ensure_employee_and_user(self, employee_id: int, expected_site_id: int | None = None) -> Employee:
        """
        ورودی: شناسه پرسنل و (اختیاری) سایت مورد انتظار. پرسنل را برمی‌گرداند و اگر حساب کاربری
        نداشته باشد، با همان مکانیزم اولین ورود (کد پرسنلی/کد ملی) می‌سازد.
        اگر پرسنل نباشد یا متعلق به سایت دیگری باشد EvaluationStructureError.
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
        """
        سرپرست ارزیابی واحد را تعیین یا جایگزین می‌کند (پرسنل باید از همان سایت باشد).
        خروجی: رکورد سرپرست همراه employee؛ واحد/پرسنل نامعتبر: EvaluationStructureError.
        """
        department = await self.db.get(Department, department_id)
        if department is None:
            raise EvaluationStructureError("واحد سازمانی موردنظر یافت نشد")
        await self._ensure_employee_and_user(employee_id, expected_site_id=department.site_id)

        # اگر واحد سرپرست دارد جایگزین می‌شود، وگرنه رکورد جدید ساخته می‌شود
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
        # بارگذاری مجدد همراه employee برای خروجی
        result = await self.db.execute(
            select(EvaluationDepartmentSupervisor)
            .options(selectinload(EvaluationDepartmentSupervisor.employee))
            .where(EvaluationDepartmentSupervisor.department_id == department_id)
        )
        return result.scalar_one()

    async def remove_department_supervisor(self, department_id: int) -> None:
        """سرپرست ارزیابی واحد را (در صورت وجود) حذف می‌کند."""
        result = await self.db.execute(
            select(EvaluationDepartmentSupervisor).where(
                EvaluationDepartmentSupervisor.department_id == department_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            await self.db.delete(existing)
            await self.db.commit()

    # ---------- مدیر (عمومی: سایت، تولید، فنی و ...) ----------

    async def add_manager(self, site_id: int, employee_id: int, title: str | None) -> EvaluationManager:
        """
        پرسنلی از همین سایت را با عنوان اختیاری به‌عنوان مدیر ارزیابی ثبت می‌کند.
        خروجی: مدیر همراه اهداف؛ تکراری یا پرسنل نامعتبر: EvaluationStructureError.
        """
        await self._ensure_employee_and_user(employee_id, expected_site_id=site_id)

        # جلوگیری از ثبت تکراری مدیر در همین سایت
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
        """عنوان نمایشی مدیر را تغییر می‌دهد و مدیر را همراه اهداف برمی‌گرداند."""
        manager = await self.db.get(EvaluationManager, manager_id)
        if manager is None:
            raise EvaluationStructureError("مدیر موردنظر یافت نشد")
        manager.title = title
        await self.db.commit()
        return await self._get_manager_with_targets(manager_id)

    async def remove_manager(self, manager_id: int) -> None:
        """مدیر را (در صورت وجود) همراه اهدافش حذف می‌کند."""
        manager = await self.db.get(EvaluationManager, manager_id)
        if manager is not None:
            await self.db.delete(manager)  # CASCADE - انتساب‌های اهداف این مدیر هم پاک می‌شوند
            await self.db.commit()

    async def _get_manager_with_targets(self, manager_id: int) -> EvaluationManager:
        """مدیر را همراه employee و اهدافش (با selectinload) برای خروجی ManagerOut می‌خواند."""
        result = await self.db.execute(
            select(EvaluationManager)
            .options(
                selectinload(EvaluationManager.employee),
                selectinload(EvaluationManager.assignments).selectinload(EvaluationManagerAssignment.target_employee),
            )
            .where(EvaluationManager.id == manager_id)
        )
        return result.scalar_one()

    # ---------- اهداف هر مدیر (کاملاً دستی) ----------

    async def add_manager_target(self, manager_id: int, target_employee_id: int) -> EvaluationManager:
        """
        یک پرسنل را به فهرست ارزیابی‌شوندگان مدیر اضافه می‌کند؛ هدف می‌تواند هر پرسنلی از هر
        واحد/سایتی باشد (روی site_id هدف محدودیتی نیست). هر فرد فقط زیر یک مدیر می‌تواند باشد.
        خروجی: مدیر همراه اهداف؛ مدیر/هدف نامعتبر، خودِ مدیر یا تخصیص تکراری: EvaluationStructureError.
        """
        manager = await self.db.get(EvaluationManager, manager_id)
        if manager is None:
            raise EvaluationStructureError("مدیر موردنظر یافت نشد")
        target_employee = await self.db.get(Employee, target_employee_id)
        if target_employee is None:
            raise EvaluationStructureError("پرسنل هدف یافت نشد")
        if target_employee_id == manager.employee_id:
            raise EvaluationStructureError("یک مدیر نمی‌تواند خودش را هدف بگیرد")

        # تخصیص تکراری به همین مدیر
        result = await self.db.execute(
            select(EvaluationManagerAssignment).where(
                EvaluationManagerAssignment.manager_id == manager_id,
                EvaluationManagerAssignment.target_employee_id == target_employee_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise EvaluationStructureError("این فرد قبلاً به این مدیر تخصیص داده شده است")

        # هر فرد هم‌زمان فقط زیر ارزیابی یک مدیر است؛ اگر به مدیر دیگری تخصیص داده شده،
        # ابتدا باید از فهرست آن مدیر حذف شود
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
        """پرسنل را (در صورت وجود) از فهرست مدیر حذف می‌کند و مدیر را همراه اهداف برمی‌گرداند."""
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
        """
        پرسنلی از همان واحد را سرشیفت آن واحد می‌کند. پرسنلی که زیرمجموعه سرشیفت دیگری است یا
        از قبل سرشیفت همین واحد است مجاز نیست (EvaluationStructureError). خروجی: سرشیفت همراه employee.
        """
        department = await self.db.get(Department, department_id)
        if department is None:
            raise EvaluationStructureError("واحد سازمانی موردنظر یافت نشد")

        employee = await self.db.get(Employee, employee_id)
        if employee is None:
            raise EvaluationStructureError("پرسنل موردنظر یافت نشد")
        if employee.department_id != department_id:
            raise EvaluationStructureError("سرشیفت باید از پرسنل همان واحد انتخاب شود")

        # پرسنلی که زیرمجموعه یک سرشیفت است نمی‌تواند هم‌زمان سرشیفت باشد (تناقض سلسله‌مراتبی)
        assignment_result = await self.db.execute(
            select(EvaluationShiftAssignment).where(EvaluationShiftAssignment.employee_id == employee_id)
        )
        if assignment_result.scalar_one_or_none() is not None:
            raise EvaluationStructureError(
                "این پرسنل هم‌اکنون زیرمجموعه یک سرشیفت دیگر است - ابتدا آن انتساب را حذف کنید"
            )

        await self._ensure_employee_and_user(employee_id, expected_site_id=department.site_id)

        # جلوگیری از ثبت تکراری سرشیفت در همین واحد
        result = await self.db.execute(
            select(EvaluationShiftLead).where(
                EvaluationShiftLead.department_id == department_id, EvaluationShiftLead.employee_id == employee_id
            )
        )
        if result.scalar_one_or_none() is not None:
            raise EvaluationStructureError("این پرسنل قبلاً سرشیفت همین واحد ثبت شده است")

        shift_lead = EvaluationShiftLead(department_id=department_id, employee_id=employee_id)
        self.db.add(shift_lead)
        await self.db.flush()  # برای گرفتن shift_lead.id پیش از commit
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
        سرشیفت را (در صورت وجود) حذف می‌کند؛ تخصیص‌های زیرمجموعه‌اش هم با ondelete=CASCADE پاک
        می‌شوند و آن پرسنل «بدون سرشیفت» می‌شوند، که در get_evaluation_targets مستقیماً زیر نظر
        سرپرست واحد قرار می‌گیرند.
        """
        shift_lead = await self.db.get(EvaluationShiftLead, shift_lead_id)
        if shift_lead is not None:
            await self.db.delete(shift_lead)
            await self.db.commit()

    # ---------- تعیین زیرمجموعه هر سرشیفت ----------

    async def set_shift_assignment(self, employee_id: int, shift_lead_id: int) -> EvaluationShiftAssignment:
        """
        پرسنل را زیر سرشیفت داده‌شده قرار می‌دهد (یا از سرشیفت قبلی جابه‌جا می‌کند). پرسنل باید عضو همان
        واحد باشد و خودش سرشیفت نباشد؛ در غیر این صورت EvaluationStructureError. خروجی: تخصیص همراه employee.
        """
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

        # سرشیفت‌های یک واحد نمی‌توانند زیرمجموعه (و ارزیاب) یکدیگر باشند
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

        # هر پرسنل حداکثر یک تخصیص دارد: به‌روزرسانی تخصیص موجود یا ساخت جدید
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
        """پرسنل را (در صورت وجود تخصیص) از زیرمجموعه سرشیفتش خارج می‌کند."""
        result = await self.db.execute(
            select(EvaluationShiftAssignment).where(EvaluationShiftAssignment.employee_id == employee_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            await self.db.delete(existing)
            await self.db.commit()

    # ---------- کاندیدهای انتخاب برای «افزودن به فهرست یک مدیر» ----------

    async def get_manager_candidates(self, site_id: int) -> list[dict]:
        """
        فهرست همه پرسنل سایت (لیست dict) با اطلاعات کمکی برای انتخابگر فرانت‌اند:
            - supervisor_department_name: نام واحدی که سرپرست ارزیابی آن است (برای «سرپرستان بدون مدیر»)
            - evaluated_by_name: نام مدیری که از قبل او را ارزیابی می‌کند (برای برچسب‌گذاری، نه پنهان‌کردن)
            - is_manager: آیا خودش مدیر ثبت‌شده است (تا در میان‌بر «سرپرستان بدون مدیر» پیشنهاد نشود)
        """
        employees_result = await self.db.execute(select(Employee).where(Employee.site_id == site_id))
        employees = employees_result.scalars().all()

        # نگاشت پرسنل سرپرست → نام واحدش (فقط واحدهای این سایت)
        supervisors_result = await self.db.execute(
            select(EvaluationDepartmentSupervisor.employee_id, Department.name)
            .join(Department, Department.id == EvaluationDepartmentSupervisor.department_id)
            .where(Department.site_id == site_id)
        )
        supervisor_department_name_by_employee_id = {row[0]: row[1] for row in supervisors_result.all()}

        # نگاشت پرسنل هدف → نام مدیرش (در همه سایت‌ها، چون هدف می‌تواند از سایت دیگر باشد)
        assignments_result = await self.db.execute(
            select(EvaluationManagerAssignment.target_employee_id, Employee.first_name, Employee.last_name)
            .join(EvaluationManager, EvaluationManager.id == EvaluationManagerAssignment.manager_id)
            .join(Employee, Employee.id == EvaluationManager.employee_id)
        )
        evaluated_by_name_by_employee_id = {
            row[0]: f"{row[1]} {row[2]}" for row in assignments_result.all()
        }

        # پرسنلی که خودشان مدیر این سایت‌اند
        managers_result = await self.db.execute(
            select(EvaluationManager.employee_id).where(EvaluationManager.site_id == site_id)
        )
        manager_employee_ids = {row[0] for row in managers_result.all()}

        return [
            {
                "id": employee.id,
                "personnel_code": employee.personnel_code,
                "first_name": employee.first_name,
                "last_name": employee.last_name,
                "department_id": employee.department_id,
                "supervisor_department_name": supervisor_department_name_by_employee_id.get(employee.id),
                "evaluated_by_name": evaluated_by_name_by_employee_id.get(employee.id),
                "is_manager": employee.id in manager_employee_ids,
            }
            for employee in employees
        ]

    async def get_site_structure(self, site_id: int) -> dict:
        """
        ساختار کامل ارزیابی سایت (dict): مدیران با اهدافشان و برای هر واحد سرپرست، سرشیفت‌ها و
        زیرمجموعه‌ها. روابط با selectinload از قبل بار می‌شوند، چون Lazy-load در Session ناهمگام
        خطای MissingGreenlet می‌دهد. سایت ناموجود: EvaluationStructureError.
        """
        site = await self.db.get(Site, site_id)
        if site is None:
            raise EvaluationStructureError("سایت موردنظر یافت نشد")

        # مدیران سایت همراه employee و اهداف
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

        # برای هر واحد: سرپرست، سرشیفت‌ها و تخصیص‌های زیرمجموعه
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
        """
        ورودی: شناسه پرسنل ارزیاب. نقش‌های او (مدیر/سرپرست/سرشیفت) و داده‌های لازم را از دیتابیس
        جمع می‌کند و با الگوریتم خالص resolve_evaluation_target_ids اهدافش را تعیین می‌کند.
        خروجی: {"is_manager", "is_department_supervisor", "is_shift_lead", "targets": list[Employee]}.
        """
        # نقش‌های ارزیاب: مدیر، سرپرست کدام واحدها، سرشیفت (کدام رکوردها)
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

        # داده خام موردنیاز الگوریتم خالص (resolve_evaluation_target_ids)؛ فقط برای
        # manager_id/department_idهای همین ارزیاب خوانده می‌شود، نه کل جدول‌ها.
        # اهداف هر مدیری که ارزیاب است:
        manager_targets_by_manager_id: dict[int, list[int]] = {}
        for manager_id in manager_ids:
            targets_result = await self.db.execute(
                select(EvaluationManagerAssignment.target_employee_id).where(
                    EvaluationManagerAssignment.manager_id == manager_id
                )
            )
            manager_targets_by_manager_id[manager_id] = [row[0] for row in targets_result.all()]

        # برای هر واحدی که ارزیاب سرپرست آن است: سرشیفت‌ها، همه پرسنل و پرسنل بدون سرشیفت
        shift_lead_employees_by_department: dict[int, list[int]] = {}
        all_employees_by_department: dict[int, list[int]] = {}
        unassigned_employees_by_department: dict[int, list[int]] = {}
        for department_id in department_ids_as_supervisor:
            shift_lead_employees_result = await self.db.execute(
                select(EvaluationShiftLead.employee_id).where(EvaluationShiftLead.department_id == department_id)
            )
            shift_lead_employee_ids = [row[0] for row in shift_lead_employees_result.all()]
            shift_lead_employees_by_department[department_id] = shift_lead_employee_ids

            employees_result = await self.db.execute(
                select(Employee.id).where(
                    Employee.department_id == department_id, Employee.id != evaluator_employee_id
                )
            )  # همه پرسنل واحد به‌جز خود ارزیاب
            department_employee_ids = [row[0] for row in employees_result.all()]
            all_employees_by_department[department_id] = department_employee_ids

            # در واحد دارای سرشیفت، پرسنلی که به هیچ سرشیفتی تخصیص داده نشده‌اند
            # مستقیماً زیر نظر سرپرست می‌مانند تا بی‌ارزیاب نباشند
            if shift_lead_employee_ids:
                shift_lead_ids_for_department_result = await self.db.execute(
                    select(EvaluationShiftLead.id).where(EvaluationShiftLead.department_id == department_id)
                )
                shift_lead_ids_for_department = [row[0] for row in shift_lead_ids_for_department_result.all()]
                assigned_result = await self.db.execute(
                    select(EvaluationShiftAssignment.employee_id).where(
                        EvaluationShiftAssignment.shift_lead_id.in_(shift_lead_ids_for_department)
                    )
                )
                assigned_employee_ids = {row[0] for row in assigned_result.all()}
                shift_lead_employee_id_set = set(shift_lead_employee_ids)
                unassigned_employees_by_department[department_id] = [
                    eid
                    for eid in department_employee_ids
                    if eid not in assigned_employee_ids and eid not in shift_lead_employee_id_set
                ]

        # زیرمجموعه هر سرشیفتی که ارزیاب است
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
            unassigned_employees_by_department=unassigned_employees_by_department,
        )

        # تبدیل شناسه‌های هدف به اشیای Employee
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
