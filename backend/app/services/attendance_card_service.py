"""
سرویس «اطلاعیه فیش کارکرد» (Attendance Card Notice) — دقیقاً هم‌ساختار با
PayrollNoticeService، فقط برای اکسل «فیش کارکرد پرسنل» (نه فیش حقوقی):

1. فایل اکسل آپلودشده Parse می‌شود (attendance_card_xlsx.py).
2. کد هر رکورد با Employee.personnel_code در کل سیستم تطبیق داده می‌شود.
3. فقط پرسنلی که کدشان پیدا شود، هدف اطلاعیه (NoticeTarget از نوع employee)
   می‌شوند — انتخاب مخاطب کاملاً خودکار و از روی فایل است.
4. برای هر پرسنل منطبق، یک AttendanceCardReceipt جداگانه ذخیره می‌شود —
   هیچ پرسنلی به کارت پرسنل دیگر دسترسی ندارد.
5. کدهایی که در فایل بودند ولی در سیستم پیدا نشدند، در پاسخ گزارش می‌شوند.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.notice import Notice, NoticePriority, NoticeStatus, NoticeTarget, NoticeTargetType, NoticeType
from app.models.attendance_card_receipt import AttendanceCardReceipt
from app.models.user import User
from app.services.attendance_card_xlsx import parse_attendance_cards_xlsx
from app.services.payroll_common import PayrollParseError

AttendanceCardParseError = PayrollParseError


@dataclass
class AttendanceCardNoticeResult:
    notice: Notice
    matched_employee_count: int
    missing_codes: list[str] = field(default_factory=list)
    invalid_row_count: int = 0


class AttendanceCardNoticeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_attendance_card_notice(
        self,
        sender: User,
        title: str,
        body: str,
        priority: NoticePriority,
        file_bytes: bytes,
    ) -> AttendanceCardNoticeResult:
        try:
            items = parse_attendance_cards_xlsx(file_bytes)
        except PayrollParseError:
            raise

        codes = {item.code for item in items if item.code}
        invalid_row_count = sum(1 for item in items if not item.code)

        code_to_employees: dict[str, list[Employee]] = {}
        if codes:
            result = await self.db.execute(select(Employee).where(Employee.personnel_code.in_(codes)))
            for emp in result.scalars().all():
                code_to_employees.setdefault(emp.personnel_code, []).append(emp)

        notice = Notice(
            sender_id=sender.id,
            title=title,
            body=body,
            priority=priority,
            status=NoticeStatus.published,
            notice_type=NoticeType.attendance_card,
            publish_at=datetime.now(timezone.utc),
        )
        self.db.add(notice)
        await self.db.flush()

        now = datetime.now(timezone.utc)
        missing_codes: list[str] = []
        employee_receipt_data: dict[int, tuple[str, list[dict]]] = {}

        for item in items:
            if not item.code:
                continue
            employees = code_to_employees.get(item.code)
            if not employees:
                missing_codes.append(item.code)
                continue
            for employee in employees:
                employee_receipt_data[employee.id] = (item.code, item.fields)

        for employee_id, (code, fields) in employee_receipt_data.items():
            self.db.add(
                NoticeTarget(notice_id=notice.id, target_type=NoticeTargetType.employee, target_id=employee_id)
            )
            self.db.add(
                AttendanceCardReceipt(
                    notice_id=notice.id,
                    employee_id=employee_id,
                    source_personnel_code=code,
                    fields_json=json.dumps(fields, ensure_ascii=False),
                    created_at=now,
                )
            )

        await self.db.commit()

        return AttendanceCardNoticeResult(
            notice=notice,
            matched_employee_count=len(employee_receipt_data),
            missing_codes=sorted(set(missing_codes)),
            invalid_row_count=invalid_row_count,
        )

    async def get_my_receipt(self, notice_id: int, employee_id: int) -> AttendanceCardReceipt | None:
        """فقط رکورد متعلق به همین employee_id — تنها نقطه دسترسی به AttendanceCardReceipt."""
        result = await self.db.execute(
            select(AttendanceCardReceipt).where(
                AttendanceCardReceipt.notice_id == notice_id, AttendanceCardReceipt.employee_id == employee_id
            )
        )
        return result.scalar_one_or_none()
