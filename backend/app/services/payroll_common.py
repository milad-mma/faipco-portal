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


# برچسب‌های شناخته‌شده نوار جمع‌بندی پایین فیش، و این‌که هرکدام زیر کدام یک
# از ۴ ستون اصلی (وام/کسور/مزایا/سایر) باید قرار بگیرد. این ۵ اصطلاح،
# متعلق به قالب گزارش (Report Engine) هستند، نه یک سازمان خاص — طبق بررسی
# مستقیم فایل واقعی XML و XLSX.
FOOTER_LABEL_COLUMN = {
    "جمع مزایا": "مزایا",
    "جمع کسور": "کسور",
    "جمع اقساط وام": "وام",
    "خالص پرداختی": "مزایا",  # ردیف دوم پایین فیش، زیر همان ستون «جمع مزایا»
    "شماره حساب": "وام",  # ردیف دوم پایین فیش، زیر همان ستون «جمع اقساط وام»
}

# ردیف (۰=اول، ۱=دوم) که هر برچسب باید در آن قرار بگیرد — مستقل از ترتیب
# پیدا شدنش، چون مثلاً «شماره حساب» همیشه باید در ردیف دوم باشد حتی اگر
# «جمع اقساط وام» (ردیف اول همان ستون) اصلاً برای این پرسنل مقدار نداشته باشد.
FOOTER_LABEL_ROW = {
    "جمع مزایا": 0,
    "جمع کسور": 0,
    "جمع اقساط وام": 0,
    "خالص پرداختی": 1,
    "شماره حساب": 1,
}


def extract_footer_rows_by_proximity(cells: list[tuple[str, str]]) -> list[dict]:
    """
    ورودی: [(شناسه‌ی موقعیت هرچه باشد، متن)] در ترتیب طبیعی سند/صفحه (نه
    لزوماً دقیقاً مجاور). چون محل دقیق برچسب/مقدارهای نوار جمع‌بندی در هر دو
    فرمت XML و XLSX کاملاً یکنواخت نیست (گاهی همان سطر/عنصر، گاهی چند مورد
    آن‌طرف‌تر)، برای هر برچسب شناخته‌شده (FOOTER_LABEL_COLUMN)، نزدیک‌ترین
    سلول «مقداری» (غیربرچسب) اطرافش را به‌عنوان مقدارش برمی‌دارد.
    """
    values_only = list(cells)
    claimed: set[int] = set()
    rows: list[dict] = []
    for idx, (_, text) in enumerate(values_only):
        if text not in FOOTER_LABEL_COLUMN:
            continue
        value = ""
        for offset in range(1, 8):
            for j in (idx - offset, idx + offset):
                if 0 <= j < len(values_only) and j not in claimed:
                    j_text = values_only[j][1]
                    if j_text not in FOOTER_LABEL_COLUMN and j_text.strip():
                        value = j_text.strip()
                        claimed.add(j)
                        break
            if value:
                break
        if value:
            rows.append({"label": text, "value": value, "column": FOOTER_LABEL_COLUMN[text]})
    return rows


@dataclass
class ReceiptSection:
    title: str
    rows: list[dict]  # [{"label": "...", "value": "..."}]


@dataclass
class ParsedReceiptItem:
    code: str | None
    report_title: str | None = None  # مثلاً «Faipco» — نام/عنوان بالای فیش، اگر در فایل موجود باشد
    header_rows: list[dict] = field(default_factory=list)  # مشخصات فیش (نام، کد، مرکز هزینه، سال، ماه)
    sections: list[ReceiptSection] = field(default_factory=list)  # ستون‌های نامدار (وام/کسور/مزایا/سایر)
    footer_rows: list[dict] = field(default_factory=list)  # جمع‌بندی‌های پایین فیش؛ هر ردیف می‌تواند "column" داشته باشد (زیر کدام یک از ۴ ستون اصلی قرار می‌گیرد)

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
        if self.report_title:
            flat.insert(0, {"label": "__report_title__", "value": self.report_title, "section": "__meta__"})
        return flat
