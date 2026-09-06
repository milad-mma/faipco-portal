"""
الگوریتم خالص Resolve کردن اهداف ارزیابی عملکرد - بدون هیچ وابستگی به
SQLAlchemy/دیتابیس (دقیقاً مثل app/core/backup_schedule_logic.py) تا
بدون نیاز به یک دیتابیس واقعی قابل‌تست باشد.

سلسله‌مراتب (طبق تصمیم صریح کاربر):
    مدیر سایت (چند نفر مجاز)  →  سرپرست‌های واحدهای همان سایت + سایر مدیران همان سایت
    سرپرست واحد               →  اگر آن واحد سرشیفت دارد: فقط سرشیفت‌ها
                                   وگرنه: همه پرسنل آن واحد
    سرشیفت واحد                →  فقط زیرمجموعه‌ی اختصاصی خودش
                                   (پرسنل بین سرشیفت‌های یک واحد تقسیم می‌شوند)

منطق واقعی خواندن این داده‌های خام از دیتابیس در
app/services/evaluation_structure_service.py انجام می‌شود؛ این فایل فقط
خودِ الگوریتم محاسباتی را نگه می‌دارد.
"""
from __future__ import annotations


def resolve_evaluation_target_ids(
    evaluator_employee_id: int,
    site_manager_of_sites: list,
    department_supervisor_of_departments: list,
    shift_lead_of_shift_lead_ids: list,
    department_supervisors_by_site: dict,
    other_managers_by_site: dict,
    shift_lead_employees_by_department: dict,
    all_employees_by_department: dict,
    shift_assignments_by_shift_lead: dict,
) -> set:
    """
    خروجی: مجموعه‌ی شناسه‌های پرسنلی که evaluator_employee_id مجاز است
    ارزیابی کند - اجتماع (Union) اهداف همه نقش‌هایی که هم‌زمان دارد،
    همیشه بدون خودش.
    """
    target_ids: set = set()

    for site_id in site_manager_of_sites:
        target_ids.update(department_supervisors_by_site.get(site_id, []))
        target_ids.update(other_managers_by_site.get(site_id, []))

    for department_id in department_supervisor_of_departments:
        shift_lead_employee_ids = shift_lead_employees_by_department.get(department_id, [])
        if shift_lead_employee_ids:
            target_ids.update(shift_lead_employee_ids)
        else:
            target_ids.update(all_employees_by_department.get(department_id, []))

    for shift_lead_id in shift_lead_of_shift_lead_ids:
        target_ids.update(shift_assignments_by_shift_lead.get(shift_lead_id, []))

    target_ids.discard(evaluator_employee_id)  # هرگز خودش را ارزیابی نکند
    return target_ids
