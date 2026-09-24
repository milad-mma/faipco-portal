"""
تولید PDF فیش حقوقی از روی فیلدهای خام استخراج‌شده (payroll_xml.py یا
payroll_xlsx.py). طرح‌بندی مطابق قالب فیش سازمان: عنوان بالای صفحه، زیرعنوان «فیش حقوق {ماه} ماه سال {سال}»، یک نوار
مشخصات با پس‌زمینه طوسی کم‌رنگ (کد پرسنلی/نام/مرکز هزینه)، جدول ۴ ستونی اصلی
(وام | کسور | مزایا | سایر)، و یک نوار جمع‌بندی پایین که هر مقدارش دقیقاً
زیر همان ستون اصلی مربوطه‌اش می‌نشیند.

پشتیبانی از فارسی: چون فونت‌های پیش‌فرض ReportLab (Helvetica) حروف فارسی/عربی
ندارند، از app.core.config.PERSIAN_FONT_PATH (یا در نبودش، DejaVu Sans که
معمولاً از قبل روی سرور نصب است) یک فونت TTF بارگذاری و برای شکل‌دهی صحیح
حروف از arabic_reshaper + python-bidi (یا در نبودشان، simple_bidi.py داخلی)
استفاده می‌شود.

متن‌های طولانی: Bidi/Reshape روی رشته اعمال می‌شود و خط‌شکنی ReportLab روی رشته‌ی
Reverse‌شده ترتیب کلمات بین خط‌ها را به‌هم می‌ریزد؛ پس برچسب‌های طولانی از قبل بر اساس
عرض ستون به چند خط شکسته و هر خط جداگانه Shape می‌شود (_wrap_and_shape).
توابع _ensure_font_registered، _shape و _wrap_and_shape در attendance_card_pdf.py هم استفاده می‌شوند.
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

# نام‌های ثبت فونت در ReportLab و وضعیت ثبت (یک‌بار در طول عمر پردازش)
_FONT_NAME = "PersianFont"
_FONT_NAME_BOLD = "PersianFont-Bold"
_font_checked = False
_font_available = False
_bold_font_available = False

# اگر فایل PERSIAN_FONT_PATH موجود نبود، این مسیرهای رایج اوبونتو/دبیان امتحان می‌شوند.
# نسخه Condensed اول است چون فشرده‌تر و به فونت Tahoma گزارش اصلی نزدیک‌تر است؛
# هر دو روی اکثر توزیع‌های لینوکس نصب‌اند و حروف فارسی/عربی را دارند.
_FALLBACK_FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansCondensed.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
)

# بازه‌های یونیکد عربی/فارسی و فرم‌های نمایشی؛ برای تشخیص نیاز به Shape
_PERSIAN_RANGES = (("\u0600", "\u06FF"), ("\u0750", "\u077F"), ("\uFB50", "\uFDFF"), ("\uFE70", "\uFEFF"))


def _bold_variant_path(regular_path: str) -> list[str]:
    """ورودی: مسیر فونت Regular. خروجی: لیست مسیرهای حدسی نسخه Bold (Regular→Bold یا پسوند -Bold.ttf)."""
    candidates = []
    if "Regular" in regular_path:
        candidates.append(regular_path.replace("Regular", "Bold"))
    if regular_path.endswith(".ttf"):
        candidates.append(regular_path[: -len(".ttf")] + "-Bold.ttf")
    return candidates


def _ensure_font_registered() -> bool:
    """
    فونت فارسی (و در صورت امکان نسخه Bold) را فقط یک‌بار در طول عمر پردازش ثبت می‌کند؛
    اول PERSIAN_FONT_PATH و بعد مسیرهای جایگزین. خروجی: True اگر فونتی ثبت شد.
    """
    global _font_checked, _font_available, _bold_font_available
    if _font_checked:
        return _font_available
    _font_checked = True

    # امتحان مسیرها به ترتیب؛ اولین مسیر موفق ثبت می‌شود
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
            # تلاش برای ثبت نسخه Bold همان فونت (اختیاری)
            for bold_path in _bold_variant_path(font_path):
                try:
                    pdfmetrics.registerFont(TTFont(_FONT_NAME_BOLD, bold_path))
                    _bold_font_available = True
                    break
                except Exception:  # noqa: BLE001
                    continue
            # ثبت خانواده برای تگ <b> در Paragraph؛ بدون Bold، همان Regular استفاده می‌شود
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
    """ورودی: متن. خروجی: True اگر حداقل یک کاراکتر در بازه‌های _PERSIAN_RANGES باشد."""
    return any(any(lo <= ch <= hi for lo, hi in _PERSIAN_RANGES) for ch in text)


def _shape(text: str) -> str:
    """
    ورودی: متن. برای متن فارسی اتصال حروف و ترتیب راست‌به‌چپ را اعمال می‌کند (بدون خط‌شکنی).
    اول arabic_reshaper + python-bidi و در نبودشان simple_bidi داخلی؛ متن غیرفارسی یا خطا = متن اصلی.
    """
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
    """
    ورودی: متن، فونت، اندازه و عرض مجاز (pt). متن را کلمه‌به‌کلمه بر اساس عرض رسم‌شده به خطوط می‌شکند.
    خروجی: خط‌های خام (Shape‌نشده) — برای ترکیب با محتوای دیگر (مثل برچسب) پیش از Shape نهایی.
    """
    if not text:
        return []
    safe_width_pts = max_width_pts * 0.8  # ضریب اطمینان تا ReportLab خودش خط را دوباره نشکند
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    # افزودن کلمه به خط جاری تا وقتی عرض مجاز رد نشود؛ کلمه‌ی تنهای بلند هم در خط خودش می‌ماند
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
    ورودی: متن، فونت، اندازه و عرض مجاز (pt). متن را به چند خط می‌شکند و هر خط را جداگانه Shape می‌کند
    تا ترتیب کلمات بین خطوط حفظ شود. خروجی: HTML خطوط با <br/> برای Paragraph.
    عرض با ضریب ۰٫۸ حساب می‌شود (در _wrap_lines) چون stringWidth با محاسبه‌ی داخلی ReportLab دقیقاً یکی نیست.
    """
    return "<br/>".join(_shape(line) for line in _wrap_lines(text, font_name, font_size, max_width_pts))


def _build_label_value_html(
    label: str, value: str, font_name: str, font_bold_name: str, font_size: float, max_width_pts: float
) -> str:
    """
    ورودی: برچسب، مقدار، فونت‌ها، اندازه و عرض سلول. HTML «برچسب: مقدار» را برای نوار مشخصات
    با ترتیب راست‌به‌چپ درست می‌سازد. خروجی: HTML برای Paragraph.

    ReportLab هر خط را چپ‌به‌راست رسم و با TA_RIGHT به راست می‌چسباند، پس آنچه آخر رشته
    می‌آید راست‌ترین است؛ برای همین برچسب در انتهای خط اول قرار می‌گیرد.
    «:» همراه برچسب یک‌جا Shape می‌شود (_shape(f"{label}:")) تا Bidi آن را کنار برچسب
    نگه دارد و به انتهای خط پرتاب نشود.
    مقدار طولانی چندخطی می‌شود: فقط خط اول (با عرض کمتر) کنار برچسب است و بقیه ادامه‌ی مقدارند.
    """
    label_clean = label.rstrip(": ：")
    label_with_colon_shaped = _shape(f"{label_clean}:")
    label_prefix_width = pdfmetrics.stringWidth(f"{label_clean}: ", font_bold_name, font_size)  # عرض اشغال‌شده توسط برچسب
    reduced_width = max(max_width_pts - label_prefix_width, max_width_pts * 0.3)  # حداقل ۳۰٪ عرض برای مقدار

    value_lines = _wrap_lines(value, font_name, font_size, reduced_width)
    if not value_lines:
        return f"<b>{label_with_colon_shaped}</b>"

    lines_html = [f"{_shape(value_lines[0])} <b>{label_with_colon_shaped}</b>"]  # برچسب در انتهای رشته = سمت راست خط
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
    ورودی: عنوان اطلاعیه، نام/کد پرسنل، نام Site و fields. خروجی: بایت‌های PDF فیش (A4).
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
    # _FONT_NAME_BOLD مستقیماً به‌عنوان fontName یک ParagraphStyle استفاده نمی‌شود:
    # ReportLab در Paragraph نام فونت را با ps2tt() به خانواده‌ی ثبت‌شده (فقط _FONT_NAME)
    # نگاشت می‌کند و نام مستقیم فونت Bold ممکن است خطای «Can't map determine family/bold/italic»
    # بدهد. پس «Bold» در Styleها همان فونت عادی است و تأکید با سایز فونت انجام می‌شود.
    font_bold = font_name if has_font else "Helvetica-Bold"

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

    # ترتیب ستون‌ها: ۴ ستون ثابت و سپس Sectionهای ناشناخته به ترتیب ظهور
    fixed_columns = ["وام", "کسور", "مزایا", "سایر"]
    extra_columns = [s for s in section_order if s not in fixed_columns]
    column_titles = fixed_columns + extra_columns

    def pop_header(*label_substrings: str) -> str | None:
        """ورودی: زیررشته‌های برچسب. اولین ردیف مشخصات منطبق را از header_rows حذف و مقدارش را برمی‌گرداند."""
        for i, row in enumerate(header_rows):
            if any(s in row["label"] for s in label_substrings):
                return header_rows.pop(i)["value"]
        return None

    # سال و ماه از نوار مشخصات جدا و در زیرعنوان نمایش داده می‌شوند
    year_value = pop_header("سال")
    month_value = pop_header("ماه")

    # سند A4 با حاشیه ۸ میلی‌متر از هر طرف
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=8 * mm,
        leftMargin=8 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
    )

    # اندازه‌ها و رنگ‌ها مطابق CSS گزارش اصلی (خروجی MHTML): عنوان ۱۲pt، نوار مشخصات ۹pt
    # با پس‌زمینه #d3d3d3، ردیف‌های جدول اصلی ۸pt با Padding حدود ۲pt.
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
    story.append(Paragraph(_shape(report_title or site_name or notice_title or "فیش حقوقی"), title_style))  # اولویت عنوان: عنوان گزارش، Site، عنوان اطلاعیه
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
        # ترتیب سلول‌ها همان ترتیب سند است (چپ به راست: مرکز هزینه، نام، کد پرسنلی)
        # که کد پرسنلی را در سمت راست قرار می‌دهد؛ Reverse لازم نیست.
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
    # جدول تخت با دو ستون (مقدار + برچسب) به‌ازای هر ستون اصلی و ردیف‌های واقعی ساخته می‌شود،
    # نه جدول‌های تودرتو در یک سلول، تا ReportLab بتواند آن را بین صفحات بشکند.
    # عرض ستون‌ها یکسان نیست و نسبت‌ها از CSS گزارش اصلی گرفته شده‌اند؛ «سایر» به‌خاطر
    # برچسب‌های بلندتر (مثل «دستمزد و مزایای مشمول بیمه تامین اجتماعی») پهن‌تر است.
    column_weights = {"وام": 0.19, "کسور": 0.21, "مزایا": 0.24, "سایر": 0.36}
    default_weight = 1 / len(column_titles)  # وزن Sectionهای ناشناخته
    total_weight = sum(column_weights.get(t, default_weight) for t in column_titles)

    col_width_map = {
        t: doc.width * (column_weights.get(t, default_weight) / total_weight) for t in column_titles
    }
    # عرض ستون «مقدار» ۴۰٪ ستون اصلی است، با یک حداقل مطلق برای ستون باریک «وام» تا اعداد
    # ۱۰ تا ۱۳ رقمی با جداکننده هزارگان وسط عدد شکسته نشوند (برچسب‌های «وام» کوتاه‌اند).
    # ۵۸pt = حدود ۴۶٫۸pt عرض بزرگ‌ترین عدد با Tahoma + ۴pt Padding + حاشیه اطمینان.
    # این حداقل فقط برای «وام» است؛ اعمال آن روی «کسور» و «مزایا» برچسب‌هایشان را بیشتر می‌شکند
    # و ارتفاع جدول را زیاد می‌کند.
    min_value_width_pts_by_column = {"وام": 58}
    value_width_map = {
        t: max(w * 0.4, min_value_width_pts_by_column.get(t, 0)) for t, w in col_width_map.items()
    }
    label_width_map = {t: col_width_map[t] - value_width_map[t] for t in column_titles}
    label_col_width_pts_map = {t: label_width_map[t] - 6 for t in column_titles}  # منهای Padding برای خط‌شکنی برچسب

    max_rows = max((len(section_rows.get(title, [])) for title in column_titles), default=0)  # تعداد ردیف جدول = بلندترین ستون

    # ردیف سرستون: عنوان هر ستون اصلی روی دو زیرستون (مقدار + برچسب) ادغام می‌شود
    header_row = []
    span_commands = []
    for i, title in enumerate(column_titles):
        # رشته خام (نه Paragraph) استفاده می‌شود: Paragraph در سلول SPAN‌شده با زیرستون‌های
        # نامساوی بر اساس عرض اولین زیرستون وسط‌چین می‌شود، ولی رشته خام + ALIGN در
        # TableStyle نسبت به عرض کامل سلول ادغام‌شده وسط‌چین می‌شود.
        header_row.append(_shape(title))
        header_row.append("")
        span_commands.append(("SPAN", (i * 2, 0), (i * 2 + 1, 0)))

    # ردیف‌های داده: برای هر ستون اصلی (مقدار، برچسب) یا دو سلول خالی
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

    main_table = Table(table_data, colWidths=col_widths, repeatRows=1)  # تکرار سرستون در صفحات بعد
    main_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
                *group_dividers,
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d3d3d3")),  # پس‌زمینه طوسی فقط برای سرستون
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

        # هر ستون اصلی حداکثر ۲ ردیف جمع‌بندی دارد (مثلاً زیر «مزایا»: «جمع مزایا» و «خالص پرداختی»؛
        # زیر «وام»: «جمع اقساط وام» و «شماره حساب»). ردیف هر برچسب از FOOTER_LABEL_ROW تعیین می‌شود،
        # مستقل از ترتیب پیدا شدنش (مثلاً «شماره حساب» حتی بدون وام در ردیف دوم می‌ماند).
        # footer_grid: ستون -> {شماره ردیف -> ردیف جمع‌بندی}
        footer_grid: dict[str, dict[int, dict]] = {title: {} for title in column_titles}
        max_footer_row = -1
        for row in footer_rows:
            col = row.get("column")
            if col not in footer_grid:
                col = column_titles[0]  # ستون نامشخص: زیر اولین ستون
            row_idx = FOOTER_LABEL_ROW.get(row["label"], 0)
            footer_grid[col][row_idx] = row
            max_footer_row = max(max_footer_row, row_idx)

        if max_footer_row >= 0:
            # در نوار جمع‌بندی برچسب‌ها کوتاه‌اند («جمع کسور»، «خالص پرداختی») و مقدارها اعداد بزرگ؛
            # پس برخلاف جدول اصلی، سهم بیشتر عرض (۵۸٪) به مقدار داده می‌شود.
            footer_value_width_map = {t: w * 0.58 for t, w in col_width_map.items()}
            footer_label_width_map = {t: w * 0.42 for t, w in col_width_map.items()}
            footer_label_width_pts_map = {t: footer_label_width_map[t] - 6 for t in column_titles}

            # هر سلول پر، یک جدول کوچک (مقدار، برچسب) است؛ سلول‌های بدون جمع‌بندی خالی می‌مانند
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
                                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                                ]
                            ),
                        )
                        table_row.append(cell)
                    else:
                        table_row.append("")
                footer_table_data.append(table_row)

            # پس‌زمینه طوسی روی کل جدول بیرونی اعمال می‌شود تا ستون‌های خالی (مثل «سایر» بدون
            # جمع‌بندی) هم یکدست طوسی باشند، مثل نوار مشخصات. عرض ستون‌ها همان جدول اصلی است.
            footer_table = Table(footer_table_data, colWidths=[col_width_map[t] for t in column_titles])
            footer_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#d3d3d3")),
                        ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            story.append(footer_table)

    # هشدار انگلیسی در انتهای PDF وقتی فونت فارسی روی سرور پیدا نشد
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
