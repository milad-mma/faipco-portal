"""
تولید PDF «فیش کارکرد» — بازسازیِ دقیق طراحی نمونه HTML مرجع:

- سربرگ: لوگو به‌صورت یک نشان کوچک در گوشه بالا-چپ کارت (نه وسط)، و عنوان
  «فیش کارکرد» + زیرعنوان ماه/سال، دقیقاً وسط عرض کارت (مستقل از لوگو).
- جدول ۴ ستونی: چون مرجع HTML با dir="rtl" است، ترتیب DOM هر ردیف
  (برچسبِ‌راست، مقدارِراست، برچسبِ‌چپ، مقدارِچپ) در نمایش فیزیکی برعکس
  می‌شود؛ یعنی چیدمان فیزیکی چپ‌به‌راست واقعی: [مقدارِچپ، برچسبِ‌چپ،
  مقدارِراست، برچسبِ‌راست]. ReportLab برخلاف HTML خودش این برعکس‌شدن را
  انجام نمی‌دهد، پس اینجا صریحاً همین ترتیب فیزیکی ساخته می‌شود.
- ستون برچسب و مقدار هر دو Bold هستند (با تگ <b> داخل متن، نه با تنظیم
  fontName روی نسخه Bold فونت — چون آن روش با خطای شناخته‌شده ReportLab
  «Can't map determine family/bold/italic» در برخی سرورها کرش می‌کند).
- سلول‌های مقدارِ «نام» و «کد پرسنلی» پس‌زمینه روشن مشخصی دارند (highlight)،
  دقیقاً مثل کلاس value.highlight در CSS مرجع.

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

_NAVY = colors.HexColor("#2b3990")
_LABEL_BG = colors.HexColor("#fafbfd")
_GRID_COLOR = colors.HexColor("#c7cbe0")
_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "images" / "faipco-logo.png"

# ترتیب دقیقاً مطابق کارت مرجع (RIGHT_COLUMN / LEFT_COLUMN ابزار HTML)
_RIGHT_COLUMN = ["name", "totalWork", "nightDays", "absence", "unpaidLeave", "deduction", "dailyMission", "unit"]
_LEFT_COLUMN = ["code", "overtime", "fridayHours", "sickLeave", "socialSick", "bonusLeave", "leaveUsed", "remainLeave"]
_HIGHLIGHT_KEYS = {"name", "code"}  # مقدار این دو کلید پس‌زمینه روشن می‌گیرد (مثل value.highlight در CSS)


def render_attendance_card_pdf(
    *,
    employee_name: str,
    month_year: str,
    fields: list[dict],  # [{"label": ..., "value": ...}]
) -> bytes:
    def _build(include_logo: bool) -> bytes:
        has_font = _ensure_font_registered()
        font_name = _FONT_NAME if has_font else "Helvetica"

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=25 * mm,
            bottomMargin=25 * mm,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
        )

        # نکته: هرگز فونت "-Bold" مستقیماً به‌عنوان fontName یک Style تنظیم
        # نمی‌شود (دلیل بالای فایل) — به‌جایش از تگ <b> داخل متنِ خودِ
        # Paragraph استفاده می‌شود تا هم واقعاً Bold دربیاید، هم کرش نکند.
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
        # لوگو با Callback مستقیم روی Canvas کشیده می‌شود (نه به‌عنوان یک
        # Flowable داخل جریان متن) — دقیقاً معادل CSS مرجع (position:absolute
        # روی گوشه بالا-چپ کارت)، مستقل از قدشِ متن عنوان/زیرعنوان. این باعث
        # می‌شود ارتفاع لوگو هیچ فاصله اضافه‌ای بین متن سربرگ و جدول اصلی
        # ایجاد نکند (که با روش قبلی — لوگو داخل همان ردیف جدول — می‌شد).
        logo_size = 26 * mm

        def _draw_logo(canvas, _doc):
            if include_logo and _LOGO_PATH.exists():
                canvas.saveState()
                x = _doc.leftMargin
                y = _doc.pagesize[1] - _doc.topMargin - logo_size + 6 * mm
                canvas.drawImage(
                    str(_LOGO_PATH), x, y, width=logo_size, height=logo_size, mask="auto", preserveAspectRatio=True
                )
                canvas.restoreState()

        story.append(Paragraph(f"<b>{_shape('فیش کارکرد')}</b>", title_style))
        story.append(Paragraph(_shape(month_year), subtitle_style))
        story.append(Spacer(1, 4 * mm))

        # ---------- جدول اصلی ----------
        by_key = {}
        field_keys_in_order = [
            "name", "code", "totalWork", "nightDays", "overtime", "fridayHours", "leaveUsed",
            "sickLeave", "socialSick", "unpaidLeave", "bonusLeave", "absence", "deduction",
            "dailyMission", "unit", "remainLeave",
        ]
        for key, item in zip(field_keys_in_order, fields):
            by_key[key] = item

        # نسبت عرض دقیقاً مطابق CSS مرجع: value≈23%، label≈29% از عرض کارت (هر جفت ۵۲٪)
        pair_width = doc.width / 2
        value_width = pair_width * (23 / 52)
        label_width = pair_width * (29 / 52)
        col_widths = [value_width, label_width, value_width, label_width]

        table_data = []
        highlight_cells = []  # [(col, row), ...] برای پس‌زمینه روشن مقدار نام/کد
        max_rows = max(len(_RIGHT_COLUMN), len(_LEFT_COLUMN))
        for i in range(max_rows):
            right_key = _RIGHT_COLUMN[i] if i < len(_RIGHT_COLUMN) else None
            left_key = _LEFT_COLUMN[i] if i < len(_LEFT_COLUMN) else None

            def _cell_pair(key):
                if key and key in by_key:
                    item = by_key[key]
                    label_p = Paragraph(f"<b>{_shape(item['label'])}</b>", label_style)
                    value_text = _wrap_and_shape(str(item["value"]), font_name, 9.5, value_width - 6)
                    value_p = Paragraph(f"<b>{value_text}</b>", value_style)
                    return label_p, value_p
                return "", ""

            left_label, left_value = _cell_pair(left_key)
            right_label, right_value = _cell_pair(right_key)

            # چیدمان فیزیکی چپ‌به‌راست واقعی (نگاه کنید به توضیح بالای فایل):
            # [مقدارِچپ، برچسبِ‌چپ، مقدارِراست، برچسبِ‌راست]
            row_index = len(table_data)
            if left_key in _HIGHLIGHT_KEYS:
                highlight_cells.append((0, row_index))
            if right_key in _HIGHLIGHT_KEYS:
                highlight_cells.append((2, row_index))

            table_data.append([left_value, left_label, right_value, right_label])

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
        for col, row_idx in highlight_cells:
            style_commands.append(("BACKGROUND", (col, row_idx), (col, row_idx), _LABEL_BG))
        table.setStyle(TableStyle(style_commands))
        story.append(table)

        doc.build(story, onFirstPage=_draw_logo, onLaterPages=_draw_logo)
        return buffer.getvalue()

    try:
        return _build(include_logo=True)
    except Exception:
        # اگر ساخت PDF همراه لوگو به هر دلیلی شکست بخورد (مثلاً فایل لوگو روی
        # این سرور خاص Deploy/Push نشده یا خراب است)، دوباره و این‌بار بدون
        # لوگو می‌سازیم — یک عنصر کاملاً تزئینی هرگز نباید باعث شود کل قابلیت
        # دانلود کارت (که چیز حیاتی است) با خطای ۵۰۰ کاملاً از کار بیفتد.
        return _build(include_logo=False)
