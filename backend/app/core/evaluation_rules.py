"""
الگوریتم‌های خالص ارزیابی عملکرد، بدون وابستگی به SQLAlchemy/دیتابیس تا بدون
دیتابیس واقعی قابل‌تست باشند:
- resolve_evaluation_target_ids: تعیین پرسنلی که هر ارزیاب مجاز به ارزیابی آن‌هاست
- validate_form_weights: اعتبارسنجی مجموع وزن دسته‌بندی‌ها و سوالات فرم
- calculate_option_based_question_score / calculate_weighted_average: محاسبه امتیاز

سلسله‌مراتب ارزیابی:
    مدیر                      →  فقط اهدافی که به‌صورت دستی به او تخصیص داده شده
    سرپرست واحد               →  اگر آن واحد سرشیفت دارد: سرشیفت‌ها + پرسنلِ بدون سرشیفت
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
    unassigned_employees_by_department: dict | None = None,
) -> set:
    """
    ورودی: شناسه ارزیاب و نگاشت‌های خام نقش‌ها (مدیر/سرپرست/سرشیفت) که از دیتابیس خوانده شده‌اند.
    خروجی: مجموعه شناسه‌های پرسنلی که ارزیاب مجاز است ارزیابی کند؛ اجتماع اهداف همه نقش‌هایش، بدون خودش.
    اهداف مدیر فقط از تخصیص دستی (manager_targets_by_manager_id) می‌آیند؛ پرسنل بدون سرشیفت زیر نظر سرپرست می‌مانند.
    """
    target_ids: set = set()

    # نقش مدیر: اهداف تخصیص‌داده‌شده‌ی دستی
    for manager_id in manager_ids_of_evaluator:
        target_ids.update(manager_targets_by_manager_id.get(manager_id, []))

    # نقش سرپرست واحد: سرشیفت‌ها (+ پرسنل بدون تخصیص) یا در نبود سرشیفت، همه پرسنل واحد
    for department_id in department_supervisor_of_departments:
        shift_lead_employee_ids = shift_lead_employees_by_department.get(department_id, [])
        if shift_lead_employee_ids:
            target_ids.update(shift_lead_employee_ids)
            if unassigned_employees_by_department:
                target_ids.update(unassigned_employees_by_department.get(department_id, []))
        else:
            target_ids.update(all_employees_by_department.get(department_id, []))

    # نقش سرشیفت: فقط پرسنل تخصیص‌داده‌شده به همان سرشیفت
    for shift_lead_id in shift_lead_of_shift_lead_ids:
        target_ids.update(shift_assignments_by_shift_lead.get(shift_lead_id, []))

    target_ids.discard(evaluator_employee_id)  # هرگز خودش را ارزیابی نکند
    return target_ids


_WEIGHT_TOLERANCE = 0.01  # گرد کردن اعشاری، نه اشکال واقعی در وزن‌ها


def validate_form_weights(categories: list) -> list:
    """
    اعتبارسنجی وزن یک فرم؛ قبل از فعال‌شدن فرم اجرا می‌شود (نه در حالت Draft). ورودی categories:
    [{"title": str, "weight": float, "is_active": bool,
      "questions": [{"text": str, "weight": float, "is_active": bool}, ...]}, ...]

    قانون: مجموع weight دسته‌بندی‌های فعال باید ۱۰۰ باشد؛ داخل هر
    دسته‌بندی فعال، مجموع weight سوالات فعال هم باید ۱۰۰ باشد.

    خروجی: لیست پیام‌های خطا (فارسی، آماده نمایش مستقیم به کاربر) - اگر
    خالی باشد یعنی معتبر است.
    """
    errors: list = []

    # فقط دسته‌بندی‌های فعال در محاسبه وزن شرکت می‌کنند
    active_categories = [c for c in categories if c.get("is_active", True)]
    if not active_categories:
        errors.append("فرم باید حداقل یک دسته‌بندی فعال داشته باشد")
        return errors

    category_weight_sum = sum(c.get("weight", 0) for c in active_categories)
    if abs(category_weight_sum - 100) > _WEIGHT_TOLERANCE:
        errors.append(f"مجموع وزن دسته‌بندی‌های فعال باید ۱۰۰ باشد (الان: {category_weight_sum:g})")

    # بررسی وزن سوالات فعال داخل هر دسته‌بندی فعال
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


def calculate_option_based_question_score(selected_option_scores: list, max_option_score: float) -> float:
    """
    امتیاز یک سوال مبتنی‌بر گزینه (single_choice/multiple_choice/rating/yes_no).
    ورودی: امتیاز گزینه‌های انتخاب‌شده و بزرگ‌ترین امتیاز میان همه گزینه‌های آن سوال.
    خروجی: میانگین امتیاز انتخاب‌ها نسبت به حداکثر، نرمالایزشده به ۰ تا ۱۰۰ (مستقل از مقیاس گزینه‌ها).
    """
    # بدون انتخاب یا با حداکثر نامعتبر، امتیاز صفر است
    if not selected_option_scores or max_option_score <= 0:
        return 0.0
    average_selected = sum(selected_option_scores) / len(selected_option_scores)
    return min(100.0, (average_selected / max_option_score) * 100)  # سقف ۱۰۰


def calculate_weighted_average(weighted_items: list) -> float:
    """
    میانگین وزنی مشترک برای هر دو سطح جمع‌بندی امتیاز:
        سوال‌ها  -> امتیاز دسته‌بندی
        دسته‌بندی‌ها -> امتیاز نهایی فرم
    weighted_items: [{"weight": float, "score": float}, ...] - چون
    validate_form_weights از قبل تضمین کرده مجموع weight های فعال ۱۰۰
    است، این‌جا فقط کافی است sum(weight/100 * score) محاسبه شود.
    """
    return sum(item["weight"] / 100 * item["score"] for item in weighted_items)
