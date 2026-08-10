"""
ساختارهای مشترک بین همه‌ی Parser های ورودی فیش حقوقی (XML، XLSX، و هر فرمت
دیگری که در آینده اضافه شود). هر Parser (مثلاً payroll_xml.py، payroll_xlsx.py)
مستقل خروجی همین ParsedReceiptItem را تولید می‌کند تا بقیه‌ی سیستم (تطبیق کد
پرسنلی، ساخت PDF) کاملاً مستقل از فرمت ورودی باشد.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class PayrollParseError(Exception):
    """خطای قابل‌نمایش به کاربر هنگام پارس فایل فیش حقوقی (هر فرمتی)."""


@dataclass
class ReceiptSection:
    title: str
    rows: list[dict]  # [{"label": "...", "value": "..."}]


@dataclass
class ParsedReceiptItem:
    code: str | None
    header_rows: list[dict] = field(default_factory=list)  # مشخصات فیش (نام، کد، مرکز هزینه، سال، ماه)
    sections: list[ReceiptSection] = field(default_factory=list)  # ستون‌های نامدار (وام/کسور/مزایا/سایر)
    footer_rows: list[dict] = field(default_factory=list)  # جمع‌بندی‌های پایین فیش

    @property
    def default_rows(self) -> list[dict]:
        """سازگاری با کدهای قدیمی‌تر: مشخصات فیش + جمع‌بندی‌ها با هم، به همان ترتیب."""
        return [*self.header_rows, *self.footer_rows]

    @property
    def fields(self) -> list[dict]:
        """نمای تخت (Flat) از همه سطرها — برای ذخیره در PayrollReceipt.fields_json."""
        flat: list[dict] = [dict(row, section="") for row in self.header_rows]
        for section in self.sections:
            for row in section.rows:
                flat.append(dict(row, section=section.title))
        flat.extend(dict(row, section="__footer__") for row in self.footer_rows)
        return flat
