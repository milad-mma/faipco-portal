"""
سرویس «اطلاعیه فیش حقوقی» (Payroll Notice).

جریان کار create_payroll_notice:
1. فایل آپلودشده Parse می‌شود — بر اساس پسوند فایل، Parser مناسب انتخاب
   می‌شود (XML یا XLSX؛ هر دو کاملاً Generic و مستقل از نام فایل/ساختار
   دقیق سازمانی). خروجی هر دو یکسان است (ParsedReceiptItem از
   payroll_common.py) پس بقیه این فایل کاملاً مستقل از فرمت ورودی است.
2. کد هر رکورد با Employee.personnel_code در کل سیستم تطبیق داده می‌شود
   (نه فقط یک Site خاص — چون فایل ورودی اطلاعاتی از Site ندارد).
3. فقط پرسنلی که کدشان پیدا شود، هدف اطلاعیه (NoticeTarget از نوع employee)
   می‌شوند — دقیقاً طبق درخواست: انتخاب مخاطب کاملاً خودکار و از روی فایل
   است، نه دستی.
4. برای هر پرسنل منطبق، یک PayrollReceipt جداگانه (فقط فیلدهای خودش) ذخیره
   می‌شود — هیچ پرسنلی به رکورد پرسنل دیگر دسترسی ندارد (GET .../payroll/mine
   در notices.py همیشه بر اساس employee_id خودِ کاربر لاگین‌شده فیلتر می‌کند).
5. کدهایی که در فایل بودند ولی در سیستم پیدا نشدند، در پاسخ گزارش می‌شوند
   (ارسال نمی‌شوند، نه حذف و نه نادیده گرفته می‌شوند — Admin/acc_manager باید
   از آن‌ها مطلع شود).

نکته طراحی مهم: بر خلاف create_notice معمولی، اینجا از _can_target عبور
نمی‌کنیم — مجوز یکتای notices.payroll (چک‌شده در Endpoint) برای ارسال به
هر پرسنلی که در فایل باشد کافی است؛ چون کل فلسفه این قابلیت «مخاطب از روی
داده، نه انتخاب دستی Site/Department» است.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.notice import Notice, NoticePriority, NoticeStatus, NoticeTarget, NoticeTargetType, NoticeType
from app.models.payroll_receipt import PayrollReceipt
from app.models.user import User
from app.services.payroll_common import ParsedReceiptItem, PayrollParseError
from app.services.payroll_xlsx import parse_salary_receipt_items_xlsx
from app.services.payroll_xml import parse_salary_receipt_items

# سازگاری با کدهای قدیمی‌تر که مستقیماً PayrollXmlError را از این فایل Import می‌کردند
PayrollXmlError = PayrollParseError

_XLSX_EXTENSIONS = (".xlsx", ".xlsm")


def parse_payroll_file(filename: str, file_bytes: bytes) -> list[ParsedReceiptItem]:
    """بر اساس پسوند فایل، Parser مناسب را انتخاب می‌کند. اگر پسوند ناشناخته بود، XML امتحان می‌شود (فرمت پیش‌فرض)."""
    lower_name = (filename or "").lower()
    if lower_name.endswith(_XLSX_EXTENSIONS):
        return parse_salary_receipt_items_xlsx(file_bytes)
    return parse_salary_receipt_items(file_bytes)


@dataclass
class PayrollNoticeResult:
    notice: Notice
    matched_employee_count: int
    missing_codes: list[str] = field(default_factory=list)
    invalid_row_count: int = 0  # ردیف‌هایی که اصلاً کد پرسنلی نداشتند


class PayrollNoticeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_payroll_notice(
        self,
        sender: User,
        title: str,
        body: str,
        priority: NoticePriority,
        file_bytes: bytes,
        filename: str = "",
    ) -> PayrollNoticeResult:
        try:
            items = parse_payroll_file(filename, file_bytes)
        except PayrollParseError:
            raise  # پیام قابل‌نمایش همان است — Endpoint مستقیماً 400 برمی‌گرداند

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
            notice_type=NoticeType.payroll,
            publish_at=datetime.now(timezone.utc),
        )
        self.db.add(notice)
        await self.db.flush()  # notice.id لازم است برای PayrollReceipt/NoticeTarget

        now = datetime.now(timezone.utc)
        missing_codes: list[str] = []
        # employee_id -> (code, fields) — اگر کدی در چند ردیف XML تکرار شده
        # باشد، آخرین ردیف جایگزین قبلی می‌شود (به‌جای این‌که دو رکورد PayrollReceipt
        # با همان notice_id+employee_id بسازیم که Unique Constraint را نقض می‌کند).
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
            notice.targets.append(NoticeTarget(target_type=NoticeTargetType.employee, target_id=employee_id))
            self.db.add(
                PayrollReceipt(
                    notice_id=notice.id,
                    employee_id=employee_id,
                    source_personnel_code=code,
                    fields_json=json.dumps(fields, ensure_ascii=False),
                    created_at=now,
                )
            )

        await self.db.commit()

        return PayrollNoticeResult(
            notice=notice,
            matched_employee_count=len(employee_receipt_data),
            missing_codes=sorted(set(missing_codes)),
            invalid_row_count=invalid_row_count,
        )

    async def get_my_receipt(self, notice_id: int, employee_id: int) -> PayrollReceipt | None:
        """
        فقط رکورد متعلق به همین employee_id را برمی‌گرداند — این تنها نقطه‌ی
        دسترسی به PayrollReceipt در کل برنامه است و همیشه با employee_id
        خودِ کاربر لاگین‌شده فراخوانی می‌شود (هرگز با ورودی از کاربر دیگر).
        """
        result = await self.db.execute(
            select(PayrollReceipt).where(
                PayrollReceipt.notice_id == notice_id, PayrollReceipt.employee_id == employee_id
            )
        )
        return result.scalar_one_or_none()
