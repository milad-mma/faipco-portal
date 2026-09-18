"""
تولید فایل Excel از گزارش درخواست‌های مرخصی/ماموریت - با openpyxl (از
قبل در requirements.txt این پروژه موجود است)، با همان قالب/استایل
گزارش‌های ارزیابی عملکرد (RTL، سرستون آبی).
"""
from __future__ import annotations

import io

import jdatetime
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

_HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_RTL_ALIGNMENT = Alignment(horizontal="right", readingOrder=2)

_STATUS_LABELS = {"pending": "در حال بررسی", "approved": "تائید شده", "rejected": "رد شده"}

_COLUMNS = [
    ("نام و نام خانوادگی", 26),
    ("کد پرسنلی", 14),
    ("واحد", 22),
    ("نوع درخواست", 24),
    ("توضیحات", 34),
    ("تاریخ ثبت", 14),
    ("تاریخ شروع", 14),
    ("تاریخ پایان", 14),
    ("ساعت شروع", 12),
    ("ساعت پایان", 12),
    ("مدت", 16),
    ("وضعیت", 14),
    ("نظر تأییدکننده", 34),
]


def _to_jalali(value) -> str:
    if not value:
        return ""
    try:
        d = value.date() if hasattr(value, "date") else value
        j = jdatetime.date.fromgregorian(date=d)
        return f"{j.year}/{j.month:02d}/{j.day:02d}"
    except Exception:
        return ""


def _format_compact_time(compact) -> str:
    if compact is None:
        return ""
    return f"{compact // 100:02d}:{compact % 100:02d}"


def _format_duration(item: dict) -> str:
    """⚠️ همان منطق نمایش در فرانت‌اند - ساعتی: ساعت و دقیقه؛ روزانه: تعداد روز."""
    start_hour, end_hour = item.get("start_hour"), item.get("end_hour")
    if start_hour is not None and end_hour is not None:
        diff = (end_hour // 100 * 60 + end_hour % 100) - (start_hour // 100 * 60 + start_hour % 100)
        if diff <= 0:
            return ""
        hours, minutes = divmod(diff, 60)
        if hours and minutes:
            return f"{hours} ساعت و {minutes} دقیقه"
        return f"{hours} ساعت" if hours else f"{minutes} دقیقه"
    start_date, end_date = item.get("start_date"), item.get("end_date")
    if start_date and end_date:
        days = (end_date - start_date).days + 1
        return f"{days} روز" if days > 0 else ""
    return ""


def build_leave_requests_xlsx(items: list[dict], site_name: str = "") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "درخواست‌ها"
    ws.sheet_view.rightToLeft = True

    if site_name:
        ws.append(["سایت", site_name])
        ws.append([])

    header_row_index = ws.max_row + 1
    ws.append([title for title, _ in _COLUMNS])
    for col in range(1, len(_COLUMNS) + 1):
        cell = ws.cell(row=header_row_index, column=col)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = _RTL_ALIGNMENT

    for item in items:
        ws.append(
            [
                item.get("requester_name") or "",
                item.get("emp_no") or "",
                item.get("requester_department") or "",
                item.get("type_title") or "",
                item.get("description") or "",
                _to_jalali(item.get("submitted_at")),
                _to_jalali(item.get("start_date")),
                _to_jalali(item.get("end_date")),
                _format_compact_time(item.get("start_hour")),
                _format_compact_time(item.get("end_hour")),
                _format_duration(item),
                _STATUS_LABELS.get(item.get("status"), item.get("status") or ""),
                item.get("manager_idea") or "",
            ]
        )

    for i, (_, width) in enumerate(_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
