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

چون نمی‌توان به نام دقیق فیلدها (که بین سازمان‌ها/واحدهای مختلف فرق می‌کند)
وابسته شد، این پارسر کاملاً heuristic و Generic عمل می‌کند:
  1. تمام Attribute های زیردرخت هر SalaryReceiptItem به ترتیب سند جمع‌آوری
     می‌شوند.
  2. هر زیردرخت با نام <SalaryReceipt*> (غیر از خودِ SalaryReceiptItem) یک
     Section جدا محسوب می‌شود (مثلاً «مزایا و پرداختی‌ها»)؛ بقیه در یک
     Section پیش‌فرض («مشخصات فیش») جمع می‌شوند.
  3. داخل هر Section، Attribute هایی که با الگوی برچسب شناخته‌شده (TextboxN،
     Title، FactorTitleN) مطابقت دارند به‌عنوان «برچسب» و مقدار مجاورشان در
     توالی سند به‌عنوان «مقدار» جفت می‌شوند.
این heuristic برای اکثریت قطعی فیلدهای فیش (حقوق پایه، کسورات، کارکرد و...)
درست جفت می‌شود؛ در چند ویجت خلاصه/جمع نهایی (مثل کادر «جمع کسور/جمع مزایا»
در پایین فیش) ممکن است ترتیب Attribute ها در XML با ترتیب دیداری یکی نباشد
و جفت‌سازی کاملاً دقیق نباشد — چون همان اعداد در بخش «کارکرد و جمع‌بندی»
هم با برچسب درست تکرار می‌شوند، این محدودیت عملاً بی‌اثر است.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from app.services.payroll_common import ParsedReceiptItem, PayrollParseError, ReceiptSection

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


def _pair_stream(stream: list[tuple[str, str]]) -> list[dict]:
    """
    (برچسب، مقدار) را از یک دنباله Attribute می‌سازد — با فرض این‌که همیشه
    «مقدار» بلافاصله قبل از Attribute برچسبِ خودش می‌آید (این جهت را از
    نمونه واقعی گزارش تأیید کرده‌ایم: Code سپس Textbox33='کد پرسنلی:'،
    Value سپس FactorTitle، ...).
    """
    rows: list[dict] = []
    i = 0
    n = len(stream)
    while i < n:
        key, value = stream[i]
        if _classify(key, value) == "label":
            # برچسبی که «مقدار»ی بلافاصله قبلش نیامده (وگرنه در تکرار قبلی مصرف می‌شد)
            rows.append({"label": value, "value": ""})
            i += 1
            continue
        # این یک «مقدار» است؛ اگر بلافاصله بعدش یک «برچسب» باشد جفت می‌شوند
        if i + 1 < n and _classify(*stream[i + 1]) == "label":
            rows.append({"label": stream[i + 1][1], "value": value})
            i += 2
            continue
        # هیچ برچسبی مجاورش نبود. اگر نام خودِ Attribute یک شناسه داخلی گزارش
        # است (TextboxN/Title/FactorTitleN بدون برچسب واقعی، مثل فیلدهای
        # خالی/بلااستفاده در قالب گزارش)، به‌جای نمایش نام فنی، کامل نادیده
        # گرفته می‌شود؛ در غیر این‌صورت همان نام Attribute به‌عنوان برچسب Fallback نمایش داده می‌شود.
        if not _LABEL_ATTR_RE.match(key):
            rows.append({"label": key, "value": value})
        i += 1
    # سطرهای بدون مقدار (برچسب یتیم/سرستون خالی) حذف می‌شوند تا PDF شلوغ نشود
    return [r for r in rows if r["value"].strip()]


def _walk(
    element: ET.Element,
    header_stream: list[tuple[str, str]],
    footer_stream: list[tuple[str, str]],
    sections: list[ReceiptSection],
    state: dict,
) -> None:
    """
    مثل نسخه قبلی، با این تفاوت که attribute های خارج از Section را بر اساس
    این‌که قبل یا بعد از اولین Section دیده شده‌اند، جدا نگه می‌دارد:
    header_stream = مشخصات فیش (نام، کد پرسنلی، مرکز هزینه، سال/ماه) —
    footer_stream = جمع‌بندی‌های پایین فیش (جمع مزایا/کسور، شماره حساب، ...)
    — این تفکیک دقیقاً مطابق ساختار واقعی گزارش (Rectangle1 قبل از Tablix2،
    Rectangle2/13/14 بعد از آن) است.
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
            section_stream: list[tuple[str, str]] = []
            _collect_flat_stream(child, section_stream)
            rows = _pair_stream(section_stream)
            if rows:
                title = _SECTION_TITLE_HINTS.get(match.group(1), child_tag)
                sections.append(ReceiptSection(title=title, rows=rows))
            # این زیردرخت به‌عنوان Section جدا مصرف شد — دوباره تکرار نمی‌شود
        else:
            _walk(child, header_stream, footer_stream, sections, state)


def _parse_one_item(item_element: ET.Element) -> ParsedReceiptItem:
    code = _find_code(item_element)
    header_stream: list[tuple[str, str]] = []
    footer_stream: list[tuple[str, str]] = []
    sections: list[ReceiptSection] = []
    _walk(item_element, header_stream, footer_stream, sections, {"seen_section": False})
    return ParsedReceiptItem(
        code=code,
        header_rows=_pair_stream(header_stream),
        sections=sections,
        footer_rows=_pair_stream(footer_stream),
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
