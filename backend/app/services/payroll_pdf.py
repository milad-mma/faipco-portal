"""
تولید PDF فیش حقوقی از روی فیلدهای خام استخراج‌شده از <SalaryReceiptItem>.

طراحی Generic: به هیچ نام فیلد خاصی (حقوق پایه، بیمه، ...) وابسته نیست — فقط
یک جدول دو ستونی «برچسب / مقدار» به همان ترتیب اصلی XML رسم می‌کند، تا حد
امکان به ساختار منبع وفادار بماند.

پشتیبانی از فارسی: چون فونت‌های پیش‌فرض ReportLab (Helvetica) حروف فارسی/عربی
ندارند و این حروف بر خلاف لاتین به‌صورت متصل (Contextual Shaping) و
راست‌به‌چپ نوشته می‌شوند، از app.core.config.PERSIAN_FONT_PATH یک فونت TTF
فارسی بارگذاری و برای شکل‌دهی صحیح از arabic_reshaper + python-bidi استفاده
می‌شود. اگر فونت موجود نباشد، به فونت پیش‌فرض (بدون پشتیبانی فارسی) سقوط
می‌کند و فقط یک‌بار هشدار در Log ثبت می‌شود — تولید PDF متوقف نمی‌شود.
"""
from __future__ import annotations

import logging
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import get_settings

logger = logging.getLogger("faipco.payroll_pdf")

_FONT_NAME = "PersianFont"
_font_checked = False
_font_available = False

# اگر فایل تنظیم‌شده در PERSIAN_FONT_PATH موجود نبود، این مسیرهای رایج در
# توزیع‌های اوبونتو/دبیان هم امتحان می‌شوند — DejaVu Sans معمولاً همراه
# سیستم‌عامل از قبل نصب است و حروف فارسی/عربی (همراه با Presentation Forms
# لازم برای اتصال حروف) را دارد، پس در بسیاری از نصب‌ها حتی بدون گذاشتن
# فونت اختصاصی هم PDF فارسی درست نمایش داده می‌شود.
_FALLBACK_FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
)

_PERSIAN_RANGES = (("\u0600", "\u06FF"), ("\u0750", "\u077F"), ("\uFB50", "\uFDFF"), ("\uFE70", "\uFEFF"))


def _ensure_font_registered() -> bool:
    """فقط یک‌بار در طول عمر پردازش، Font را ثبت می‌کند (Cache شده)."""
    global _font_checked, _font_available
    if _font_checked:
        return _font_available
    _font_checked = True

    candidates = [get_settings().PERSIAN_FONT_PATH, *_FALLBACK_FONT_PATHS]
    for font_path in candidates:
        try:
            pdfmetrics.registerFont(TTFont(_FONT_NAME, font_path))
            _font_available = True
            if font_path != candidates[0]:
                logger.info(
                    "فونت اختصاصی فارسی (%s) پیدا نشد؛ از فونت جایگزین سیستم (%s) استفاده شد.",
                    candidates[0],
                    font_path,
                )
            return True
        except Exception:  # noqa: BLE001 - این مسیر موجود نیست، مسیر بعدی امتحان می‌شود
            continue

    logger.warning(
        "هیچ فونت فارسی پیدا نشد (نه %s و نه فونت‌های جایگزین سیستم) — متن فارسی در PDF "
        "فیش حقوقی درست نمایش داده نمی‌شود. طبق backend/app/assets/fonts/README.md یک فونت TTF قرار دهید.",
        candidates[0],
    )
    _font_available = False
    return False


def _contains_persian(text: str) -> bool:
    return any(any(lo <= ch <= hi for lo, hi in _PERSIAN_RANGES) for ch in text)


def _shape(text: str) -> str:
    """متن فارسی را برای نمایش صحیح (اتصال حروف + ترتیب راست‌به‌چپ) آماده می‌کند."""
    if not text or not _contains_persian(text):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(text))
    except ImportError:
        # arabic-reshaper/python-bidi نصب نیستند — از پیاده‌سازی حداقلی
        # داخلی (بدون وابستگی خارجی) به‌عنوان شبکه ایمنی استفاده می‌شود.
        from app.services.simple_bidi import simple_bidi, simple_reshape

        return simple_bidi(simple_reshape(text))
    except Exception:  # noqa: BLE001 - هر خطای دیگر نباید کل تولید PDF را متوقف کند
        return text


def render_payroll_receipt_pdf(
    *,
    notice_title: str,
    employee_name: str,
    personnel_code: str,
    site_name: str | None,
    fields: list[dict],
) -> bytes:
    """
    fields: خروجی ParsedReceiptItem.fields — لیست تخت {"label", "value", "section"}
    که "section" یکی از "" (مشخصات فیش)، یکی از عناوین ستون‌های اصلی («وام»،
    «کسور»، «مزایا»، «سایر»، یا نام Generic هر Section ناشناخته دیگر)، یا
    "__footer__" (جمع‌بندی پایین فیش) است.

    طرح‌بندی این تابع دقیقاً از روی نمونه واقعی فیش این سازمان ساخته شده:
    یک نوار مشخصات بالا (کد پرسنلی/نام/مرکز هزینه)، یک جدول ۴ ستونی اصلی
    (وام | کسور | مزایا | سایر، از چپ به راست)، و یک نوار جمع‌بندی پایین.
    اگر XML سازمان دیگری Section هایی غیر از این ۴ تا داشته باشد (نام‌های
    ناشناخته)، به‌عنوان ستون‌های اضافه در همان جدول اصلی اضافه می‌شوند — یعنی
    سیستم برای این ۴ تا بهینه شده ولی به آن‌ها محدود نیست.
    """
    has_font = _ensure_font_registered()
    font_name = _FONT_NAME if has_font else "Helvetica"
    font_bold = _FONT_NAME if has_font else "Helvetica-Bold"

    # فیلدهای تخت را بر اساس section بازسازی می‌کنیم
    header_rows: list[dict] = []
    footer_rows: list[dict] = []
    section_rows: dict[str, list[dict]] = {}
    section_order: list[str] = []
    for row in fields:
        section = row.get("section", "")
        if section == "":
            header_rows.append(row)
        elif section == "__footer__":
            footer_rows.append(row)
        else:
            if section not in section_rows:
                section_rows[section] = []
                section_order.append(section)
            section_rows[section].append(row)

    # ترتیب ثابت ۴ ستون اصلی (اگر موجود نباشند هم به‌صورت خالی نمایش داده
    # می‌شوند تا چیدمان با نمونه اصلی یکی باشد)؛ هر Section ناشناخته دیگر
    # (سازمان‌های دیگر) بعد از این ۴ تا اضافه می‌شود.
    fixed_columns = ["وام", "کسور", "مزایا", "سایر"]
    extra_columns = [s for s in section_order if s not in fixed_columns]
    column_titles = fixed_columns + extra_columns

    # جدا کردن سطر «سال»/«ماه» از بقیه‌ی مشخصات، برای زیرعنوان بالای صفحه
    def pop_header(*label_substrings: str) -> str | None:
        for i, row in enumerate(header_rows):
            if any(s in row["label"] for s in label_substrings):
                return header_rows.pop(i)["value"]
        return None

    year_value = pop_header("سال")
    month_value = pop_header("ماه")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )

    title_style = ParagraphStyle("PayrollTitle", fontName=font_bold, fontSize=15, alignment=TA_CENTER, spaceAfter=6)
    subtitle_style = ParagraphStyle("PayrollSubtitle", fontName=font_name, fontSize=12, alignment=TA_CENTER, spaceAfter=10)
    info_style = ParagraphStyle("InfoCell", fontName=font_name, fontSize=9.5, alignment=TA_RIGHT, leading=13)
    info_label_style = ParagraphStyle("InfoLabel", fontName=font_bold, fontSize=9.5, alignment=TA_RIGHT, leading=13)
    col_header_style = ParagraphStyle("ColHeader", fontName=font_bold, fontSize=10, alignment=TA_CENTER)
    row_label_style = ParagraphStyle("RowLabel", fontName=font_name, fontSize=7.6, alignment=TA_RIGHT, leading=9.5)
    row_value_style = ParagraphStyle("RowValue", fontName=font_name, fontSize=7.6, alignment=TA_RIGHT, leading=9.5)
    footer_label_style = ParagraphStyle("FooterLabel", fontName=font_bold, fontSize=9, alignment=TA_RIGHT)
    footer_value_style = ParagraphStyle("FooterValue", fontName=font_name, fontSize=9, alignment=TA_RIGHT)

    story = []

    story.append(Paragraph(_shape(site_name or notice_title or "فیش حقوقی"), title_style))
    if month_value or year_value:
        subtitle = "فیش حقوق ماه " + (month_value or "") + "     سال " + (year_value or "")
        story.append(Paragraph(_shape(subtitle), subtitle_style))
    elif notice_title and site_name:
        story.append(Paragraph(_shape(notice_title), subtitle_style))

    # ---------- نوار مشخصات (کد پرسنلی / نام / مرکز هزینه / بقیه مشخصات باقی‌مانده) ----------
    if header_rows:
        info_cells = []
        for row in header_rows:
            info_cells.append(
                Paragraph(f"{_shape(row['label'])} {_shape(row['value'])}", info_label_style)
            )
        # راست‌به‌چپ: چون Table چپ‌به‌راست می‌چیند، لیست را برعکس می‌کنیم تا
        # اولین مشخصه (کد پرسنلی) در سمت راست صفحه بیفتد.
        info_cells.reverse()
        info_table = Table([info_cells], colWidths=[doc.width / len(info_cells)] * len(info_cells))
        info_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#94a3b8")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(info_table)
        story.append(Spacer(1, 4 * mm))

    # ---------- جدول اصلی ۴ ستونی (وام | کسور | مزایا | سایر) ----------
    def build_column_cell(rows: list[dict]):
        if not rows:
            return ""
        inner_data = [
            [Paragraph(_shape(r["value"]), row_value_style), Paragraph(_shape(r["label"]), row_label_style)]
            for r in rows
        ]
        inner = Table(inner_data, colWidths=["45%", "55%"])
        inner.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#e2e8f0")),
                ]
            )
        )
        return inner

    header_row = [Paragraph(_shape(title), col_header_style) for title in column_titles]
    body_row = [build_column_cell(section_rows.get(title, [])) for title in column_titles]

    col_width = doc.width / len(column_titles)
    main_table = Table([header_row, body_row], colWidths=[col_width] * len(column_titles))
    main_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#94a3b8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#94a3b8")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, 0), 5),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("TOPPADDING", (0, 1), (-1, 1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(main_table)

    # ---------- نوار جمع‌بندی پایین ----------
    if footer_rows:
        story.append(Spacer(1, 2 * mm))
        footer_cells = []
        for row in footer_rows:
            footer_cells.append(
                Table(
                    [[Paragraph(_shape(row["value"]), footer_value_style), Paragraph(_shape(row["label"]), footer_label_style)]],
                    colWidths=["45%", "55%"],
                    style=TableStyle(
                        [
                            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#94a3b8")),
                            ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ]
                    ),
                )
            )
        footer_cells.reverse()
        footer_outer = Table([footer_cells], colWidths=[doc.width / len(footer_cells)] * len(footer_cells))
        footer_outer.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(footer_outer)

    if not has_font:
        story.append(Spacer(1, 6 * mm))
        story.append(
            Paragraph(
                "Warning: Persian font not installed on server — Persian text above may not render correctly.",
                ParagraphStyle("Warn", fontName="Helvetica", fontSize=8, textColor=colors.red),
            )
        )

    doc.build(story)
    return buffer.getvalue()
