"""
تولید PDF فیش حقوقی از روی فیلدهای خام استخراج‌شده (payroll_xml.py یا
payroll_xlsx.py) — طرح‌بندی دقیقاً از روی نمونه واقعی فیش این سازمان تنظیم
شده: عنوان بالای صفحه، زیرعنوان «فیش حقوق {ماه} ماه سال {سال}»، یک نوار
مشخصات با پس‌زمینه طوسی کم‌رنگ (کد پرسنلی/نام/مرکز هزینه)، جدول ۴ ستونی اصلی
(وام | کسور | مزایا | سایر)، و یک نوار جمع‌بندی پایین که هر مقدارش دقیقاً
زیر همان ستون اصلی مربوطه‌اش می‌نشیند.

پشتیبانی از فارسی: چون فونت‌های پیش‌فرض ReportLab (Helvetica) حروف فارسی/عربی
ندارند، از app.core.config.PERSIAN_FONT_PATH (یا در نبودش، DejaVu Sans که
معمولاً از قبل روی سرور نصب است) یک فونت TTF بارگذاری و برای شکل‌دهی صحیح
حروف از arabic_reshaper + python-bidi (یا در نبودشان، simple_bidi.py داخلی)
استفاده می‌شود.

نکته مهم درباره متن‌های طولانی: چون Bidi/Reshape قبل از چیدمان متن روی کل
رشته اعمال می‌شود، اگر بگذاریم خودِ ReportLab یک رشته‌ی از قبل Reverse‌شده را
خط‌شکنی کند، ترتیب کلمات بین خط‌ها به‌هم می‌ریزد. برای همین، برچسب‌های طولانی
را خودمان از قبل بر اساس عرض واقعی ستون به چند خط می‌شکنیم و هر خط را
جداگانه Shape می‌کنیم (_wrap_and_shape) — نه کل رشته را یک‌جا.
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
from app.services.payroll_common import FOOTER_LABEL_ROW

logger = logging.getLogger("faipco.payroll_pdf")

_FONT_NAME = "PersianFont"
_FONT_NAME_BOLD = "PersianFont-Bold"
_font_checked = False
_font_available = False
_bold_font_available = False

# اگر فایل تنظیم‌شده در PERSIAN_FONT_PATH موجود نبود، این مسیرهای رایج در
# توزیع‌های اوبونتو/دبیان هم امتحان می‌شوند — نسخه Condensed را اول امتحان
# می‌کنیم چون فشرده‌تر است و به ساختار فشرده گزارش اصلی (فونت Tahoma) نزدیک‌تر
# می‌ماند؛ هر دو از قبل روی اکثر توزیع‌های لینوکس نصب هستند و حروف فارسی/عربی را دارند.
_FALLBACK_FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansCondensed.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
)

_PERSIAN_RANGES = (("\u0600", "\u06FF"), ("\u0750", "\u077F"), ("\uFB50", "\uFDFF"), ("\uFE70", "\uFEFF"))


def _bold_variant_path(regular_path: str) -> list[str]:
    """چند حدس معقول برای مسیر نسخه Bold همان فونت (بر اساس قراردادهای نام‌گذاری رایج)."""
    candidates = []
    if "Regular" in regular_path:
        candidates.append(regular_path.replace("Regular", "Bold"))
    if regular_path.endswith(".ttf"):
        candidates.append(regular_path[: -len(".ttf")] + "-Bold.ttf")
    return candidates


def _ensure_font_registered() -> bool:
    """فقط یک‌بار در طول عمر پردازش، Font (و در صورت امکان نسخه Bold آن) را ثبت می‌کند."""
    global _font_checked, _font_available, _bold_font_available
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
            for bold_path in _bold_variant_path(font_path):
                try:
                    pdfmetrics.registerFont(TTFont(_FONT_NAME_BOLD, bold_path))
                    _bold_font_available = True
                    break
                except Exception:  # noqa: BLE001
                    continue
            pdfmetrics.registerFontFamily(
                _FONT_NAME,
                normal=_FONT_NAME,
                bold=_FONT_NAME_BOLD if _bold_font_available else _FONT_NAME,
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
    """متن فارسی را برای نمایش صحیح (اتصال حروف + ترتیب راست‌به‌چپ) آماده می‌کند — بدون خط‌شکنی."""
    if not text or not _contains_persian(text):
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(text))
    except ImportError:
        from app.services.simple_bidi import simple_bidi, simple_reshape

        return simple_bidi(simple_reshape(text))
    except Exception:  # noqa: BLE001 - هر خطای دیگر نباید کل تولید PDF را متوقف کند
        return text


def _wrap_lines(text: str, font_name: str, font_size: float, max_width_pts: float) -> list[str]:
    """مثل _wrap_and_shape ولی خط‌های خام (هنوز Shape نشده) را برمی‌گرداند — برای ترکیب با محتوای دیگر (مثل برچسب) قبل از Shape نهایی."""
    if not text:
        return []
    safe_width_pts = max_width_pts * 0.8
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        width = pdfmetrics.stringWidth(candidate, font_name, font_size)
        if width <= safe_width_pts or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _wrap_and_shape(text: str, font_name: str, font_size: float, max_width_pts: float) -> str:
    """
    متن را بر اساس عرض واقعی (px) به چند خط می‌شکند و هر خط را جداگانه Shape
    می‌کند — چون Shape کردن کل رشته و سپس گذاشتن خط‌شکنی به عهده ReportLab
    باعث به‌هم‌ریختن ترتیب کلمات بین خطوط می‌شود (نتیجه یک بار درست‌کردن این
    مشکل واقعی بود؛ توضیح کامل در docstring بالای فایل).

    نکته حیاتی: محاسبه عرض با pdfmetrics.stringWidth همیشه دقیقاً با
    محاسبه داخلی ReportLab یکی نیست؛ اگر خیلی به مرز عرض واقعی نزدیک حساب
    کنیم، ممکن است تصور کنیم یک خط جا می‌شود ولی ReportLab موقع رسم واقعی
    دوباره آن را (این‌بار روی رشته‌ی از قبل Reverse‌شده و با ترتیب غلط)
    بشکند. برای همین با ضریب اطمینان ۰٫۸ محاسبه می‌کنیم تا تصمیم شکستن خط
    همیشه دست خودمان بماند، نه ReportLab.
    """
    return "<br/>".join(_shape(line) for line in _wrap_lines(text, font_name, font_size, max_width_pts))


def _build_label_value_html(
    label: str, value: str, font_name: str, font_bold_name: str, font_size: float, max_width_pts: float
) -> str:
    """
    برای نوار مشخصات: «<b>برچسب:</b> مقدار». نکته مهم: اگر مقدار طولانی باشد
    و به چند خط بشکند، فقط خط اولش کنار برچسب می‌آید (با عرض کمی کمتر، چون
    جای برچسب را هم اشغال کرده)؛ برچسب هرگز داخل خط‌های بعدی گم یا به انتهای
    متن منتقل نمی‌شود — چون یک‌بار امتحان شد که همه‌چیز (برچسب+مقدار) با هم
    در یک رشته Wrap شود و باعث می‌شد ReportLab خودش دوباره خط بشکند و ترتیب
    را به‌هم بریزد (همان مشکلی که در _wrap_and_shape حلش کردیم، اینجا چون
    برچسب هم به رشته اضافه می‌شد دوباره سر بلند کرده بود).
    """
    label_clean = label.rstrip(": ：")
    label_shaped = _shape(label_clean)
    label_prefix_width = pdfmetrics.stringWidth(f"{label_clean}: ", font_bold_name, font_size)
    reduced_width = max(max_width_pts - label_prefix_width, max_width_pts * 0.3)

    value_lines = _wrap_lines(value, font_name, font_size, reduced_width)
    if not value_lines:
        return f"<b>{label_shaped}:</b>"

    lines_html = [f"<b>{label_shaped}:</b> {_shape(value_lines[0])}"]
    lines_html.extend(_shape(line) for line in value_lines[1:])
    return "<br/>".join(lines_html)




def render_payroll_receipt_pdf(
    *,
    notice_title: str,
    employee_name: str,
    personnel_code: str,
    site_name: str | None,
    fields: list[dict],
) -> bytes:
    """
    fields: خروجی ParsedReceiptItem.fields — لیست تخت {"label", "value", "section"}.
    "section" یکی از این‌هاست:
      ""            → مشخصات فیش (نوار بالای صفحه)
      "__meta__"     → فقط یک ردیف با label="__report_title__" (عنوان بالای فیش، مثل «Faipco»)
      "__footer__"   → جمع‌بندی پایین فیش؛ اگر ردیف "column" هم داشته باشد،
                       دقیقاً زیر همان ستون اصلی چیده می‌شود
      هر چیز دیگر    → نام یکی از ستون‌های اصلی («وام»/«کسور»/«مزایا»/«سایر»
                       یا Section ناشناخته یک سازمان دیگر)
    """
    has_font = _ensure_font_registered()
    font_name = _FONT_NAME if has_font else "Helvetica"
    font_bold = _FONT_NAME_BOLD if has_font else "Helvetica-Bold"

    # ---------- بازسازی فیلدهای تخت به بخش‌های معنادار ----------
    report_title: str | None = None
    header_rows: list[dict] = []
    footer_rows: list[dict] = []
    section_rows: dict[str, list[dict]] = {}
    section_order: list[str] = []
    for row in fields:
        section = row.get("section", "")
        if section == "__meta__" and row.get("label") == "__report_title__":
            report_title = row.get("value")
        elif section == "":
            header_rows.append(row)
        elif section == "__footer__":
            footer_rows.append(row)
        else:
            if section not in section_rows:
                section_rows[section] = []
                section_order.append(section)
            section_rows[section].append(row)

    fixed_columns = ["وام", "کسور", "مزایا", "سایر"]
    extra_columns = [s for s in section_order if s not in fixed_columns]
    column_titles = fixed_columns + extra_columns

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
        rightMargin=8 * mm,
        leftMargin=8 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
    )

    # اندازه‌ها و رنگ‌ها دقیقاً از روی CSS خودِ گزارش اصلی (خروجی MHTML همان
    # سیستم) خوانده شده‌اند: عنوان ۱۲pt Bold، برچسب نوار مشخصات ۹pt Bold/مقدار
    # ۹pt عادی با پس‌زمینه #d3d3d3، ردیف‌های جدول اصلی ۸pt با Padding فقط ۲pt.
    title_style = ParagraphStyle("PayrollTitle", fontName=font_bold, fontSize=12, alignment=TA_CENTER, spaceAfter=4)
    subtitle_style = ParagraphStyle(
        "PayrollSubtitle", fontName=font_bold, fontSize=10, alignment=TA_CENTER, spaceAfter=6
    )
    info_cell_style = ParagraphStyle("InfoCell", fontName=font_name, fontSize=9, alignment=TA_RIGHT, leading=11)
    col_header_style = ParagraphStyle("ColHeader", fontName=font_bold, fontSize=9, alignment=TA_CENTER)
    row_label_style = ParagraphStyle("RowLabel", fontName=font_name, fontSize=8, alignment=TA_RIGHT, leading=9.2)
    row_value_style = ParagraphStyle("RowValue", fontName=font_name, fontSize=8, alignment=TA_RIGHT, leading=9.2)
    footer_label_style = ParagraphStyle("FooterLabel", fontName=font_bold, fontSize=8, alignment=TA_RIGHT)
    footer_value_style = ParagraphStyle("FooterValue", fontName=font_name, fontSize=8, alignment=TA_RIGHT)

    story = []

    # ---------- عنوان و زیرعنوان ----------
    story.append(Paragraph(_shape(report_title or site_name or notice_title or "فیش حقوقی"), title_style))
    if month_value or year_value:
        subtitle = f"فیش حقوق {month_value or ''} ماه سال {year_value or ''}".replace("  ", " ").strip()
        story.append(Paragraph(_shape(subtitle), subtitle_style))

    # ---------- نوار مشخصات: پس‌زمینه طوسی کم‌رنگ، از راست: کد پرسنلی، نام، مرکز هزینه ----------
    if header_rows:
        info_col_width_pts = (doc.width / len(header_rows)) - 12  # منهای Padding داخلی سلول
        info_cells = []
        for row in header_rows:
            cell_html = _build_label_value_html(row["label"], row["value"], font_name, font_bold, 9, info_col_width_pts)
            info_cells.append(Paragraph(cell_html, info_cell_style))
        # ترتیب طبیعی سند (مرکز هزینه، نام، کد پرسنلی) از چپ به راست همان
        # چیزی است که در نمایش راست‌به‌چپ، کد پرسنلی را در سمت راست می‌گذارد
        # — پس هیچ Reverse ای لازم نیست.
        info_table = Table([info_cells], colWidths=[doc.width / len(info_cells)] * len(info_cells))
        info_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#d3d3d3")),
                    ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(info_table)
        story.append(Spacer(1, 1.5 * mm))

    # ---------- جدول اصلی ۴ ستونی ----------
    # نکته حیاتی ۱ (پایداری بین صفحات): این جدول را به‌جای «۴ سلول که هرکدام
    # یک جدول تودرتوی کامل داخلش است» با ۸ ستون تخت (مقدار+برچسب برای هرکدام
    # از ۴ ستون اصلی) و چند ردیف واقعی می‌سازیم؛ یک جدول تودرتوی خیلی بلند در
    # یک سلول اگر از یک صفحه بلندتر شود، ReportLab نمی‌تواند آن را بین صفحات
    # بشکند و کل تولید PDF متوقف می‌شود، ولی جدول تخت با ردیف واقعی می‌تواند.
    #
    # نکته حیاتی ۲ (عرض هر ستون): در گزارش اصلی، عرض هر ۴ ستون یکسان نیست —
    # ستون «سایر» چون برچسب‌های بلندتری دارد (مثلاً «دستمزد و مزایای مشمول
    # بیمه تامین اجتماعی»)، عرض بیشتری می‌گیرد. این نسبت‌ها از CSS واقعی
    # همان گزارش استخراج شده‌اند.
    column_weights = {"وام": 0.19, "کسور": 0.21, "مزایا": 0.24, "سایر": 0.36}
    default_weight = 1 / len(column_titles)
    total_weight = sum(column_weights.get(t, default_weight) for t in column_titles)

    col_width_map = {
        t: doc.width * (column_weights.get(t, default_weight) / total_weight) for t in column_titles
    }
    value_width_map = {t: w * 0.4 for t, w in col_width_map.items()}
    label_width_map = {t: w * 0.6 for t, w in col_width_map.items()}
    label_col_width_pts_map = {t: label_width_map[t] - 6 for t in column_titles}

    max_rows = max((len(section_rows.get(title, [])) for title in column_titles), default=0)

    header_row = []
    span_commands = []
    for i, title in enumerate(column_titles):
        # نکته مهم: عمداً رشته خام (نه Paragraph) استفاده می‌شود — وقتی یک
        # Paragraph داخل سلولی قرار می‌گیرد که با SPAN بین دو ستون با عرض
        # نامساوی (مقدار ۴۰٪ / برچسب ۶۰٪) ادغام شده، مرکز‌چینی داخلی خودِ
        # Paragraph گاهی بر اساس عرض فقط اولین زیرستون محاسبه می‌شود، نه کل
        # عرض ادغام‌شده — نتیجه‌اش این بود که عنوان هر ستون به‌جای وسط واقعی
        # ستون، کمی به چپ متمایل می‌شد. رشته خام + ALIGN در TableStyle این
        # مشکل را ندارد چون مستقیماً نسبت به عرض واقعی سلول (بعد از Span)
        # وسط‌چین می‌شود.
        header_row.append(_shape(title))
        header_row.append("")
        span_commands.append(("SPAN", (i * 2, 0), (i * 2 + 1, 0)))

    table_data = [header_row]
    for row_idx in range(max_rows):
        row_cells = []
        for title in column_titles:
            rows = section_rows.get(title, [])
            if row_idx < len(rows):
                r = rows[row_idx]
                row_cells.append(Paragraph(_shape(r["value"]), row_value_style))
                row_cells.append(
                    Paragraph(
                        _wrap_and_shape(r["label"], font_name, 8, label_col_width_pts_map[title]), row_label_style
                    )
                )
            else:
                row_cells.append("")
                row_cells.append("")
        table_data.append(row_cells)

    col_widths = []
    for title in column_titles:
        col_widths.extend([value_width_map[title], label_width_map[title]])

    # خط ضخیم‌تر بین هر دو ستون اصلی مجاور (نه بین زوج مقدار/برچسب خودشان)
    group_dividers = [
        ("LINEAFTER", (i * 2 + 1, 0), (i * 2 + 1, -1), 0.7, colors.black)
        for i in range(len(column_titles) - 1)
    ]

    main_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    main_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
                *group_dividers,
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d3d3d3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), font_bold),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("TOPPADDING", (0, 0), (-1, 0), 3),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
                ("TOPPADDING", (0, 1), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 1.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(main_table)

    # ---------- نوار جمع‌بندی پایین: هر مقدار دقیقاً زیر همان ستون اصلی‌اش ----------
    if footer_rows:
        story.append(Spacer(1, 1 * mm))

        # هر ستون اصلی می‌تواند حداکثر ۲ ردیف جمع‌بندی داشته باشد (مثلاً زیر
        # «مزایا»: هم «جمع مزایا» (ردیف اول) هم «خالص پرداختی» (ردیف دوم)؛
        # زیر «وام»: هم «جمع اقساط وام» (ردیف اول) هم «شماره حساب» (ردیف دوم)).
        # موقعیت هر برچسب از FOOTER_LABEL_ROW صریحاً معلوم است — مستقل از
        # ترتیب پیدا شدنش (مثلاً اگر پرسنلی وام نداشته باشد، «شماره حساب»
        # باید همچنان در ردیف دوم بماند، نه این‌که به ردیف اول منتقل شود).
        footer_grid: dict[str, dict[int, dict]] = {title: {} for title in column_titles}
        max_footer_row = -1
        for row in footer_rows:
            col = row.get("column")
            if col not in footer_grid:
                col = column_titles[0]
            row_idx = FOOTER_LABEL_ROW.get(row["label"], 0)
            footer_grid[col][row_idx] = row
            max_footer_row = max(max_footer_row, row_idx)

        if max_footer_row >= 0:
            # برخلاف جدول اصلی، در نوار جمع‌بندی برچسب‌ها همیشه کوتاهند
            # («جمع کسور»، «خالص پرداختی») ولی مقدارها می‌توانند اعداد بزرگ
            # باشند — پس نسبت عرض برعکس می‌شود (به مقدار فضای بیشتر داده می‌شود).
            footer_value_width_map = {t: w * 0.58 for t, w in col_width_map.items()}
            footer_label_width_map = {t: w * 0.42 for t, w in col_width_map.items()}
            footer_label_width_pts_map = {t: footer_label_width_map[t] - 6 for t in column_titles}

            footer_table_data = []
            for row_idx in range(max_footer_row + 1):
                table_row = []
                for title in column_titles:
                    r = footer_grid.get(title, {}).get(row_idx)
                    if r:
                        cell = Table(
                            [
                                [
                                    Paragraph(_shape(r["value"]), footer_value_style),
                                    Paragraph(
                                        _wrap_and_shape(
                                            r["label"], font_name, 8, footer_label_width_pts_map[title]
                                        ),
                                        footer_label_style,
                                    ),
                                ]
                            ],
                            colWidths=[footer_value_width_map[title], footer_label_width_map[title]],
                            style=TableStyle(
                                [
                                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#d3d3d3")),
                                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ]
                            ),
                        )
                        table_row.append(cell)
                    else:
                        table_row.append("")
                footer_table_data.append(table_row)

            footer_table = Table(footer_table_data, colWidths=[col_width_map[t] for t in column_titles])
            footer_table.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ]
                )
            )
            story.append(footer_table)

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
