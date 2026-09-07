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
    manager_ids_of_evaluator: list,
    manager_targets_by_manager_id: dict,
    department_supervisor_of_departments: list,
    shift_lead_of_shift_lead_ids: list,
    shift_lead_employees_by_department: dict,
    all_employees_by_department: dict,
    shift_assignments_by_shift_lead: dict,
) -> set:
    """
    خروجی: مجموعه‌ی شناسه‌های پرسنلی که evaluator_employee_id مجاز است
    ارزیابی کند - اجتماع (Union) اهداف همه نقش‌هایی که هم‌زمان دارد،
    همیشه بدون خودش.

    ⚠️ بازطراحی: نقش «مدیر» دیگر هیچ قانون خودکاری («مدیر سایت = همه
    سرپرست‌ها») ندارد - اهداف هر مدیر (manager_ids_of_evaluator) کاملاً
    از manager_targets_by_manager_id (تخصیص صریح و دستی) خوانده می‌شود؛
    این طراحی اجازه می‌دهد چارت سازمانی واقعی (مثلاً یک مدیر میانی مثل
    «مدیر تولید» که فقط بخشی از سرپرست‌ها را ارزیابی می‌کند، یا تخصیص
    مستقیم یک فرد خاص از یک واحد دیگر به هر مدیری) کاملاً پیاده شود.
    """
    target_ids: set = set()

    for manager_id in manager_ids_of_evaluator:
        target_ids.update(manager_targets_by_manager_id.get(manager_id, []))

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


_WEIGHT_TOLERANCE = 0.01  # گرد کردن اعشاری، نه اشکال واقعی در وزن‌ها


def validate_form_weights(categories: list) -> list:
    """
    الگوریتم خالص اعتبارسنجی وزن یک فرم - قبل از فعال‌شدن یک فرم اجرا
    می‌شود (نه در حالت Draft، که ممکن است هنوز ناقص باشد). categories:
    [{"title": str, "weight": float, "is_active": bool,
      "questions": [{"text": str, "weight": float, "is_active": bool}, ...]}, ...]

    قانون: مجموع weight دسته‌بندی‌های فعال باید ۱۰۰ باشد؛ داخل هر
    دسته‌بندی فعال، مجموع weight سوالات فعال هم باید ۱۰۰ باشد.

    خروجی: لیست پیام‌های خطا (فارسی، آماده نمایش مستقیم به کاربر) - اگر
    خالی باشد یعنی معتبر است.
    """
    errors: list = []

    active_categories = [c for c in categories if c.get("is_active", True)]
    if not active_categories:
        errors.append("فرم باید حداقل یک دسته‌بندی فعال داشته باشد")
        return errors

    category_weight_sum = sum(c.get("weight", 0) for c in active_categories)
    if abs(category_weight_sum - 100) > _WEIGHT_TOLERANCE:
        errors.append(f"مجموع وزن دسته‌بندی‌های فعال باید ۱۰۰ باشد (الان: {category_weight_sum:g})")

    for category in active_categories:
        active_questions = [q for q in category.get("questions", []) if q.get("is_active", True)]
        title = category.get("title", "")
        if not active_questions:
            errors.append(f"دسته‌بندی «{title}» باید حداقل یک سوال فعال داشته باشد")
            continue
        question_weight_sum = sum(q.get("weight", 0) for q in active_questions)
        if abs(question_weight_sum - 100) > _WEIGHT_TOLERANCE:
            errors.append(f"مجموع وزن سوالات فعال دسته‌بندی «{title}» باید ۱۰۰ باشد (الان: {question_weight_sum:g})")

    return errors


def calculate_option_based_question_score(selected_option_scores: list) -> float:
    """
    امتیاز یک سوال از نوع مبتنی‌بر گزینه (single_choice/multiple_choice/
    rating/yes_no) - میانگین امتیاز گزینه‌های انتخاب‌شده. برای
    single_choice/rating/yes_no که همیشه دقیقاً یک گزینه انتخاب می‌شود،
    این میانگین همان یک عدد است؛ برای multiple_choice که می‌تواند چند
    گزینه هم‌زمان انتخاب شود، میانگین معنادارترین ترکیب است.
    """
    if not selected_option_scores:
        return 0.0
    return sum(selected_option_scores) / len(selected_option_scores)


def calculate_weighted_average(weighted_items: list) -> float:
    """
    الگوریتم خالص مشترک برای هر دو سطح جمع‌بندی امتیاز:
        سوال‌ها  -> امتیاز دسته‌بندی
        دسته‌بندی‌ها -> امتیاز نهایی فرم
    weighted_items: [{"weight": float, "score": float}, ...] - چون
    validate_form_weights از قبل تضمین کرده مجموع weight های فعال ۱۰۰
    است، این‌جا فقط کافی است sum(weight/100 * score) محاسبه شود.
    """
    return sum(item["weight"] / 100 * item["score"] for item in weighted_items)
