"""
سرویس مدیریتی «درخواست مرخصی/ماموریت» - پیکربندی Mapping، نوع‌های
قابل‌تعریف، و تخصیص تأییدکننده هر واحد (نه خواندن/نوشتن خودِ WF_Requests
که در leave_request_service.py است).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.employee import Department, Employee
from app.models.leave_request import LeaveRequestApprover, LeaveRequestMapping, LeaveRequestType
from app.models.user import Permission
from app.repositories.user_repository import UserRepository


class LeaveRequestStructureError(Exception):
    pass


# ⚠️ طبق درخواست صریح کاربر: وقتی نگاشت مرخصی/ماموریت یک سایت برای اولین
# بار ایجاد می‌شود، همین سه نوع پایه خودکار برایش ساخته می‌شوند - چون
# همه سایت‌های این استقرار به یک سیستم کاراوب/Kara مشترک با همین مقادیر
# واقعی وصل‌اند (تأییدشده: OperationsID/ActionId/Card_No این سه نوع برای
# سایت‌های موجود کاملاً یکسان بود). اگر سایتی مقادیر واقعاً متفاوتی
# داشت، ادمین می‌تواند بعداً این نوع‌های پیش‌فرض را دستی ویرایش/حذف/
# جایگزین کند.
DEFAULT_LEAVE_REQUEST_TYPES = [
    # title, is_mission, is_hourly, action_id, operation_id, card_no
    ("مرخصی روزانه استحقاقی", False, False, 1, 5, 57),
    ("مرخصی ساعتی استحقاقی", False, True, 3, 5, 17),
    ("ماموریت ساعتی", True, True, 9, 3, 9),
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

    async def _seed_default_types_if_none(self, site_id: int) -> None:
        """⚠️ فقط اگر این سایت هنوز هیچ نوع درخواستی ندارد - تا نوع‌های دستیِ از قبل موجود را دوباره اضافه نکند."""
        existing_types = await self.list_types(site_id)
        if existing_types:
            return
        for title, is_mission, is_hourly, action_id, operation_id, card_no in DEFAULT_LEAVE_REQUEST_TYPES:
            await self.add_type(site_id, title, is_mission, is_hourly, action_id, operation_id, card_no)

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
    ) -> LeaveRequestType:
        leave_type = LeaveRequestType(
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
        # ⚠️ طبق درخواست صریح کاربر: به‌جای یک جدول مجوز اختصاصی جدا، از
        # همان سیستم نقش/مجوز (RBAC) موجود پروژه استفاده می‌شود - هر نوع
        # درخواست یک Permission اختصاصی خودش می‌گیرد (leave_requests.view.type.<id>)
        # تا از صفحه «مدیریت نقش/مجوز» بشود نقشی (مثلاً «حراست») ساخت که
        # فقط همین یک مجوز را دارد.
        self.db.add(
            Permission(
                code=f"leave_requests.view.type.{leave_type.id}", description=f"مشاهده درخواست‌های «{title}»"
            )
        )
        await self.db.commit()
        return leave_type

    async def update_type(self, type_id: int, data: dict) -> LeaveRequestType:
        leave_type = await self.db.get(LeaveRequestType, type_id)
        if leave_type is None:
            raise LeaveRequestStructureError("نوع درخواست موردنظر یافت نشد")
        for key, value in data.items():
            setattr(leave_type, key, value)
        if "title" in data:
            result = await self.db.execute(
                select(Permission).where(Permission.code == f"leave_requests.view.type.{type_id}")
            )
            permission = result.scalar_one_or_none()
            if permission is not None:
                permission.description = f"مشاهده درخواست‌های «{data['title']}»"
        await self.db.commit()
        await self.db.refresh(leave_type)
        return leave_type

    async def delete_type(self, type_id: int) -> None:
        leave_type = await self.db.get(LeaveRequestType, type_id)
        if leave_type is not None:
            await self.db.delete(leave_type)
        result = await self.db.execute(
            select(Permission).where(Permission.code == f"leave_requests.view.type.{type_id}")
        )
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
