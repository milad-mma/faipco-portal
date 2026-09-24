"""
تولید PDF «فیش کارکرد» با ReportLab.

یک تابع عمومی دارد (render_attendance_card_pdf) که از فیلدهای {label, value}
یک کارت A4 می‌سازد:

- سربرگ: لوگو به‌صورت یک نشان کوچک در گوشه بالا-چپ کارت، و عنوان
  «فیش کارکرد» + زیرعنوان ماه/سال دقیقاً وسط عرض کارت (مستقل از لوگو).
- جدول ۴ ستونی با چیدمان فیزیکی چپ‌به‌راست:
  [مقدارِچپ، برچسبِ‌چپ، مقدارِراست، برچسبِ‌راست]. ReportLab برخلاف HTML با
  dir="rtl" ترتیب ستون‌ها را برعکس نمی‌کند، پس همین ترتیب فیزیکی صریحاً ساخته می‌شود.
- برچسب و مقدار هر دو Bold هستند؛ با تگ <b> داخل متن، نه با تنظیم fontName
  روی نسخه‌ی Bold فونت (آن روش در برخی سرورها با خطای ReportLab
  «Can't map determine family/bold/italic» کرش می‌کند).
- سلول‌های مقدارِ «نام» و «کد پرسنلی» پس‌زمینه‌ی روشن (highlight) دارند.

از همان زیرساخت فونت/Shape فارسی payroll_pdf.py استفاده می‌شود.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.payroll_pdf import _FONT_NAME, _ensure_font_registered, _shape, _wrap_and_shape

_NAVY = colors.HexColor("#2b3990")  # رنگ اصلی عنوان، برچسب‌ها و قاب جدول
_LABEL_BG = colors.HexColor("#fafbfd")  # پس‌زمینه‌ی ستون برچسب و سلول‌های highlight
_GRID_COLOR = colors.HexColor("#c7cbe0")  # رنگ خطوط داخلی جدول
_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "images" / "faipco-logo.png"  # app/assets/images/...

# کلیدهای فیلدها به ترتیب ردیف‌ها، برای نیمه‌ی راست و نیمه‌ی چپ کارت
_RIGHT_COLUMN = ["name", "totalWork", "nightDays", "absence", "unpaidLeave", "deduction", "dailyMission", "unit"]
_LEFT_COLUMN = ["code", "overtime", "fridayHours", "sickLeave", "socialSick", "bonusLeave", "leaveUsed", "remainLeave"]
_HIGHLIGHT_KEYS = {"name", "code"}  # مقدار این دو کلید پس‌زمینه‌ی روشن می‌گیرد


def render_attendance_card_pdf(
    *,
    employee_name: str,
    month_year: str,
    fields: list[dict],  # [{"label": ..., "value": ...}]
) -> bytes:
    """
    PDF یک فیش کارکرد را می‌سازد و بایت‌های آن را برمی‌گرداند.
    ورودی: نام پرسنل، متن ماه/سال (زیرعنوان) و ۱۶ فیلد برچسب‌دار به ترتیب _FIELD_LABELS.
    ابتدا با لوگو ساخته می‌شود؛ اگر شکست خورد، بدون لوگو تکرار می‌شود.
    """
    def _build(include_logo: bool) -> bytes:
        """کل PDF را می‌سازد؛ include_logo مشخص می‌کند لوگو روی Canvas کشیده شود یا نه."""
        has_font = _ensure_font_registered()
        font_name = _FONT_NAME if has_font else "Helvetica"  # اگر فونت فارسی در دسترس نبود

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=25 * mm,
            bottomMargin=25 * mm,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
        )

        # استایل‌های متن؛ فونت "-Bold" هرگز به‌عنوان fontName تنظیم نمی‌شود (دلیل بالای فایل)،
        # Bold با تگ <b> داخل متن Paragraph اعمال می‌شود
        title_style = ParagraphStyle(
            "cardTitle", fontName=font_name, fontSize=15, alignment=TA_CENTER, textColor=_NAVY, leading=19
        )
        subtitle_style = ParagraphStyle(
            "cardSubtitle", fontName=font_name, fontSize=10.5, alignment=TA_CENTER, textColor=colors.HexColor("#333333")
        )
        label_style = ParagraphStyle(
            "cellLabel", fontName=font_name, fontSize=9.5, alignment=TA_RIGHT, textColor=_NAVY, leading=13
        )
        value_style = ParagraphStyle(
            "cellValue", fontName=font_name, fontSize=9.5, alignment=TA_CENTER, leading=13
        )

        story = []

        # ---------- سربرگ ----------
        # لوگو با Callback مستقیم روی Canvas کشیده می‌شود (نه به‌عنوان Flowable داخل
        # جریان متن) تا مثل position:absolute در گوشه‌ی بالا-چپ قرار بگیرد و ارتفاعش
        # هیچ فاصله‌ی اضافه‌ای بین سربرگ و جدول ایجاد نکند
        logo_size = 26 * mm

        def _draw_logo(canvas, _doc):
            """لوگو را در گوشه‌ی بالا-چپ صفحه می‌کشد (اگر فعال و فایل موجود باشد)."""
            if include_logo and _LOGO_PATH.exists():
                canvas.saveState()
                x = _doc.leftMargin
                y = _doc.pagesize[1] - _doc.topMargin - logo_size + 6 * mm  # کمی بالاتر از حاشیه‌ی بالا
                canvas.drawImage(
                    str(_LOGO_PATH), x, y, width=logo_size, height=logo_size, mask="auto", preserveAspectRatio=True
                )
                canvas.restoreState()

        # عنوان و زیرعنوان وسط‌چین
        story.append(Paragraph(f"<b>{_shape('فیش کارکرد')}</b>", title_style))
        story.append(Paragraph(_shape(month_year), subtitle_style))
        story.append(Spacer(1, 4 * mm))

        # ---------- جدول اصلی ----------
        # فیلدهای ورودی به ترتیب _FIELD_LABELS هستند؛ اینجا به کلید نگاشت می‌شوند
        by_key = {}
        field_keys_in_order = [
            "name", "code", "totalWork", "nightDays", "overtime", "fridayHours", "leaveUsed",
            "sickLeave", "socialSick", "unpaidLeave", "bonusLeave", "absence", "deduction",
            "dailyMission", "unit", "remainLeave",
        ]
        for key, item in zip(field_keys_in_order, fields):
            by_key[key] = item

        # نسبت عرض ستون‌ها: مقدار ≈۲۳٪ و برچسب ≈۲۹٪ از عرض کارت (هر جفت ۵۲٪ و بعد نرمال‌شده به نصف عرض)
        pair_width = doc.width / 2
        value_width = pair_width * (23 / 52)
        label_width = pair_width * (29 / 52)
        col_widths = [value_width, label_width, value_width, label_width]

        table_data = []
        highlight_cells = []  # [(col, row), ...] برای پس‌زمینه‌ی روشن مقدار نام/کد
        max_rows = max(len(_RIGHT_COLUMN), len(_LEFT_COLUMN))
        # هر ردیف جدول یک فیلد از ستون راست و یک فیلد از ستون چپ دارد
        for i in range(max_rows):
            right_key = _RIGHT_COLUMN[i] if i < len(_RIGHT_COLUMN) else None
            left_key = _LEFT_COLUMN[i] if i < len(_LEFT_COLUMN) else None

            def _cell_pair(key):
                """برای یک کلید، جفت (Paragraph برچسب، Paragraph مقدار) می‌سازد؛ کلید نبود -> دو سلول خالی."""
                if key and key in by_key:
                    item = by_key[key]
                    label_p = Paragraph(f"<b>{_shape(item['label'])}</b>", label_style)
                    value_text = _wrap_and_shape(str(item["value"]), font_name, 9.5, value_width - 6)
                    value_p = Paragraph(f"<b>{value_text}</b>", value_style)
                    return label_p, value_p
                return "", ""

            left_label, left_value = _cell_pair(left_key)
            right_label, right_value = _cell_pair(right_key)

            # چیدمان فیزیکی چپ‌به‌راست: [مقدارِچپ، برچسبِ‌چپ، مقدارِراست، برچسبِ‌راست]
            # ستون ۰ مقدارِ چپ و ستون ۲ مقدارِ راست است
            row_index = len(table_data)
            if left_key in _HIGHLIGHT_KEYS:
                highlight_cells.append((0, row_index))
            if right_key in _HIGHLIGHT_KEYS:
                highlight_cells.append((2, row_index))

            table_data.append([left_value, left_label, right_value, right_label])

        # استایل جدول: خطوط داخلی، پس‌زمینه‌ی ستون برچسب‌ها، فاصله‌ی داخلی و قاب سرمه‌ای
        table = Table(table_data, colWidths=col_widths, repeatRows=0)
        style_commands = [
            ("GRID", (0, 0), (-1, -1), 0.5, _GRID_COLOR),
            ("BACKGROUND", (1, 0), (1, -1), _LABEL_BG),  # ستون برچسبِ‌چپ
            ("BACKGROUND", (3, 0), (3, -1), _LABEL_BG),  # ستون برچسبِ‌راست
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("BOX", (0, 0), (-1, -1), 1.5, _NAVY),
        ]
        # پس‌زمینه‌ی روشن برای سلول‌های مقدار نام/کد
        for col, row_idx in highlight_cells:
            style_commands.append(("BACKGROUND", (col, row_idx), (col, row_idx), _LABEL_BG))
        table.setStyle(TableStyle(style_commands))
        story.append(table)

        doc.build(story, onFirstPage=_draw_logo, onLaterPages=_draw_logo)  # لوگو روی هر صفحه
        return buffer.getvalue()

    try:
        return _build(include_logo=True)
    except Exception:
        # اگر ساخت PDF با لوگو شکست بخورد (مثلاً فایل لوگو موجود نیست یا خراب است)،
        # بدون لوگو ساخته می‌شود تا یک عنصر تزئینی دانلود کارت را با خطای ۵۰۰ از کار نیندازد
        return _build(include_logo=False)
