"""
پارس فایل XLSX فیش حقوقی.

ساختار واقعی این فایل‌ها (خروجی مستقیم "چاپ به Excel" همان گزارش SSRS): هر
پرسنل یک بلوک از سطرها را اشغال می‌کند که با یک سطر «مشخصات» (کد پرسنلی/نام/
مرکز هزینه) شروع می‌شود. زیرِ آن، یک سطر «سرستون» چهار Section را با نامشان
(«وام»، «کسور»، «مزایا»، «سایر») در چهار محدوده‌ی ستونی جدا مشخص می‌کند؛ در
سطرهای بعدی، هر Section مستقل از بقیه، ردیف‌های خودش را به شکل (مقدار در
ستون کوچک‌تر، برچسب در ستون بزرگ‌تر همان سطر) دارد.

چون این فرمت هیچ Header ستونی به سبک جدول معمولی ندارد (مختصات کاملاً شبیه
همان چیدمان بصری گزارش/PDF است، نه یک Export تخت)، پارسر کاملاً Positional و
Generic عمل می‌کند — نه به نام فایل وابسته است و نه به تعداد/ترتیب دقیق
Section ها (اگر Section ناشناخته‌ای هم باشد، به همان اسمش اضافه می‌شود).

الگوریتم:
  1. هر سلولی که دقیقاً برابر «کد پرسنلی:» باشد، شروع یک بلوک پرسنل جدید است.
  2. همان سطر (سطر مشخصات) با یک عبور «مقدار سپس برچسب» (مثل XML) به
     (کد پرسنلی، نام، مرکز هزینه، ...) شکسته می‌شود — هر سلول متنی که به «:»
     ختم شود «برچسب» است و سلول غیرخالیِ ماقبلش «مقدار» همان برچسب.
  3. نزدیک‌ترین سطر زیرِ آن که شامل نام‌های شناخته‌شده («وام»/«کسور»/«مزایا»/
     «سایر») باشد، ستون شروع هر Section را مشخص می‌کند.
  4. برای هر سطر از سطر بعد از سرستون تا قبل از بلوک پرسنل بعدی، سلول‌های هر
     Section (بر اساس محدوده ستونی‌اش) به‌صورت (اولین سلول غیرخالی = مقدار،
     آخرین سلول غیرخالی = برچسب) خوانده می‌شوند.
"""
from __future__ import annotations

import io
import re

import openpyxl

from app.services.payroll_common import ParsedReceiptItem, PayrollParseError, ReceiptSection

_INFO_LABEL_CODE = "کد پرسنلی:"
_PERIOD_LABEL = "فیش حقوق ماه"  # همیشه چند سطر قبل از «کد پرسنلی:» همان بلوک می‌آید — برای تشخیص دقیق مرز واقعی بلوک
# چند برچسب شناخته‌شده که برخلاف «کد پرسنلی:»/«نام و نام خانوادگی:» با «:»
# ختم نمی‌شوند ولی هنوز هم به‌وضوح «برچسب» هستند نه «مقدار» (اصطلاحات عمومی
# گزارش حقوق و دستمزد، نه داده اختصاصی یک سازمان خاص)
_KNOWN_LABEL_WORDS_NO_COLON = {"سال", "فیش حقوق ماه", "ماه"}
_SECTION_NAME_RE = re.compile(r"^(وام|کسور|مزایا|سایر|[\w\u0600-\u06FF ]{2,20})$")
_KNOWN_SECTION_NAMES = {"وام", "کسور", "مزایا", "سایر"}
_NUMERIC_RE = re.compile(r"^[\-+]?[0-9۰-۹]+([.,٫][0-9۰-۹]+)*$")


def _cell_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _row_cells(ws, row: int, max_col: int) -> list[tuple[int, str]]:
    """[(شماره ستون, متن)] سلول‌های غیرخالی یک سطر، به ترتیب ستون."""
    out = []
    for c in range(1, max_col + 1):
        v = _cell_str(ws.cell(row=row, column=c).value)
        if v:
            out.append((c, v))
    return out


def _is_label_text(text: str) -> bool:
    return text.endswith(":") or text.endswith("：") or text in _KNOWN_LABEL_WORDS_NO_COLON


def _pair_row_value_then_label(cells: list[tuple[int, str]]) -> list[dict]:
    """
    مثل payroll_xml._pair_stream ولی روی سلول‌های یک سطر Excel: هر سلولی که
    برچسب شناخته شود (به «:» ختم شود یا یکی از اصطلاحات عمومی شناخته‌شده
    باشد)، بلافاصله سلول غیرخالی ماقبلش (در همان لیست) «مقدار» همان برچسب
    می‌شود.
    """
    rows: list[dict] = []
    i = 0
    n = len(cells)
    while i < n:
        col, text = cells[i]
        if _is_label_text(text):
            rows.append({"label": text.rstrip(": ："), "value": ""})
            i += 1
            continue
        if i + 1 < n and _is_label_text(cells[i + 1][1]):
            rows.append({"label": cells[i + 1][1].rstrip(": ："), "value": text})
            i += 2
            continue
        rows.append({"label": f"col{col}", "value": text})
        i += 1
    return [r for r in rows if r["value"].strip()]


def _find_code(rows: list[dict]) -> str | None:
    for row in rows:
        if "کد پرسنلی" in row["label"]:
            return row["value"]
    return None


def parse_salary_receipt_items_xlsx(file_bytes: bytes) -> list[ParsedReceiptItem]:
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as e:  # noqa: BLE001 - فایل خراب/فرمت نامعتبر
        raise PayrollParseError(f"فایل XLSX معتبر نیست: {e}") from e

    ws = wb.worksheets[0]
    max_col = ws.max_column
    max_row = ws.max_row

    # ---------- ۱. پیدا کردن شروع هر بلوک پرسنل ----------
    # نکته مهم: «کد پرسنلی:» خودش چند سطر بعد از شروع واقعی بلوک می‌آید (بلوک
    # واقعاً از سطر «فیش حقوق ماه ... سال ...» شروع می‌شود). اگر مرز بلوک را
    # فقط بر اساس «کد پرسنلی:» بگیریم، انتهای هر بلوک چند سطر از ابتدای بلوک
    # بعدی را هم به اشتباه قورت می‌دهد (چون آن چند سطر قبل از «کد پرسنلی:»ی
    # بعدی، هنوز داخل محدوده به‌حساب می‌آیند). پس ابتدا سطرهای «فیش حقوق ماه»
    # را هم پیدا می‌کنیم و نزدیک‌ترین‌شان (قبل از هر «کد پرسنلی:») را به‌عنوان
    # مرز واقعی شروع بلوک در نظر می‌گیریم.
    info_rows: list[int] = []
    period_rows: list[int] = []
    for r in range(1, max_row + 1):
        for c in range(1, max_col + 1):
            text = _cell_str(ws.cell(row=r, column=c).value)
            if text == _INFO_LABEL_CODE:
                info_rows.append(r)
            elif text == _PERIOD_LABEL:
                period_rows.append(r)

    if not info_rows:
        raise PayrollParseError(
            f"هیچ سطر «{_INFO_LABEL_CODE}» در فایل پیدا نشد — این فایل با ساختار مورد انتظار مطابقت ندارد"
        )

    def _true_block_start(info_row: int) -> int:
        candidates = [p for p in period_rows if p <= info_row and info_row - p <= 5]
        return min(candidates) if candidates else info_row

    block_start_rows = sorted({_true_block_start(r) for r in info_rows})
    # اگر (به‌ندرت) دو «کد پرسنلی:» به یک «فیش حقوق ماه» نگاشت شدند، آن دو را
    # با خودِ info_row هرکدام به‌عنوان بلوک جدا نگه می‌داریم (خیلی بعید ولی برای اطمینان)
    if len(block_start_rows) < len(info_rows):
        block_start_rows = sorted(set(block_start_rows) | set(info_rows))

    items: list[ParsedReceiptItem] = []

    for idx, block_start in enumerate(block_start_rows):
        block_end = (block_start_rows[idx + 1] - 1) if idx + 1 < len(block_start_rows) else max_row
        # سطر واقعی «کد پرسنلی:» داخل همین بلوک (ممکن است چند سطر پایین‌تر از block_start باشد)
        info_row = next((r for r in info_rows if block_start <= r <= block_end), block_start)

        # ---------- ۲. مشخصات فیش: از شروع بلوک تا سطر info_row را با هم می‌خوانیم
        # (چون «سال»/«فیش حقوق ماه» و «کد پرسنلی»/«نام»/«مرکز هزینه» در این
        # فایل روی دو سطر جدا از هم پخش شده‌اند، نه یک سطر) ----------
        header_rows: list[dict] = []
        for r in range(block_start, info_row + 1):
            header_rows.extend(_pair_row_value_then_label(_row_cells(ws, r, max_col)))
        code = _find_code(header_rows)

        # ---------- ۳. پیدا کردن سطر سرستون Section ها (نزدیک‌ترین سطر زیرِ info_row) ----------
        section_header_row: int | None = None
        section_starts: list[tuple[int, str]] = []  # [(ستون شروع, نام Section)]
        for r in range(info_row + 1, block_end + 1):
            found = [
                (c, _cell_str(ws.cell(row=r, column=c).value))
                for c in range(1, max_col + 1)
                if _cell_str(ws.cell(row=r, column=c).value) in _KNOWN_SECTION_NAMES
            ]
            if len(found) >= 2:  # حداقل ۲ Section شناخته‌شده روی یک سطر باشد تا مطمئن شویم سرستون است
                section_header_row = r
                section_starts = found
                break

        sections: list[ReceiptSection] = []
        data_start_row = (section_header_row + 1) if section_header_row else (info_row + 1)
        footer_start_row = block_end + 1

        if section_starts:
            section_starts.sort(key=lambda x: x[0])
            # محدوده هر Section: از ستون شروع خودش تا یکی‌مانده‌به ستون شروع بعدی
            ranges: list[tuple[int, int, str]] = []
            for i, (start_col, name) in enumerate(section_starts):
                end_col = section_starts[i + 1][0] - 1 if i + 1 < len(section_starts) else max_col
                ranges.append((start_col, end_col, name))

            section_rows_map: dict[str, list[dict]] = {name: [] for _, _, name in ranges}
            last_data_row = section_header_row  # اگر هیچ ردیف داده‌ای پیدا نشد، Footer از همین‌جا شروع می‌شود

            for r in range(data_start_row, block_end + 1):
                matched_this_row = False
                for start_col, end_col, name in ranges:
                    cells = [
                        (c, _cell_str(ws.cell(row=r, column=c).value))
                        for c in range(start_col, end_col + 1)
                        if _cell_str(ws.cell(row=r, column=c).value)
                    ]
                    if not cells:
                        continue
                    if len(cells) == 1:
                        # فقط یک سلول (بدون جفت مشخص) — نادیده گرفته می‌شود، چون
                        # معلوم نیست مقدار است یا برچسب یتیم (این خودش هم به‌عنوان
                        # «ردیف داده معتبر» به‌حساب نمی‌آید تا مرز واقعی Footer درست تشخیص داده شود)
                        continue
                    value_col, value_text = cells[0]
                    label_col, label_text = cells[-1]
                    if value_text and label_text and value_col != label_col:
                        section_rows_map[name].append({"label": label_text, "value": value_text})
                        matched_this_row = True
                if matched_this_row:
                    last_data_row = r

            for start_col, end_col, name in ranges:
                if section_rows_map[name]:
                    sections.append(ReceiptSection(title=name, rows=section_rows_map[name]))

            footer_start_row = last_data_row + 1

        # ---------- ۴. جمع‌بندی پایین بلوک (بین آخرین ردیف داده و بلوک بعدی) ----------
        footer_rows: list[dict] = []
        for r in range(footer_start_row, block_end + 1):
            row_cells = _row_cells(ws, r, max_col)
            if row_cells:
                footer_rows.extend(_pair_row_value_then_label(row_cells))

        items.append(
            ParsedReceiptItem(code=code, header_rows=header_rows, sections=sections, footer_rows=footer_rows)
        )

    return items
