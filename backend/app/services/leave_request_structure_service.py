"""
سرویس پیکربندی ماژول «درخواست مرخصی/ماموریت» (جدول‌های پورتال، نه کاراوب).

شامل: نگاشت ستون‌های کاراوب هر سایت (Mapping) و فعال/غیرفعال‌بودن ماژول، نوع‌های
درخواست و مجوز مشاهده‌ی مشترک هر عنوان نوع، تأییدکننده دستی هر واحد و مسئول نیروی
انسانی سایت. خواندن/نوشتن خودِ WF_Requests در leave_request_service.py است.
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
    """خطای منطقی این سرویس (رکورد یافت نشد، ورودی نامعتبر)؛ در endpoint به 400 تبدیل می‌شود."""

    pass


def permission_code_for_type_title(title: str) -> str:
    """
    کد مجوز مشاهده‌ی یک نوع درخواست را از روی عنوان آن می‌سازد (فاصله‌ها به زیرخط).
    کد از عنوان ساخته می‌شود نه شناسه سطر، تا نوع‌های هم‌عنوان در سایت‌های مختلف
    یک Permission مشترک داشته باشند؛ سایت‌بندی از طریق UserRole.site_id انجام می‌شود.
    """
    slug = re.sub(r"\s+", "_", title.strip())
    return f"leave_requests.view.type.{slug}"


# نوع‌های پایه‌ای که هنگام ساخت اولین نگاشت هر سایت به‌صورت خودکار ایجاد می‌شوند
# (مقادیر واقعی کاراوب مشترک همه سایت‌ها)؛ ادمین می‌تواند بعداً آن‌ها را ویرایش/حذف کند.
DEFAULT_LEAVE_REQUEST_TYPES = [
    # title, is_mission, is_hourly, action_id, operation_id, card_no, is_forgotten_punch
    ("مرخصی روزانه استحقاقی", False, False, 1, 5, 57, False),
    ("مرخصی ساعتی استحقاقی", False, True, 3, 5, 17, False),
    ("ماموریت ساعتی", True, True, 9, 3, 9, False),
    # مقادیر کاراوب برای «ورود و خروج فراموش شده» (WF_Action = ۸)
    ("تردد فراموش شده", False, True, 8, 2, 305, True),
]


class LeaveRequestStructureService:
    """عملیات CRUD روی جدول‌های پیکربندی ماژول مرخصی/ماموریت؛ هر متد خودش commit می‌کند."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- نگاشت ستون‌ها (Mapping) ----------

    async def get_mapping(self, site_id: int) -> LeaveRequestMapping | None:
        """نگاشت کاراوب یک سایت را برمی‌گرداند؛ None یعنی ماژول برای این سایت تنظیم نشده."""
        result = await self.db.execute(select(LeaveRequestMapping).where(LeaveRequestMapping.site_id == site_id))
        return result.scalar_one_or_none()

    async def upsert_mapping(self, site_id: int, data: dict) -> LeaveRequestMapping:
        """
        نگاشت یک سایت را می‌سازد یا فیلدهایش را به‌روز می‌کند (ورودی: دیکشنری فیلدهای LeaveRequestMappingIn).
        اگر نگاشت برای اولین بار ساخته شود، نوع‌های پیش‌فرض هم برای سایت ایجاد می‌شوند.
        """
        existing = await self.get_mapping(site_id)
        is_new_mapping = existing is None
        # به‌روزرسانی رکورد موجود یا ساخت رکورد جدید
        if existing is not None:
            for key, value in data.items():
                setattr(existing, key, value)
            mapping = existing
        else:
            mapping = LeaveRequestMapping(site_id=site_id, **data)
            self.db.add(mapping)
        await self.db.commit()
        await self.db.refresh(mapping)

        # فقط برای نگاشت تازه‌ساخته‌شده نوع‌های پایه اضافه می‌شوند
        if is_new_mapping:
            await self._seed_default_types_if_none(site_id)

        return mapping

    # ---------- فعال/غیرفعال بودن ماژول برای سایت ----------

    async def get_module_status(self, site_id: int) -> dict:
        """وضعیت ماژول برای سایت: has_mapping (نگاشت دارد) و is_disabled (از پنل غیرفعال شده)."""
        mapping = await self.get_mapping(site_id)
        return {"has_mapping": mapping is not None, "is_disabled": bool(mapping and mapping.is_disabled)}

    async def set_module_disabled(self, site_id: int, is_disabled: bool) -> dict:
        """پرچم is_disabled نگاشت سایت را تنظیم می‌کند و وضعیت جدید را برمی‌گرداند؛ بدون نگاشت خطا می‌دهد."""
        mapping = await self.get_mapping(site_id)
        if mapping is None:
            raise LeaveRequestStructureError(
                "برای این سایت هنوز نگاشت مرخصی/ماموریت تنظیم نشده - ماژول از قبل غیرفعال است"
            )
        mapping.is_disabled = is_disabled
        await self.db.commit()
        return await self.get_module_status(site_id)

    async def _seed_default_types_if_none(self, site_id: int) -> None:
        """نوع‌های DEFAULT_LEAVE_REQUEST_TYPES را فقط اگر سایت هنوز هیچ نوعی ندارد می‌سازد."""
        existing_types = await self.list_types(site_id)
        if existing_types:
            return
        for title, is_mission, is_hourly, action_id, operation_id, card_no, forgotten in DEFAULT_LEAVE_REQUEST_TYPES:
            await self.add_type(site_id, title, is_mission, is_hourly, action_id, operation_id, card_no, forgotten)

    async def delete_mapping(self, site_id: int) -> None:
        """نگاشت سایت را حذف می‌کند (ماژول برای سایت غیرفعال می‌شود)؛ اگر نبود، کاری نمی‌کند."""
        mapping = await self.get_mapping(site_id)
        if mapping is not None:
            await self.db.delete(mapping)
            await self.db.commit()

    # ---------- نوع‌های درخواست ----------

    async def list_types(self, site_id: int) -> list[LeaveRequestType]:
        """همه نوع‌های درخواست یک سایت (فعال و غیرفعال) به ترتیب شناسه."""
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
        """
        یک نوع درخواست جدید برای سایت می‌سازد و مطمئن می‌شود مجوز مشاهده‌ی عنوان آن وجود دارد.
        ورودی: عنوان، پرچم‌های مأموریت/ساعتی/تردد فراموش‌شده و مقادیر کاراوب (action/operation/card).
        """
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
        Permission مشاهده‌ی این عنوان نوع را در صورت نبود می‌سازد.
        مجوز بین نوع‌های هم‌عنوان در سایت‌های مختلف مشترک است؛ اگر از قبل وجود داشته باشد، دوباره ساخته نمی‌شود.
        """
        code = permission_code_for_type_title(title)
        # اگر مجوز با همین کد از قبل هست، کاری نمی‌کند
        result = await self.db.execute(select(Permission).where(Permission.code == code))
        if result.scalar_one_or_none() is not None:
            return
        self.db.add(Permission(code=code, description=f"مشاهده درخواست‌های «{title}»"))
        await self.db.commit()

    async def update_type(self, type_id: int, data: dict) -> LeaveRequestType:
        """
        فیلدهای داده‌شده (data) را روی یک نوع درخواست اعمال می‌کند و رکورد به‌روز را برمی‌گرداند.
        اگر عنوان تغییر کند، مجوز عنوان جدید ساخته می‌شود؛ مجوز عنوان قبلی دست‌نخورده می‌ماند.
        """
        leave_type = await self.db.get(LeaveRequestType, type_id)
        if leave_type is None:
            raise LeaveRequestStructureError("نوع درخواست موردنظر یافت نشد")
        for key, value in data.items():
            setattr(leave_type, key, value)
        if "title" in data:
            # مجوز عنوان قبلی حذف نمی‌شود چون ممکن است نوع‌های هم‌عنوان در سایت‌های دیگر از آن استفاده کنند
            await self._ensure_permission_for_title(data["title"])
        await self.db.commit()
        await self.db.refresh(leave_type)
        return leave_type

    async def delete_type(self, type_id: int) -> None:
        """
        یک نوع درخواست را حذف می‌کند. مجوز مشاهده‌ی عنوان آن فقط وقتی حذف می‌شود که
        هیچ نوع دیگری (در هیچ سایتی) با همین عنوان باقی نمانده باشد.
        """
        leave_type = await self.db.get(LeaveRequestType, type_id)
        if leave_type is None:
            return
        title = leave_type.title
        await self.db.delete(leave_type)
        await self.db.commit()

        # اگر نوع هم‌عنوانی در سایت دیگری مانده، مجوز مشترک باید بماند
        remaining = await self.db.execute(select(LeaveRequestType).where(LeaveRequestType.title == title))
        if remaining.scalar_one_or_none() is not None:
            return
        # حذف مجوز یتیم‌شده
        code = permission_code_for_type_title(title)
        result = await self.db.execute(select(Permission).where(Permission.code == code))
        permission = result.scalar_one_or_none()
        if permission is not None:
            await self.db.delete(permission)  # RolePermission های مرتبط با ondelete=CASCADE خودکار پاک می‌شوند
            await self.db.commit()

    # ---------- تخصیص تأییدکننده هر واحد ----------

    async def list_approvers(self, site_id: int) -> list[LeaveRequestApprover]:
        """تأییدکننده‌های دستی همه واحدهای یک سایت، همراه با واحد و پرسنل تأییدکننده."""
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
        """
        تأییدکننده یک واحد را تعیین یا جایگزین می‌کند و رکورد کامل (با واحد و پرسنل) را برمی‌گرداند.
        اگر واحد یا پرسنل وجود نداشته باشد خطا می‌دهد؛ برای پرسنل در صورت نبود، حساب کاربری ساخته می‌شود.
        """
        department = await self.db.get(Department, department_id)
        if department is None:
            raise LeaveRequestStructureError("واحد سازمانی موردنظر یافت نشد")
        employee = await self.db.get(Employee, approver_employee_id)
        if employee is None:
            raise LeaveRequestStructureError("پرسنل موردنظر یافت نشد")

        # تأییدکننده باید بتواند وارد پورتال شود؛ مثل بقیه سرپرست‌های پروژه حساب کاربری تضمین می‌شود
        await UserRepository(self.db).get_or_create_employee_user(employee)

        # هر واحد حداکثر یک تأییدکننده دارد: رکورد موجود به‌روز می‌شود یا رکورد جدید ساخته می‌شود
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
        # بارگذاری مجدد با روابط برای خروجی LeaveRequestApproverOut
        result = await self.db.execute(
            select(LeaveRequestApprover)
            .options(
                selectinload(LeaveRequestApprover.department), selectinload(LeaveRequestApprover.approver_employee)
            )
            .where(LeaveRequestApprover.department_id == department_id)
        )
        return result.scalar_one()

    async def remove_approver(self, department_id: int) -> None:
        """تأییدکننده دستی یک واحد را حذف می‌کند؛ اگر تعیین نشده بود، کاری نمی‌کند."""
        result = await self.db.execute(
            select(LeaveRequestApprover).where(LeaveRequestApprover.department_id == department_id)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            await self.db.delete(existing)
            await self.db.commit()


    # ---------- مسئول نیروی انسانی سایت (تأییدکننده نهایی تردد فراموش‌شده) ----------

    async def get_hr_officer(self, site_id: int) -> LeaveRequestHrOfficer | None:
        """مسئول نیروی انسانی سایت را همراه با پرسنل برمی‌گرداند؛ None یعنی تعیین نشده."""
        result = await self.db.execute(
            select(LeaveRequestHrOfficer)
            .options(selectinload(LeaveRequestHrOfficer.employee))
            .where(LeaveRequestHrOfficer.site_id == site_id)
        )
        return result.scalar_one_or_none()

    async def set_hr_officer(self, site_id: int, employee_id: int) -> LeaveRequestHrOfficer:
        """
        مسئول نیروی انسانی سایت را تعیین یا جایگزین می‌کند و رکورد کامل را برمی‌گرداند.
        پرسنل باید متعلق به همین سایت و دارای کد پرسنلی عددی باشد (در کاراوب به‌عنوان Emp_No نوشته می‌شود).
        """
        employee = await self.db.get(Employee, employee_id)
        if employee is None or employee.site_id != site_id:
            raise LeaveRequestStructureError("پرسنل موردنظر در این سایت یافت نشد")
        if not (employee.personnel_code or "").isdigit():
            raise LeaveRequestStructureError("کد پرسنلی این فرد عددی نیست - نمی‌تواند تأییدکننده کاراوب باشد")
        await UserRepository(self.db).get_or_create_employee_user(employee)  # تضمین حساب کاربری برای ورود
        # هر سایت حداکثر یک مسئول: رکورد موجود به‌روز می‌شود یا رکورد جدید ساخته می‌شود
        existing = await self.get_hr_officer(site_id)
        if existing is not None:
            existing.employee_id = employee_id
        else:
            self.db.add(LeaveRequestHrOfficer(site_id=site_id, employee_id=employee_id))
        await self.db.commit()
        self.db.expire_all()  # تا رابطه employee با مقدار جدید بارگذاری شود
        return await self.get_hr_officer(site_id)

    async def remove_hr_officer(self, site_id: int) -> None:
        """مسئول نیروی انسانی سایت را حذف می‌کند؛ اگر تعیین نشده بود، کاری نمی‌کند."""
        existing = await self.get_hr_officer(site_id)
        if existing is not None:
            await self.db.delete(existing)
            await self.db.commit()
