"""
پارس XML فیش حقوقی.

نکته کلیدی درباره‌ی فرمت واقعی: فایل‌های واقعی این سازمان خروجی مستقیم یک
گزارش‌ساز نوع SSRS/Telerik هستند — نه یک XML ساده با تگ‌های تخت مثل
<Amount>. در این فرمت:
  - هر رکورد پرسنل داخل یک <SalaryReceiptItem> است (در هر عمقی از درخت،
    بدون فرض خاصی درباره‌ی نام ریشه فایل).
  - کد پرسنلی («Code») یک Attribute است (نه یک Element)، و ممکن است روی هر
    گره‌ای در عمق دلخواه زیر SalaryReceiptItem قرار داشته باشد.
  - بقیه‌ی داده‌ها (حقوق پایه، کسورات، کارکرد، ...) هم به‌صورت Attribute
    روی گره‌های تودرتو (Rectangle/Column/Details/...) پخش شده‌اند؛ هر بخش
    داده (وام/کسورات/مزایا/کارکرد) داخل یک زیردرخت با نام <SalaryReceipt*>
    (مثل SalaryReceiptPayment) قرار دارد.
  - برچسب هر مقدار معمولاً در یک Attribute مجاور با نامی مثل TextboxN یا
    Title/FactorTitle آمده — نه در نام خودِ Attribute مقدار.
  - استثنا: بخش «وام» یک سرستون جدا (Row0 با یک Column به‌ازای هر برچسب:
    «مانده»، «مبلغ قسط»، «نام وام») و ردیف‌های داده‌اش (Details1) را کاملاً
    جدا از آن سرستون دارد — یعنی مقدار و برچسبش اصلاً مجاور هم نیستند. برای
    همین این بخش با تطبیق «موقعیت ستون» (نه توالی سند) پردازش می‌شود.

چون نمی‌توان به نام دقیق فیلدها (که بین سازمان‌ها/واحدهای مختلف فرق می‌کند)
وابسته شد، این پارسر تا حد امکان heuristic و Generic عمل می‌کند:
  1. تمام Attribute های زیردرخت هر SalaryReceiptItem به ترتیب سند جمع‌آوری
     می‌شوند.
  2. هر زیردرخت با نام <SalaryReceipt*> (غیر از خودِ SalaryReceiptItem) یک
     Section جدا محسوب می‌شود؛ بقیه در «مشخصات فیش» یا «جمع‌بندی پایین»
     (بسته به این‌که قبل یا بعد از اولین Section باشند) جمع می‌شوند.
  3. داخل هر Section، اول تلاش می‌شود الگوی «سرستون + ردیف داده هم‌موقعیت»
     (مثل وام) تشخیص داده شود؛ اگر نبود، Attribute هایی که با الگوی برچسب
     شناخته‌شده (TextboxN، Title، FactorTitleN) مطابقت دارند به‌عنوان
     «برچسب» و مقدار مجاورشان در توالی سند به‌عنوان «مقدار» جفت می‌شوند.
  4. نوار جمع‌بندی پایین فیش («جمع مزایا»/«جمع کسور»/«جمع اقساط وام»/
     «خالص پرداختی»/«شماره حساب») چون در XML به‌هم‌ریخته و غیرمجاور است، با
     یک الگوریتم «نزدیک‌ترین همسایه» استخراج می‌شود — تفصیل در
     payroll_common.extract_footer_rows_by_proximity.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from app.services.payroll_common import (
    FOOTER_LABEL_COLUMN,
    ParsedReceiptItem,
    PayrollParseError,
    ReceiptSection,
    extract_footer_rows_by_proximity,
)

# نام قدیمی (سازگاری با کدهای قبلی که مستقیماً از این فایل Import می‌کردند)
PayrollXmlError = PayrollParseError

_FORBIDDEN_MARKERS = (b"<!DOCTYPE", b"<!ENTITY")
_CODE_ATTR_CANDIDATES = ("Code", "code", "PersonnelCode", "EmployeeCode")

_SECTION_TAG_RE = re.compile(r"^SalaryReceipt(.+)$")
_SECTION_TITLE_HINTS = {
    "Loan": "وام",
    "Deduction": "کسور",
    "Payment": "مزایا",
    "Attendance": "سایر",
}
_LABEL_ATTR_RE = re.compile(r"^(Textbox\d+|Title\d*|FactorTitle\d*)$")
_NUMERIC_RE = re.compile(r"^[\-+]?[0-9۰-۹]+([.,٫][0-9۰-۹]+)*$")
_REPORT_META_ATTR_KEYS = {"Name"}  # روی تگ Report، صرفاً متادیتای داخلی گزارش (بدون معنای مالی)

_ROW_TAG_RE = re.compile(r"^Row\d+$")
_DETAILS_TAG_RE = re.compile(r"^Details\d*$")
_COLUMN_TAG_RE = re.compile(r"^Column(\d+)$")

# نگاشت مستقیم Attribute برچسب → Attribute مقدار برای نوار جمع‌بندی پایین
# فیش (Rectangle2/13/14). برخلاف بقیه گزارش، این‌ها در XML به‌هم‌ریخته و
# غیرمجاورند (مثلاً Textbox18 مقدار «جمع مزایا» است ولی بین آن و برچسبش
# Textbox17، یک برچسب کاملاً نامرتبط دیگر فاصله انداخته) — با بررسی مستقیم
# چند رکورد واقعی، این نگاشت کاملاً ثابت و قابل‌اتکا تشخیص داده شد.
_FOOTER_LABEL_TO_VALUE_ATTR = {
    "Textbox17": "Textbox18",  # جمع مزایا
    "Textbox19": "Textbox20",  # جمع کسور
    "Textbox22": "Textbox21",  # جمع اقساط وام
    "Textbox26": "Textbox25",  # خالص پرداختی
    "Textbox24": "Textbox23",  # شماره حساب
}


def _local(tag: str) -> str:
    """اگر Namespace داشته باشد (مثل {urn:x}Code)، فقط نام واقعی تگ را نگه می‌دارد."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find_code(item_element: ET.Element) -> str | None:
    for sub in item_element.iter():
        for candidate in _CODE_ATTR_CANDIDATES:
            if candidate in sub.attrib:
                value = sub.attrib[candidate].strip()
                if value:
                    return value
    return None


def _collect_flat_stream(element: ET.Element, stream: list[tuple[str, str]]) -> None:
    """تمام Attribute های این زیردرخت را به ترتیب سند (Depth-First) جمع می‌کند."""
    tag = _local(element.tag)
    for key, value in element.attrib.items():
        if key.startswith("{"):  # Attribute های Namespace-دار (مثل xsi:...)
            continue
        if tag == "Report" and key in _REPORT_META_ATTR_KEYS:
            continue
        stream.append((key, value))
    for child in element:
        _collect_flat_stream(child, stream)


def _classify(key: str, value: str) -> str:
    """
    'value' یا 'label' برمی‌گرداند. اول بر اساس محتوا قضاوت می‌کند (عدد = تقریباً
    همیشه مقدار)، چون در برخی ویجت‌ها (مثل جمع‌های پایین فیش) نام Attribute
    مقدار و برچسب هر دو از یک الگو (TextboxN) پیروی می‌کنند و نمی‌شود فقط از
    روی نام تشخیص داد؛ فقط وقتی محتوا عدد نیست، به الگوی نام (TextboxN/Title/
    FactorTitleN) یا خالی‌بودن مقدار به‌عنوان نشانه «برچسب» رجوع می‌کند.
    """
    v = value.strip()
    if v and _NUMERIC_RE.match(v):
        return "value"
    if _LABEL_ATTR_RE.match(key) or not v:
        return "label"
    return "value"


def _pair_stream(stream: list[tuple[str, str]], keep_orphans: bool = False) -> list[dict]:
    """
    (برچسب، مقدار) را از یک دنباله Attribute می‌سازد — با فرض این‌که همیشه
    «مقدار» بلافاصله قبل از Attribute برچسبِ خودش می‌آید.
    keep_orphans=True یعنی ردیف‌های بدون مقدار (برچسب یتیم) هم برگردانده
    شوند (برای استخراج عنوان گزارش از روی همین‌ها استفاده می‌شود)، وگرنه
    این ردیف‌ها حذف می‌شوند تا PDF شلوغ نشود.
    """
    rows: list[dict] = []
    i = 0
    n = len(stream)
    while i < n:
        key, value = stream[i]
        if _classify(key, value) == "label":
            rows.append({"label": value, "value": ""})
            i += 1
            continue
        if i + 1 < n and _classify(*stream[i + 1]) == "label":
            rows.append({"label": stream[i + 1][1], "value": value})
            i += 2
            continue
        if not _LABEL_ATTR_RE.match(key):
            rows.append({"label": key, "value": value})
        i += 1
    if keep_orphans:
        return rows
    return [r for r in rows if r["value"].strip()]


def _extract_footer_rows_xml(footer_stream: list[tuple[str, str]]) -> list[dict]:
    """
    اول با نگاشت مستقیم نام Attribute (_FOOTER_LABEL_TO_VALUE_ATTR) — که در
    این فرمت گزارش کاملاً ثابت و قابل‌اتکاست — تلاش می‌کند؛ برای هر مورد
    ناشناخته (فرمت گزارش دیگری با نام Attribute متفاوت)، به الگوریتم عمومی
    «نزدیک‌ترین همسایه» (extract_footer_rows_by_proximity) سقوط می‌کند.
    """
    footer_dict = dict(footer_stream)
    rows: list[dict] = []
    matched_labels: set[str] = set()

    for label_key, value_key in _FOOTER_LABEL_TO_VALUE_ATTR.items():
        label_text = footer_dict.get(label_key, "").strip()
        value_text = footer_dict.get(value_key, "").strip()
        if label_text and value_text and label_text in FOOTER_LABEL_COLUMN:
            rows.append({"label": label_text, "value": value_text, "column": FOOTER_LABEL_COLUMN[label_text]})
            matched_labels.add(label_text)

    # اگر هیچ‌کدام از Attribute های شناخته‌شده بالا در این فایل پیدا نشدند
    # (فرمت گزارش دیگری)، به روش عمومی سقوط می‌کنیم.
    if not matched_labels:
        return extract_footer_rows_by_proximity(footer_stream)

    return rows


def _try_parse_tablix_columns(section_element: ET.Element) -> list[dict] | None:
    """
    اگر این Section شامل یک ردیف سرستون (RowN، هر فرزند ColumnN دقیقاً یک
    Attribute برچسب) و حداقل یک ردیف داده (DetailsN، هر فرزند ColumnN
    دقیقاً یک Attribute مقدار) باشد، آن‌ها را بر اساس شماره ستون (نه توالی
    سند) به‌هم جفت می‌کند و لیست {label,value} برمی‌گرداند. اگر این الگوی
    خاص پیدا نشد، None برمی‌گرداند تا فراخوان به pairing معمولی سقوط کند.
    """
    header_row = next((el for el in section_element.iter() if _ROW_TAG_RE.match(_local(el.tag))), None)
    if header_row is None:
        return None

    column_labels: dict[int, str] = {}
    for child in header_row:
        m = _COLUMN_TAG_RE.match(_local(child.tag))
        if not m or len(child.attrib) != 1:
            return None
        column_labels[int(m.group(1))] = next(iter(child.attrib.values())).strip()

    if not column_labels:
        return None

    details_elements = [el for el in section_element.iter() if _DETAILS_TAG_RE.match(_local(el.tag))]
    if not details_elements:
        return None

    rows: list[dict] = []
    for details in details_elements:
        for child in details:
            m = _COLUMN_TAG_RE.match(_local(child.tag))
            if not m or len(child.attrib) != 1:
                continue
            label = column_labels.get(int(m.group(1)))
            value = next(iter(child.attrib.values()), "").strip()
            if label and value:
                rows.append({"label": label, "value": value})

    return rows if rows else None


def _walk(
    element: ET.Element,
    header_stream: list[tuple[str, str]],
    footer_stream: list[tuple[str, str]],
    sections: list[ReceiptSection],
    state: dict,
) -> None:
    """
    attribute های خارج از Section را بر اساس این‌که قبل یا بعد از اولین
    Section دیده شده‌اند، جدا نگه می‌دارد: header_stream = مشخصات فیش،
    footer_stream = جمع‌بندی‌های پایین فیش.
    """
    tag = _local(element.tag)
    target_stream = footer_stream if state["seen_section"] else header_stream
    for key, value in element.attrib.items():
        if key.startswith("{"):
            continue
        if tag == "Report" and key in _REPORT_META_ATTR_KEYS:
            continue
        target_stream.append((key, value))

    for child in element:
        child_tag = _local(child.tag)
        match = _SECTION_TAG_RE.match(child_tag)
        if match:
            state["seen_section"] = True
            rows = _try_parse_tablix_columns(child)
            if rows is None:
                section_stream: list[tuple[str, str]] = []
                _collect_flat_stream(child, section_stream)
                rows = _pair_stream(section_stream)
            if rows:
                title = _SECTION_TITLE_HINTS.get(match.group(1), child_tag)
                sections.append(ReceiptSection(title=title, rows=rows))
        else:
            _walk(child, header_stream, footer_stream, sections, state)


def _extract_report_title(header_rows_with_orphans: list[dict]) -> tuple[str | None, list[dict]]:
    """
    اولین ردیف «یتیم» (برچسبی که هیچ مقداری برایش پیدا نشد، مثل
    Textbox32="Faipco") را به‌عنوان عنوان بالای فیش برمی‌دارد؛ چون معمولاً
    همین است که در گزارش اصلی به‌عنوان نام/لوگوی متنی سازمان نمایش داده
    می‌شود. بقیه‌ی ردیف‌های معتبر (دارای مقدار) بدون تغییر برگردانده می‌شوند.
    """
    title = None
    kept: list[dict] = []
    for row in header_rows_with_orphans:
        if not row["value"].strip():
            if title is None:
                title = row["label"]
            continue
        kept.append(row)
    return title, kept


def _parse_one_item(item_element: ET.Element) -> ParsedReceiptItem:
    code = _find_code(item_element)
    header_stream: list[tuple[str, str]] = []
    footer_stream: list[tuple[str, str]] = []
    sections: list[ReceiptSection] = []
    _walk(item_element, header_stream, footer_stream, sections, {"seen_section": False})

    header_rows_raw = _pair_stream(header_stream, keep_orphans=True)
    report_title, header_rows = _extract_report_title(header_rows_raw)

    footer_rows = _extract_footer_rows_xml(footer_stream)

    return ParsedReceiptItem(
        code=code,
        report_title=report_title,
        header_rows=header_rows,
        sections=sections,
        footer_rows=footer_rows,
    )


def parse_salary_receipt_items(xml_bytes: bytes) -> list[ParsedReceiptItem]:
    """تمام <SalaryReceiptItem> های فایل را پیدا و Parse می‌کند — مستقل از نام/ریشه فایل."""
    if not xml_bytes or not xml_bytes.strip():
        raise PayrollXmlError("فایل XML خالی است")

    for marker in _FORBIDDEN_MARKERS:
        if marker in xml_bytes:
            raise PayrollXmlError(
                "فایل XML شامل DOCTYPE/ENTITY است و به دلایل امنیتی پذیرفته نمی‌شود"
            )

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise PayrollXmlError(f"فایل XML معتبر نیست: {e}") from e

    items: list[ParsedReceiptItem] = []
    for element in root.iter():
        if _local(element.tag) != "SalaryReceiptItem":
            continue
        items.append(_parse_one_item(element))

    if not items:
        raise PayrollXmlError(
            "هیچ <SalaryReceiptItem> ای در فایل پیدا نشد — ساختار XML باید شامل این تگ باشد"
        )

    return items
