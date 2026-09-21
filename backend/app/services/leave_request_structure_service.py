"""
سرویس مدیریتی «درخواست مرخصی/ماموریت» - پیکربندی Mapping، نوع‌های
قابل‌تعریف، و تخصیص تأییدکننده هر واحد (نه خواندن/نوشتن خودِ WF_Requests
که در leave_request_service.py است).
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.employee import Department, Employee
from app.models.leave_request import (
    LeaveRequestApprover,
    LeaveRequestHrOfficer,
    LeaveRequestMapping,
    LeaveRequestType,
)
from app.models.user import Permission
from app.repositories.user_repository import UserRepository


class LeaveRequestStructureError(Exception):
    pass


def permission_code_for_type_title(title: str) -> str:
    """
    ⚠️ طبق درخواست صریح کاربر: مجوز مشاهده باید به‌ازای هر «نوع درخواست»
    (مفهوم، نه هر ردیف - یعنی یک بار برای «مرخصی روزانه استحقاقی»، نه
    یک‌بار برای هر سایتی که این عنوان را دارد) فقط یک Permission داشته
    باشد - سایت‌بندی مثل بقیه سیستم RBAC از طریق UserRole.site_id (هنگام
    تخصیص نقش به کاربر) انجام می‌شود، نه از طریق کد مجوز. کد از روی
    عنوانِ نوع (نه شناسه عددی سطر) ساخته می‌شود - تا دو نوع هم‌عنوان در
    دو سایت مختلف، دقیقاً یک مجوز مشترک بگیرند.
    """
    slug = re.sub(r"\s+", "_", title.strip())
    return f"leave_requests.view.type.{slug}"


# ⚠️ طبق درخواست صریح کاربر: وقتی نگاشت مرخصی/ماموریت یک سایت برای اولین
# بار ایجاد می‌شود، همین سه نوع پایه خودکار برایش ساخته می‌شوند - چون
# همه سایت‌های این استقرار به یک سیستم کاراوب/Kara مشترک با همین مقادیر
# واقعی وصل‌اند (تأییدشده: OperationsID/ActionId/Card_No این سه نوع برای
# سایت‌های موجود کاملاً یکسان بود). اگر سایتی مقادیر واقعاً متفاوتی
# داشت، ادمین می‌تواند بعداً این نوع‌های پیش‌فرض را دستی ویرایش/حذف/
# جایگزین کند.
DEFAULT_LEAVE_REQUEST_TYPES = [
    # title, is_mission, is_hourly, action_id, operation_id, card_no, is_forgotten_punch
    ("مرخصی روزانه استحقاقی", False, False, 1, 5, 57, False),
    ("مرخصی ساعتی استحقاقی", False, True, 3, 5, 17, False),
    ("ماموریت ساعتی", True, True, 9, 3, 9, False),
    # مقادیر واقعی کاراوب برای «ورود و خروج فراموش شده» (WF_Action = ۸)
    ("تردد فراموش شده", False, True, 8, 2, 305, True),
]


class LeaveRequestStructureService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- نگاشت ستون‌ها (Mapping) ----------

    async def get_mapping(self, site_id: int) -> LeaveRequestMapping | None:
        result = await self.db.execute(select(LeaveRequestMapping).where(LeaveRequestMapping.site_id == site_id))
        return result.scalar_one_or_none()

    async def upsert_mapping(self, site_id: int, data: dict) -> LeaveRequestMapping:
        existing = await self.get_mapping(site_id)
        is_new_mapping = existing is None
        if existing is not None:
            for key, value in data.items():
                setattr(existing, key, value)
            mapping = existing
        else:
            mapping = LeaveRequestMapping(site_id=site_id, **data)
            self.db.add(mapping)
        await self.db.commit()
        await self.db.refresh(mapping)

        if is_new_mapping:
            await self._seed_default_types_if_none(site_id)

        return mapping

    # ---------- فعال/غیرفعال بودن ماژول برای سایت ----------

    async def get_module_status(self, site_id: int) -> dict:
        mapping = await self.get_mapping(site_id)
        return {"has_mapping": mapping is not None, "is_disabled": bool(mapping and mapping.is_disabled)}

    async def set_module_disabled(self, site_id: int, is_disabled: bool) -> dict:
        mapping = await self.get_mapping(site_id)
        if mapping is None:
            raise LeaveRequestStructureError(
                "برای این سایت هنوز نگاشت مرخصی/ماموریت تنظیم نشده - ماژول از قبل غیرفعال است"
            )
        mapping.is_disabled = is_disabled
        await self.db.commit()
        return await self.get_module_status(site_id)

    async def _seed_default_types_if_none(self, site_id: int) -> None:
        """⚠️ فقط اگر این سایت هنوز هیچ نوع درخواستی ندارد - تا نوع‌های دستیِ از قبل موجود را دوباره اضافه نکند."""
        existing_types = await self.list_types(site_id)
        if existing_types:
            return
        for title, is_mission, is_hourly, action_id, operation_id, card_no, forgotten in DEFAULT_LEAVE_REQUEST_TYPES:
            await self.add_type(site_id, title, is_mission, is_hourly, action_id, operation_id, card_no, forgotten)

    async def delete_mapping(self, site_id: int) -> None:
        mapping = await self.get_mapping(site_id)
        if mapping is not None:
            await self.db.delete(mapping)
            await self.db.commit()

    # ---------- نوع‌های درخواست ----------

    async def list_types(self, site_id: int) -> list[LeaveRequestType]:
        result = await self.db.execute(
            select(LeaveRequestType).where(LeaveRequestType.site_id == site_id).order_by(LeaveRequestType.id)
        )
        return list(result.scalars().all())

    async def add_type(
        self,
        site_id: int,
        title: str,
        is_mission: bool,
        is_hourly: bool,
        action_id: int | None = None,
        operation_id: int | None = None,
        card_no: int | None = None,
        is_forgotten_punch: bool = False,
    ) -> LeaveRequestType:
        leave_type = LeaveRequestType(
            is_forgotten_punch=is_forgotten_punch,
            site_id=site_id,
            title=title,
            is_mission=is_mission,
            is_hourly=is_hourly,
            action_id=action_id,
            operation_id=operation_id,
            card_no=card_no,
        )
        self.db.add(leave_type)
        await self.db.commit()
        await self.db.refresh(leave_type)
        await self._ensure_permission_for_title(title)
        return leave_type

    async def _ensure_permission_for_title(self, title: str) -> None:
        """
        ⚠️ طبق درخواست صریح کاربر: یک نوع «مفهومی» (مثلاً «مرخصی روزانه
        استحقاقی») در چند سایت مختلف باید دقیقاً یک Permission مشترک
        داشته باشد - نه یکی جداگانه به‌ازای هر سایت. اگر از قبل مجوزی با
        همین عنوان ساخته شده (برای سایت دیگری)، دوباره ساخته نمی‌شود.
        """
        code = permission_code_for_type_title(title)
        result = await self.db.execute(select(Permission).where(Permission.code == code))
        if result.scalar_one_or_none() is not None:
            return
        self.db.add(Permission(code=code, description=f"مشاهده درخواست‌های «{title}»"))
        await self.db.commit()

    async def update_type(self, type_id: int, data: dict) -> LeaveRequestType:
        leave_type = await self.db.get(LeaveRequestType, type_id)
        if leave_type is None:
            raise LeaveRequestStructureError("نوع درخواست موردنظر یافت نشد")
        for key, value in data.items():
            setattr(leave_type, key, value)
        if "title" in data:
            # ⚠️ مجوز قدیمی (متعلق به عنوان قبلی) دست‌نخورده باقی می‌ماند -
            # چون ممکن است هنوز توسط نوع‌های هم‌عنوان در سایت‌های دیگر
            # استفاده شود؛ فقط مطمئن می‌شویم عنوان جدید هم مجوز خودش را دارد.
            await self._ensure_permission_for_title(data["title"])
        await self.db.commit()
        await self.db.refresh(leave_type)
        return leave_type

    async def delete_type(self, type_id: int) -> None:
        leave_type = await self.db.get(LeaveRequestType, type_id)
        if leave_type is None:
            return
        title = leave_type.title
        await self.db.delete(leave_type)
        await self.db.commit()

        # ⚠️ مجوز مشترک را فقط وقتی حذف کن که دیگر هیچ نوعی (در هیچ
        # سایتی) با همین عنوان باقی نمانده باشد - وگرنه دسترسی نقش‌هایی
        # که برای سایت‌های دیگر همین نوع را می‌بینند هم از بین می‌رود.
        remaining = await self.db.execute(select(LeaveRequestType).where(LeaveRequestType.title == title))
        if remaining.scalar_one_or_none() is not None:
            return
        code = permission_code_for_type_title(title)
        result = await self.db.execute(select(Permission).where(Permission.code == code))
        permission = result.scalar_one_or_none()
        if permission is not None:
            await self.db.delete(permission)  # ⚠️ RolePermission های مرتبط با ondelete=CASCADE خودکار پاک می‌شوند
            await self.db.commit()

    # ---------- تخصیص تأییدکننده هر واحد ----------

    async def list_approvers(self, site_id: int) -> list[LeaveRequestApprover]:
        result = await self.db.execute(
            select(LeaveRequestApprover)
            .options(
                selectinload(LeaveRequestApprover.department), selectinload(LeaveRequestApprover.approver_employee)
            )
            .join(Department, Department.id == LeaveRequestApprover.department_id)
            .where(Department.site_id == site_id)
        )
        return list(result.scalars().all())

    async def set_approver(self, department_id: int, approver_employee_id: int) -> LeaveRequestApprover:
        department = await self.db.get(Department, department_id)
        if department is None:
            raise LeaveRequestStructureError("واحد سازمانی موردنظر یافت نشد")
        employee = await self.db.get(Employee, approver_employee_id)
        if employee is None:
            raise LeaveRequestStructureError("پرسنل موردنظر یافت نشد")

        # طبق الگوی بقیه سرپرست‌های این پروژه - اطمینان از وجود حساب کاربری
        await UserRepository(self.db).get_or_create_employee_user(employee)

        result = await self.db.execute(
            select(LeaveRequestApprover).where(LeaveRequestApprover.department_id == department_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.approver_employee_id = approver_employee_id
        else:
            existing = LeaveRequestApprover(department_id=department_id, approver_employee_id=approver_employee_id)
            self.db.add(existing)
        await self.db.commit()
        result = await self.db.execute(
            select(LeaveRequestApprover)
            .options(
                selectinload(LeaveRequestApprover.department), selectinload(LeaveRequestApprover.approver_employee)
            )
            .where(LeaveRequestApprover.department_id == department_id)
        )
        return result.scalar_one()

    async def remove_approver(self, department_id: int) -> None:
        result = await self.db.execute(
            select(LeaveRequestApprover).where(LeaveRequestApprover.department_id == department_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            await self.db.delete(existing)
            await self.db.commit()


    # ---------- مسئول نیروی انسانی سایت (تأییدکننده نهایی تردد فراموش‌شده) ----------

    async def get_hr_officer(self, site_id: int) -> LeaveRequestHrOfficer | None:
        result = await self.db.execute(
            select(LeaveRequestHrOfficer)
            .options(selectinload(LeaveRequestHrOfficer.employee))
            .where(LeaveRequestHrOfficer.site_id == site_id)
        )
        return result.scalar_one_or_none()

    async def set_hr_officer(self, site_id: int, employee_id: int) -> LeaveRequestHrOfficer:
        employee = await self.db.get(Employee, employee_id)
        if employee is None or employee.site_id != site_id:
            raise LeaveRequestStructureError("پرسنل موردنظر در این سایت یافت نشد")
        if not (employee.personnel_code or "").isdigit():
            raise LeaveRequestStructureError("کد پرسنلی این فرد عددی نیست - نمی‌تواند تأییدکننده کاراوب باشد")
        await UserRepository(self.db).get_or_create_employee_user(employee)
        existing = await self.get_hr_officer(site_id)
        if existing is not None:
            existing.employee_id = employee_id
        else:
            self.db.add(LeaveRequestHrOfficer(site_id=site_id, employee_id=employee_id))
        await self.db.commit()
        self.db.expire_all()
        return await self.get_hr_officer(site_id)

    async def remove_hr_officer(self, site_id: int) -> None:
        existing = await self.get_hr_officer(site_id)
        if existing is not None:
            await self.db.delete(existing)
            await self.db.commit()
