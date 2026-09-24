"""
ساختارهای مشترک بین همه‌ی Parserهای ورودی فیش حقوقی (XML، XLSX و ...).

هر Parser (مثلاً payroll_xml.py و payroll_xlsx.py) خروجی ParsedReceiptItem تولید می‌کند
تا بقیه‌ی سیستم (تطبیق کد پرسنلی، ساخت PDF) مستقل از فرمت ورودی باشد.
شامل: PayrollParseError، نگاشت برچسب‌های نوار جمع‌بندی، تابع استخراج جمع‌بندی
بر اساس مجاورت، و dataclassهای ReceiptSection و ParsedReceiptItem.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class PayrollParseError(Exception):
    """خطای قابل‌نمایش به کاربر هنگام پارس فایل فیش حقوقی (هر فرمتی)."""


# برچسب‌های شناخته‌شده‌ی نوار جمع‌بندی پایین فیش و ستونی (از ۴ ستون وام/کسور/مزایا/سایر)
# که هرکدام زیر آن قرار می‌گیرد. این برچسب‌ها متعلق به قالب گزارش (Report Engine) هستند
# و در هر دو فرمت XML و XLSX یکسان‌اند.
FOOTER_LABEL_COLUMN = {
    "جمع مزایا": "مزایا",
    "جمع کسور": "کسور",
    "جمع اقساط وام": "وام",
    "خالص پرداختی": "مزایا",  # ردیف دوم پایین فیش، زیر همان ستون «جمع مزایا»
    "شماره حساب": "وام",  # ردیف دوم پایین فیش، زیر همان ستون «جمع اقساط وام»
}

# ردیف (۰=اول، ۱=دوم) که هر برچسب باید در آن قرار بگیرد — مستقل از ترتیب
# پیدا شدنش، چون مثلاً «شماره حساب» همیشه باید در ردیف دوم باشد حتی اگر
# «جمع اقساط وام» (ردیف اول همان ستون) برای این پرسنل مقدار نداشته باشد.
FOOTER_LABEL_ROW = {
    "جمع مزایا": 0,
    "جمع کسور": 0,
    "جمع اقساط وام": 0,
    "خالص پرداختی": 1,
    "شماره حساب": 1,
}


def extract_footer_rows_by_proximity(cells: list[tuple[str, str]]) -> list[dict]:
    """
    ورودی: [(شناسه‌ی موقعیت، متن)] به ترتیب طبیعی سند. برای هر برچسب شناخته‌شده
    (FOOTER_LABEL_COLUMN) نزدیک‌ترین سلول غیربرچسبِ غیرخالیِ اطرافش را مقدار آن می‌گیرد.
    خروجی: لیست {"label", "value", "column"}؛ برچسب‌های بدون مقدار حذف می‌شوند.
    """
    values_only = list(cells)
    claimed: set[int] = set()  # اندیس سلول‌هایی که به‌عنوان مقدار یک برچسب برداشته شده‌اند
    rows: list[dict] = []
    # پیمایش سلول‌ها و پردازش فقط سلول‌های برچسب
    for idx, (_, text) in enumerate(values_only):
        if text not in FOOTER_LABEL_COLUMN:
            continue
        value = ""
        # جست‌وجوی دوطرفه با فاصله‌ی رو به افزایش (حداکثر ۷ سلول) برای نزدیک‌ترین مقدار
        for offset in range(1, 8):
            for j in (idx - offset, idx + offset):  # اول سمت قبل، بعد سمت بعد
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
    """یک ستون نامدار فیش (مثل وام/کسور/مزایا/سایر) با عنوان و ردیف‌های برچسب/مقدار."""
    title: str
    rows: list[dict]  # [{"label": "...", "value": "..."}]


@dataclass
class ParsedReceiptItem:
    """
    فیش پارس‌شده‌ی یک پرسنل، مستقل از فرمت ورودی.
    شامل کد پرسنلی، عنوان گزارش، مشخصات بالای فیش، ستون‌ها و جمع‌بندی‌های پایین.
    """
    code: str | None  # کد پرسنلی برای تطبیق با Employee.personnel_code
    report_title: str | None = None  # مثلاً «Faipco» — نام/عنوان بالای فیش، اگر در فایل موجود باشد
    header_rows: list[dict] = field(default_factory=list)  # مشخصات فیش (نام، کد، مرکز هزینه، سال، ماه)
    sections: list[ReceiptSection] = field(default_factory=list)  # ستون‌های نامدار (وام/کسور/مزایا/سایر)
    footer_rows: list[dict] = field(default_factory=list)  # جمع‌بندی‌های پایین فیش؛ هر ردیف می‌تواند "column" داشته باشد (زیر کدام یک از ۴ ستون اصلی قرار می‌گیرد)

    @property
    def default_rows(self) -> list[dict]:
        """خروجی: مشخصات فیش و جمع‌بندی‌ها با هم، به همان ترتیب (برای مصرف‌کننده‌هایی که ستون‌ها را لازم ندارند)."""
        return [*self.header_rows, *self.footer_rows]

    @property
    def fields(self) -> list[dict]:
        """
        نمای تخت (Flat) از همه‌ی ردیف‌ها با کلید section — برای ذخیره در PayrollReceipt.fields_json.
        section: "" برای مشخصات، عنوان ستون، "__footer__" برای جمع‌بندی و "__meta__" برای عنوان گزارش.
        """
        flat: list[dict] = [dict(row, section="") for row in self.header_rows]
        # ردیف‌های هر ستون با عنوان همان ستون
        for section in self.sections:
            for row in section.rows:
                flat.append(dict(row, section=section.title))
        flat.extend(dict(row, section="__footer__") for row in self.footer_rows)
        # عنوان گزارش به‌صورت ردیف متا در ابتدای لیست
        if self.report_title:
            flat.insert(0, {"label": "__report_title__", "value": self.report_title, "section": "__meta__"})
        return flat
