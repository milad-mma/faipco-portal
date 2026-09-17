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
from app.models.leave_request import LeaveRequestApprover, LeaveRequestMapping, LeaveRequestType, LeaveRequestTypeViewer
from app.repositories.user_repository import UserRepository


class LeaveRequestStructureError(Exception):
    pass


class LeaveRequestStructureService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- نگاشت ستون‌ها (Mapping) ----------

    async def get_mapping(self, site_id: int) -> LeaveRequestMapping | None:
        result = await self.db.execute(select(LeaveRequestMapping).where(LeaveRequestMapping.site_id == site_id))
        return result.scalar_one_or_none()

    async def upsert_mapping(self, site_id: int, data: dict) -> LeaveRequestMapping:
        existing = await self.get_mapping(site_id)
        if existing is not None:
            for key, value in data.items():
                setattr(existing, key, value)
            mapping = existing
        else:
            mapping = LeaveRequestMapping(site_id=site_id, **data)
            self.db.add(mapping)
        await self.db.commit()
        await self.db.refresh(mapping)
        return mapping

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
        return leave_type

    async def update_type(self, type_id: int, data: dict) -> LeaveRequestType:
        leave_type = await self.db.get(LeaveRequestType, type_id)
        if leave_type is None:
            raise LeaveRequestStructureError("نوع درخواست موردنظر یافت نشد")
        for key, value in data.items():
            setattr(leave_type, key, value)
        await self.db.commit()
        await self.db.refresh(leave_type)
        return leave_type

    async def delete_type(self, type_id: int) -> None:
        leave_type = await self.db.get(LeaveRequestType, type_id)
        if leave_type is not None:
            await self.db.delete(leave_type)
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

    # ---------- مجوز مشاهده به تفکیک نوع ----------

    async def list_type_viewers(self, leave_type_id: int) -> list[LeaveRequestTypeViewer]:
        result = await self.db.execute(
            select(LeaveRequestTypeViewer)
            .options(selectinload(LeaveRequestTypeViewer.employee))
            .where(LeaveRequestTypeViewer.leave_type_id == leave_type_id)
        )
        return list(result.scalars().all())

    async def add_type_viewer(self, leave_type_id: int, employee_id: int) -> LeaveRequestTypeViewer:
        existing = await self.db.execute(
            select(LeaveRequestTypeViewer).where(
                LeaveRequestTypeViewer.leave_type_id == leave_type_id,
                LeaveRequestTypeViewer.employee_id == employee_id,
            )
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = LeaveRequestTypeViewer(leave_type_id=leave_type_id, employee_id=employee_id)
            self.db.add(row)
            await self.db.commit()
            await self.db.refresh(row)
        result = await self.db.execute(
            select(LeaveRequestTypeViewer)
            .options(selectinload(LeaveRequestTypeViewer.employee))
            .where(LeaveRequestTypeViewer.id == row.id)
        )
        return result.scalar_one()

    async def remove_type_viewer(self, viewer_id: int) -> None:
        row = await self.db.get(LeaveRequestTypeViewer, viewer_id)
        if row is not None:
            await self.db.delete(row)
            await self.db.commit()

    async def get_allowed_type_ids_for_employee(self, site_id: int, employee_id: int) -> list[int]:
        """
        ⚠️ فهرست شناسه‌های نوعی که این فرد صراحتاً به آن‌ها دسترسی
        محدود دارد (نه مجوز سراسری leave_requests.view/manage) - برای
        استفاده در فیلتر «همه درخواست‌های مرخصی/ماموریت».
        """
        result = await self.db.execute(
            select(LeaveRequestTypeViewer.leave_type_id)
            .join(LeaveRequestType, LeaveRequestType.id == LeaveRequestTypeViewer.leave_type_id)
            .where(LeaveRequestTypeViewer.employee_id == employee_id, LeaveRequestType.site_id == site_id)
        )
        return list(result.scalars().all())
