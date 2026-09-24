"""
سرویس «اطلاعیه فیش حقوقی» (Payroll Notice).

جریان کار create_payroll_notice:
1. فایل آپلودشده Parse می‌شود؛ Parser بر اساس پسوند انتخاب می‌شود (XML یا XLSX).
   خروجی هر دو ParsedReceiptItem (payroll_common.py) است، پس بقیه‌ی این فایل
   مستقل از فرمت ورودی است.
2. کد هر رکورد با Employee.personnel_code در کل سیستم تطبیق داده می‌شود
   (نه یک Site خاص، چون فایل ورودی اطلاعات Site ندارد).
3. فقط پرسنلی که کدشان پیدا شود هدف اطلاعیه (NoticeTarget از نوع employee) می‌شوند؛
   مخاطبان به‌صورت خودکار از روی فایل تعیین می‌شوند، نه دستی.
4. برای هر پرسنل منطبق یک PayrollReceipt جداگانه (فقط فیلدهای خودش) ذخیره می‌شود؛
   GET .../payroll/mine در notices.py همیشه با employee_id کاربر لاگین‌شده فیلتر می‌کند.
5. کدهایی که در فایل بودند ولی در سیستم پیدا نشدند در پاسخ گزارش می‌شوند
   تا Admin/acc_manager از آن‌ها مطلع شود.

برخلاف create_notice معمولی، اینجا _can_target بررسی نمی‌شود: مجوز notices.payroll
(که در Endpoint چک می‌شود) برای ارسال به هر پرسنلی که در فایل باشد کافی است،
چون مخاطبان از روی داده تعیین می‌شوند نه انتخاب دستی Site/Department.
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

# نام مستعار PayrollParseError برای کدهایی که PayrollXmlError را از این ماژول Import می‌کنند
PayrollXmlError = PayrollParseError

_XLSX_EXTENSIONS = (".xlsx", ".xlsm")  # پسوندهایی که با Parser اکسل خوانده می‌شوند


def parse_payroll_file(filename: str, file_bytes: bytes) -> list[ParsedReceiptItem]:
    """
    ورودی: نام و بایت‌های فایل. Parser را بر اساس پسوند انتخاب می‌کند (پسوند ناشناخته = XML).
    خروجی: لیست ParsedReceiptItem؛ در خطای پارس PayrollParseError.
    """
    lower_name = (filename or "").lower()
    if lower_name.endswith(_XLSX_EXTENSIONS):
        return parse_salary_receipt_items_xlsx(file_bytes)
    return parse_salary_receipt_items(file_bytes)


@dataclass
class PayrollNoticeResult:
    """نتیجه‌ی ساخت اطلاعیه فیش: اطلاعیه، تعداد پرسنل منطبق، کدهای پیدانشده و تعداد ردیف‌های بدون کد."""
    notice: Notice
    matched_employee_count: int
    missing_codes: list[str] = field(default_factory=list)  # کدهای موجود در فایل که پرسنلی با آن‌ها پیدا نشد
    invalid_row_count: int = 0  # ردیف‌هایی که اصلاً کد پرسنلی نداشتند
    out_of_scope_codes: list[str] = field(default_factory=list)  # کدهایی که فقط در سایت‌های غیرمجاز فرستنده پرسنل دارند


class PayrollNoticeService:
    """ساخت اطلاعیه‌ی فیش حقوقی از روی فایل و واکشی فیش خودِ پرسنل."""
    def __init__(self, db: AsyncSession):
        """ورودی: Session دیتابیس async."""
        self.db = db

    async def create_payroll_notice(
        self,
        sender: User,
        title: str,
        body: str,
        priority: NoticePriority,
        file_bytes: bytes,
        filename: str = "",
        site_ids: set[int] | None = None,
    ) -> PayrollNoticeResult:
        """
        ورودی: فرستنده، عنوان، متن، اولویت و فایل فیش. اطلاعیه منتشرشده می‌سازد و برای هر
        پرسنل منطبق یک NoticeTarget و یک PayrollReceipt ثبت می‌کند.
        site_ids: سایت‌هایی که فرستنده مجوز ارسال فیش برایشان دارد (None = همه)؛ پرسنل بقیه‌ی سایت‌ها فیش نمی‌گیرند.
        خروجی: PayrollNoticeResult.
        """
        # پارس فایل ورودی
        try:
            items = parse_payroll_file(filename, file_bytes)
        except PayrollParseError:
            raise  # پیام قابل‌نمایش همان است — Endpoint مستقیماً 400 برمی‌گرداند

        # کدهای یکتا و شمارش ردیف‌های بدون کد
        codes = {item.code for item in items if item.code}
        invalid_row_count = sum(1 for item in items if not item.code)

        # واکشی یکجای پرسنل‌های منطبق؛ یک کد ممکن است به چند پرسنل برسد
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

        # ساخت اطلاعیه منتشرشده از نوع payroll
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
        # employee_id -> (code, fields) — اگر کدی در چند ردیف فایل تکرار شده باشد،
        # آخرین ردیف جایگزین قبلی می‌شود تا Unique Constraint (notice_id, employee_id) نقض نشود.
        employee_receipt_data: dict[int, tuple[str, list[dict]]] = {}

        # تطبیق هر ردیف با پرسنل و ثبت کدهای پیدانشده
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

        for employee_id, (code, fields) in employee_receipt_data.items():
            # NoticeTarget مستقیماً با notice_id به Session اضافه می‌شود (نه notice.targets.append)
            # چون دسترسی به Relationship بارگذاری‌نشده در AsyncSession باعث MissingGreenlet می‌شود.
            self.db.add(
                NoticeTarget(notice_id=notice.id, target_type=NoticeTargetType.employee, target_id=employee_id)
            )
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
            out_of_scope_codes=sorted(out_of_scope),
        )

    async def get_my_receipt(self, notice_id: int, employee_id: int) -> PayrollReceipt | None:
        """
        ورودی: شناسه اطلاعیه و employee_id کاربر لاگین‌شده.
        خروجی: فیش همان پرسنل در آن اطلاعیه یا None؛ این تنها نقطه‌ی دسترسی به PayrollReceipt است.
        """
        result = await self.db.execute(
            select(PayrollReceipt).where(
                PayrollReceipt.notice_id == notice_id, PayrollReceipt.employee_id == employee_id
            )
        )
        return result.scalar_one_or_none()
