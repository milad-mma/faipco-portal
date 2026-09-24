"""
سرویس «اطلاعیه فیش کارکرد» (Attendance Card Notice).

هم‌ساختار با PayrollNoticeService است ولی برای اکسل «فیش کارکرد پرسنل»
(نه فیش حقوقی) کار می‌کند. مراحل ساخت اطلاعیه:

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

AttendanceCardParseError = PayrollParseError  # همان خطای Parse فیش حقوقی، با نام مخصوص این ماژول


@dataclass
class AttendanceCardNoticeResult:
    """نتیجه‌ی ساخت اطلاعیه: اطلاعیه‌ی ساخته‌شده، تعداد پرسنل منطبق، کدهای پیدانشده و تعداد ردیف‌های نامعتبر."""
    notice: Notice
    matched_employee_count: int
    missing_codes: list[str] = field(default_factory=list)
    invalid_row_count: int = 0
    out_of_scope_codes: list[str] = field(default_factory=list)  # کدهایی که فقط در سایت‌های غیرمجاز فرستنده پرسنل دارند


class AttendanceCardNoticeService:
    """ساخت اطلاعیه‌ی فیش کارکرد از فایل اکسل و خواندن فیش هر پرسنل."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_attendance_card_notice(
        self,
        sender: User,
        title: str,
        body: str,
        priority: NoticePriority,
        file_bytes: bytes,
        card_subtitle: str,
        site_ids: set[int] | None = None,
    ) -> AttendanceCardNoticeResult:
        """
        از بایت‌های اکسل فیش کارکرد، یک اطلاعیه‌ی منتشرشده می‌سازد.
        ورودی: فرستنده، عنوان/متن/اولویت اطلاعیه، بایت‌های فایل و زیرعنوان کارت.
        site_ids: سایت‌هایی که فرستنده مجوز ارسال فیش کارکرد برایشان دارد (None = همه).
        برای هر کد پرسنلی منطبق، NoticeTarget و AttendanceCardReceipt ثبت و commit می‌شود.
        """
        # Parse فایل؛ خطای Parse به لایه‌ی API منتقل می‌شود
        try:
            items = parse_attendance_cards_xlsx(file_bytes)
        except PayrollParseError:
            raise

        codes = {item.code for item in items if item.code}  # کدهای پرسنلی یکتا در فایل
        invalid_row_count = sum(1 for item in items if not item.code)  # ردیف‌های بدون کد

        # نگاشت کد پرسنلی -> پرسنل‌ها (یک کد ممکن است به چند رکورد Employee بخورد)
        code_to_employees: dict[str, list[Employee]] = {}
        out_of_scope: set[str] = set()
        if codes:
            result = await self.db.execute(select(Employee).where(Employee.personnel_code.in_(codes)))
            for emp in result.scalars().all():
                # پرسنل سایت‌هایی که فرستنده مجوزشان را ندارد کنار گذاشته می‌شوند
                if site_ids is not None and emp.site_id not in site_ids:
                    out_of_scope.add(emp.personnel_code)
                    continue
                code_to_employees.setdefault(emp.personnel_code, []).append(emp)
        out_of_scope -= set(code_to_employees)  # کدی که در سایت مجاز هم پرسنل دارد «خارج از محدوده» نیست

        # ساخت اطلاعیه با وضعیت «منتشرشده» و نوع «فیش کارکرد»
        notice = Notice(
            sender_id=sender.id,
            title=title,
            body=body,
            priority=priority,
            status=NoticeStatus.published,
            notice_type=NoticeType.attendance_card,
            publish_at=datetime.now(timezone.utc),
            card_subtitle=card_subtitle,
        )
        self.db.add(notice)
        await self.db.flush()  # برای گرفتن notice.id

        now = datetime.now(timezone.utc)
        missing_codes: list[str] = []
        employee_receipt_data: dict[int, tuple[str, list[dict]]] = {}  # employee_id -> (کد، فیلدهای فیش)

        # تطبیق هر ردیف فایل با پرسنل؛ کدهای پیدانشده جدا نگه داشته می‌شوند
        for item in items:
            if not item.code:
                continue
            employees = code_to_employees.get(item.code)
            if not employees:
                if item.code not in out_of_scope:
                    missing_codes.append(item.code)
                continue
            for employee in employees:
                employee_receipt_data[employee.id] = (item.code, item.fields)

        # برای هر پرسنل منطبق: هدف اطلاعیه + رکورد فیش (fields به‌صورت JSON)
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
            out_of_scope_codes=sorted(out_of_scope),
        )

    async def get_my_receipt(self, notice_id: int, employee_id: int) -> AttendanceCardReceipt | None:
        """
        فیش کارکرد یک پرسنل در یک اطلاعیه را برمی‌گرداند (یا None).
        تنها نقطه‌ی دسترسی به AttendanceCardReceipt است و همیشه با employee_id فیلتر می‌شود.
        """
        result = await self.db.execute(
            select(AttendanceCardReceipt).where(
                AttendanceCardReceipt.notice_id == notice_id, AttendanceCardReceipt.employee_id == employee_id
            )
        )
        return result.scalar_one_or_none()
