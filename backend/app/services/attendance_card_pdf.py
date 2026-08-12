"""
تولید PDF «فیش کارکرد» — طراحی مطابق نمونه HTML مرجع: کادر سرمه‌ای دور کارت،
لوگو گوشه بالا، عنوان «فیش کارکرد» + زیرعنوان ماه/سال، و جدول دو‌ستونی
برچسب/مقدار (۸ ردیف سمت راست، ۸ ردیف سمت چپ).

برخلاف ابزار HTML مرجع (که ۸ کارت را کنار هم روی یک برگه A4 برای چاپ دستی
می‌چیند)، اینجا هر پرسنل فایل PDF مستقل خودش را می‌گیرد (یک کارت در وسط
صفحه) — چون توزیع از طریق پرتال و به‌صورت انفرادی است، نه چاپ گروهی.

از همان زیرساخت فونت/Shape فارسی payroll_pdf.py استفاده می‌شود تا رفتار
یکسان و بدون تکرار کد باشد.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.payroll_pdf import (
    _FONT_NAME,
    _ensure_font_registered,
    _shape,
    _wrap_and_shape,
)

_NAVY = colors.HexColor("#2b3990")
_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "images" / "faipco-logo.png"


def render_attendance_card_pdf(
    *,
    employee_name: str,
    month_year: str,
    fields: list[dict],  # [{"label": ..., "value": ...}]
) -> bytes:
    def _build(include_logo: bool) -> bytes:
        has_font = _ensure_font_registered()
        font_name = _FONT_NAME if has_font else "Helvetica"
        # نکته مهم: عمداً از _FONT_NAME_BOLD مستقیماً به‌عنوان fontName یک
        # ParagraphStyle استفاده نمی‌شود. ReportLab برای Paragraph (نه
        # drawString ساده)، fontName هر Style را با ps2tt() به یک "خانواده"
        # فونت Map می‌کند؛ این تابع فقط خانواده‌ای که با registerFontFamily
        # ثبت شده (اینجا فقط _FONT_NAME) را می‌شناسد، نه نام مستقیم فونت
        # Bold را. استفاده مستقیم از _FONT_NAME_BOLD اینجا — بسته به این‌که
        # کدام فونت Bold روی هر سرور واقعاً پیدا/ثبت شود — می‌تواند با خطای
        # «Can't map determine family/bold/italic» کل تولید PDF را خراب کند.
        # پس این‌جا برای «حس Bold»، فقط از رنگ سرمه‌ای + سایز بزرگ‌تر استفاده
        # می‌شود، نه وزن واقعی Bold — تضمین می‌کند این کارت مستقل از این‌که
        # کدام فونت روی کدام سرور Register شده، همیشه قابل‌ساخت بماند.
        font_bold = font_name

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=30 * mm,
            bottomMargin=30 * mm,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
        )

        title_style = ParagraphStyle(
            "cardTitle", fontName=font_bold, fontSize=16, alignment=TA_CENTER, textColor=_NAVY, leading=20
        )
        subtitle_style = ParagraphStyle(
            "cardSubtitle", fontName=font_name, fontSize=11, alignment=TA_CENTER, textColor=colors.HexColor("#333333")
        )
        label_style = ParagraphStyle(
            "cellLabel", fontName=font_bold, fontSize=9.5, alignment=TA_RIGHT, textColor=_NAVY, leading=13
        )
        value_style = ParagraphStyle(
            "cellValue", fontName=font_name, fontSize=10, alignment=TA_CENTER, leading=13
        )

        story = []

        if include_logo and _LOGO_PATH.exists():
            logo = Image(str(_LOGO_PATH), width=22 * mm, height=22 * mm)
            logo.hAlign = "CENTER"
            story.append(logo)
            story.append(Spacer(1, 4 * mm))

        story.append(Paragraph(_shape("فیش کارکرد"), title_style))
        story.append(Paragraph(_shape(month_year), subtitle_style))
        story.append(Spacer(1, 6 * mm))

        # ترتیب دقیقاً مطابق کارت مرجع: راست‌چین از بالا به پایین، سپس چپ‌چین
        right_column = ["name", "totalWork", "nightDays", "absence", "unpaidLeave", "deduction", "dailyMission", "unit"]
        left_column = ["code", "overtime", "fridayHours", "sickLeave", "socialSick", "bonusLeave", "leaveUsed", "remainLeave"]
        by_key = {}
        # fields در ترتیب مرجع (name, code, totalWork, ...) با label فارسی می‌آید؛
        # چون کلید انگلیسی در PDF لازم نیست، مستقیم بر اساس همان ترتیب ورودی نگاشت می‌کنیم
        field_keys_in_order = [
            "name", "code", "totalWork", "nightDays", "overtime", "fridayHours", "leaveUsed",
            "sickLeave", "socialSick", "unpaidLeave", "bonusLeave", "absence", "deduction",
            "dailyMission", "unit", "remainLeave",
        ]
        for key, item in zip(field_keys_in_order, fields):
            by_key[key] = item

        col_width = (doc.width) / 4
        table_data = []
        max_rows = max(len(right_column), len(left_column))
        for i in range(max_rows):
            row = []
            # نکته مهم: ReportLab ستون‌های جدول را همیشه از چپ به راست در
            # آرایه قرار می‌دهد (برخلاف HTML با dir=rtl که خودکار برعکس
            # می‌کند) — پس برای اینکه «right_column» واقعاً سمت راستِ فیزیکی
            # صفحه دربیاید، باید اول left_column را در آرایه بگذاریم.
            for key_list in (left_column, right_column):
                key = key_list[i] if i < len(key_list) else None
                if key and key in by_key:
                    item = by_key[key]
                    label_text = _shape(item["label"])
                    value_text = _wrap_and_shape(str(item["value"]), font_name, 10, col_width - 6)
                    row.append(Paragraph(label_text, label_style))
                    row.append(Paragraph(value_text, value_style))
                else:
                    row.append("")
                    row.append("")
            table_data.append(row)

        table = Table(table_data, colWidths=[col_width] * 4, repeatRows=0)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c7cbe0")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#fafbfd")),
                    ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#fafbfd")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("BOX", (0, 0), (-1, -1), 1.5, _NAVY),
                ]
            )
        )
        story.append(table)

        doc.build(story)
        return buffer.getvalue()

    try:
        return _build(include_logo=True)
    except Exception:
        # اگر ساخت PDF همراه لوگو به هر دلیلی شکست بخورد (مثلاً فایل لوگو روی
        # این سرور خاص Deploy/Push نشده یا خراب است)، دوباره و این‌بار بدون
        # لوگو می‌سازیم — یک عنصر کاملاً تزئینی هرگز نباید باعث شود کل قابلیت
        # دانلود کارت (که چیز حیاتی است) با خطای ۵۰۰ کاملاً از کار بیفتد.
        return _build(include_logo=False)
