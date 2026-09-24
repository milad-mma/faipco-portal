"""
تولید فایل Excel (با openpyxl) از گزارش‌های مدیریتی ارزیابی عملکرد:
گزارش یک دوره برای یک سایت (خلاصه واحدها، جزئیات پرسنل، سوال و پاسخ) و مقایسه دو دوره
(میانگین واحدها و روند پرسنل). همه شیت‌ها راست‌به‌چپ‌اند و خروجی بایت‌های فایل xlsx است.
"""
from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# سبک سطر سرتیتر: پس‌زمینه سرمه‌ای، متن سفید پررنگ، چینش راست‌به‌چپ
_HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
_HEADER_FONT = Font(color="FFFFFF", bold=True)
_RTL_ALIGNMENT = Alignment(horizontal="right", readingOrder=2)  # readingOrder=2 یعنی RTL


def _style_header_row(ws, row: int, column_count: int) -> None:
    """ورودی: شیت، شماره سطر و تعداد ستون. سبک سرتیتر را به سلول‌های آن سطر می‌دهد و شیت را RTL می‌کند."""
    for col in range(1, column_count + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = _RTL_ALIGNMENT
    ws.sheet_view.rightToLeft = True


def _autofit_columns(ws, widths: list[int]) -> None:
    """عرض ستون‌های شیت را به ترتیب از فهرست widths تنظیم می‌کند."""
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width


def build_site_period_report_xlsx(report: dict, answers: list[dict] | None = None) -> bytes:
    """
    ورودی: گزارش دوره (خروجی get_site_period_report) و در صورت وجود ریز پاسخ‌ها (get_period_answers).
    شیت‌های «خلاصه»، «جزئیات پرسنل» و (اگر answers باشد) «سوال و پاسخ» را می‌سازد.
    خروجی: بایت‌های فایل xlsx.
    """
    wb = Workbook()

    # --- شیت خلاصه: اطلاعات کلی سایت/دوره و جدول آمار واحدها ---
    summary_ws = wb.active
    summary_ws.title = "خلاصه"
    summary_ws.sheet_view.rightToLeft = True
    summary_ws.append(["سایت", report["site_name"]])
    summary_ws.append(["دوره ارزیابی", report["period_title"]])
    summary_ws.append(
        [
            "میانگین کل سایت",
            round(report["overall_average_score"], 1) if report["overall_average_score"] is not None else "—",
        ]
    )
    summary_ws.append(["تعداد ارزیابی ثبت‌شده", report["overall_count"]])
    summary_ws.append([])
    header_row = summary_ws.max_row + 1  # شماره سطری که سرتیتر جدول واحدها در آن درج می‌شود
    summary_ws.append(["واحد", "میانگین", "تعداد", "کمترین", "بیشترین"])
    _style_header_row(summary_ws, header_row, 5)
    for dept in report["departments"]:
        summary_ws.append(
            [
                dept["department_name"],
                round(dept["average_score"], 1) if dept["average_score"] is not None else "—",
                dept["count"],
                round(dept["min_score"], 1) if dept["min_score"] is not None else "—",
                round(dept["max_score"], 1) if dept["max_score"] is not None else "—",
            ]
        )
    _autofit_columns(summary_ws, [24, 12, 10, 10, 10])

    # --- شیت جزئیات پرسنل: یک سطر برای هر پرسنل با امتیازش ---
    detail_ws = wb.create_sheet("جزئیات پرسنل")
    detail_ws.sheet_view.rightToLeft = True
    detail_ws.append(["واحد", "نام", "نام خانوادگی", "کد پرسنلی", "امتیاز"])
    _style_header_row(detail_ws, 1, 5)
    for dept in report["departments"]:
        for emp in dept["employees"]:
            detail_ws.append(
                [
                    dept["department_name"],
                    emp["first_name"],
                    emp["last_name"],
                    emp["personnel_code"],
                    round(emp["score"], 1) if emp["score"] is not None else "—",
                ]
            )
    _autofit_columns(detail_ws, [20, 16, 16, 14, 10])

    # --- شیت سوال و پاسخ: ریز پاسخ هر سوال، جدا از شیت خلاصه‌ی جزئیات پرسنل ---
    if answers:
        answers_ws = wb.create_sheet("سوال و پاسخ")
        answers_ws.sheet_view.rightToLeft = True
        answers_ws.append(
            [
                "واحد",
                "نام",
                "نام خانوادگی",
                "کد پرسنلی",
                "امتیاز کل",
                "سوال",
                "پاسخ",
                "گزینه‌های ممکن",
                "امتیاز سوال",
                "نظر ارزیاب",
            ]
        )
        _style_header_row(answers_ws, 1, 10)
        for a in answers:
            answers_ws.append(
                [
                    a["department"] or "—",
                    a["first_name"],
                    a["last_name"],
                    a["personnel_code"],
                    round(a["total_score"], 1) if a["total_score"] is not None else "—",
                    a["question"],
                    a["answer"],
                    a["options"] or "—",
                    round(a["score"], 1) if a["score"] is not None else "—",
                    a["comment"] or "—",
                ]
            )
        _autofit_columns(answers_ws, [18, 14, 14, 12, 10, 45, 28, 38, 10, 30])

    # ذخیره در حافظه و برگرداندن بایت‌ها
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def build_period_comparison_xlsx(comparison: dict) -> bytes:
    """
    ورودی: خروجی get_period_comparison. شیت «مقایسه دوره‌ها» (میانگین واحدها و تغییر) و در صورت
    وجود پرسنل، شیت «روند پرسنل» (دو امتیاز و تغییر هر نفر) را می‌سازد. خروجی: بایت‌های فایل xlsx.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "مقایسه دوره‌ها"
    ws.sheet_view.rightToLeft = True

    # --- اطلاعات کلی و میانگین کل سایت در هر دو دوره ---
    ws.append(["سایت", comparison["site_name"]])
    ws.append(["دوره اول", comparison["period_a"]["title"]])
    ws.append(["دوره دوم", comparison["period_b"]["title"]])
    avg_a_overall = comparison["period_a"]["average_score"]
    avg_b_overall = comparison["period_b"]["average_score"]
    ws.append(
        [
            "میانگین کل سایت",
            round(avg_a_overall, 1) if avg_a_overall is not None else "—",
            round(avg_b_overall, 1) if avg_b_overall is not None else "—",
        ]
    )
    ws.append([])
    # --- جدول واحدها: میانگین هر دوره و تغییر (دوره دوم منهای دوره اول) ---
    header_row = ws.max_row + 1
    ws.append(
        ["واحد", f"میانگین ({comparison['period_a']['title']})", f"میانگین ({comparison['period_b']['title']})", "تغییر"]
    )
    _style_header_row(ws, header_row, 4)
    for dept in comparison["departments"]:
        avg_a = dept["period_a_average"]
        avg_b = dept["period_b_average"]
        change = round(avg_b - avg_a, 1) if (avg_a is not None and avg_b is not None) else "—"  # فقط اگر هر دو مقدار باشند
        ws.append(
            [
                dept["department_name"],
                round(avg_a, 1) if avg_a is not None else "—",
                round(avg_b, 1) if avg_b is not None else "—",
                change,
            ]
        )
    _autofit_columns(ws, [24, 22, 22, 12])

    # --- شیت روند پرسنل: همان داده‌ای که UI زیر هر واحد نشان می‌دهد (دو امتیاز و تغییر هر نفر) ---
    has_employees = any(d.get("employees") for d in comparison["departments"])
    if has_employees:
        trend_ws = wb.create_sheet("روند پرسنل")
        trend_ws.sheet_view.rightToLeft = True
        trend_ws.append(
            [
                "واحد",
                "نام",
                "نام خانوادگی",
                "کد پرسنلی",
                comparison["period_a"]["title"],
                comparison["period_b"]["title"],
                "تغییر",
            ]
        )
        _style_header_row(trend_ws, 1, 7)
        for dept in comparison["departments"]:
            for emp in dept.get("employees", []):
                score_a = emp.get("period_a_score")
                score_b = emp.get("period_b_score")
                change = (
                    round(score_b - score_a, 1)
                    if (score_a is not None and score_b is not None)
                    else "—"
                )
                trend_ws.append(
                    [
                        dept["department_name"],
                        emp["first_name"],
                        emp["last_name"],
                        emp["personnel_code"],
                        round(score_a, 1) if score_a is not None else "—",
                        round(score_b, 1) if score_b is not None else "—",
                        change,
                    ]
                )
        _autofit_columns(trend_ws, [20, 15, 15, 13, 20, 20, 10])

    # ذخیره در حافظه و برگرداندن بایت‌ها
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
