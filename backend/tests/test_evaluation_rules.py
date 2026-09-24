"""
تست‌های واحد الگوریتم‌های خالص ارزیابی عملکرد در app/core/evaluation_rules.py
(بدون I/O و بدون دیتابیس واقعی):
- resolve_evaluation_target_ids: اهداف مدیر، سرپرست و سرشیفت
- validate_form_weights: اعتبارسنجی وزن دسته‌بندی‌ها و سوالات
- calculate_option_based_question_score / calculate_weighted_average: محاسبه امتیاز
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # افزودن backend/ به مسیر import

from app.core.evaluation_rules import resolve_evaluation_target_ids


def test_manager_evaluates_explicitly_assigned_targets():
    """مدیر: هر لیستی از اهداف که صریحاً به او تخصیص داده شده (نه یک قانون خودکار)."""
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=100,
        manager_ids_of_evaluator=[1],
        manager_targets_by_manager_id={1: [200, 300, 400]},
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=[],
        shift_lead_employees_by_department={},
        all_employees_by_department={},
        shift_assignments_by_shift_lead={},
    )
    assert targets == {200, 300, 400}


def test_intermediate_manager_can_have_partial_targets_not_all_supervisors():
    """
    چارت چندسطحی: مدیر میانی (مثل «مدیر تولید») فقط بخشی از سرپرست‌ها را ارزیابی می‌کند
    و مدیر سایت فقط اهداف تخصیص‌داده‌شده به خودش را.
    """
    site_manager_targets = resolve_evaluation_target_ids(
        evaluator_employee_id=1,  # مدیر سایت
        manager_ids_of_evaluator=[10],
        manager_targets_by_manager_id={10: [2], 20: [200, 300]},  # فقط یک سرپرست مستقیم زیر مدیر سایت
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=[],
        shift_lead_employees_by_department={},
        all_employees_by_department={},
        shift_assignments_by_shift_lead={},
    )
    assert site_manager_targets == {2}

    production_manager_targets = resolve_evaluation_target_ids(
        evaluator_employee_id=2,  # مدیر تولید - یک مدیر میانی مستقل
        manager_ids_of_evaluator=[20],
        manager_targets_by_manager_id={10: [2], 20: [200, 300]},  # بقیه سرپرست‌ها زیر او
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=[],
        shift_lead_employees_by_department={},
        all_employees_by_department={},
        shift_assignments_by_shift_lead={},
    )
    assert production_manager_targets == {200, 300}


def test_manager_can_target_arbitrary_employee_from_any_department():
    """مدیر می‌تواند هر فرد خاصی را - حتی از واحد/سایت دیگر - مستقیم هدف بگیرد."""
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=100,
        manager_ids_of_evaluator=[1],
        manager_targets_by_manager_id={1: [999]},  # ۹۹۹ ممکن است هیچ ربطی به سرپرستی نداشته باشد
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=[],
        shift_lead_employees_by_department={},
        all_employees_by_department={},
        shift_assignments_by_shift_lead={},
    )
    assert targets == {999}


def test_department_supervisor_evaluates_all_employees_when_no_shift_leads():
    """سرپرست واحد بدون سرشیفت، همه پرسنل واحد را ارزیابی می‌کند."""
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=200,
        manager_ids_of_evaluator=[],
        manager_targets_by_manager_id={},
        department_supervisor_of_departments=[10],
        shift_lead_of_shift_lead_ids=[],
        shift_lead_employees_by_department={10: []},
        all_employees_by_department={10: [500, 501, 502]},
        shift_assignments_by_shift_lead={},
    )
    assert targets == {500, 501, 502}


def test_department_supervisor_evaluates_only_shift_leads_when_present():
    """
    مهم‌ترین قانون سرشیفت: وقتی واحد سرشیفت دارد، سرپرست دیگر پرسنل عادی
    را مستقیم ارزیابی نمی‌کند - فقط سرشیفت‌ها را.
    """
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=700,
        manager_ids_of_evaluator=[],
        manager_targets_by_manager_id={},
        department_supervisor_of_departments=["C"],
        shift_lead_of_shift_lead_ids=[],
        shift_lead_employees_by_department={"C": [600, 601]},
        all_employees_by_department={"C": [600, 601, 800, 801, 802]},
        shift_assignments_by_shift_lead={},
    )
    assert targets == {600, 601}
    assert 800 not in targets and 801 not in targets and 802 not in targets


def test_department_supervisor_also_evaluates_employees_unassigned_to_any_shift_lead():
    """
    اگر واحد سرشیفت دارد ولی بعضی پرسنل هنوز به
    هیچ سرشیفتی تخصیص داده نشده‌اند، آن پرسنل نباید بی‌ارزیاب بمانند -
    مستقیماً زیر نظر سرپرست باقی می‌مانند (علاوه بر خودِ سرشیفت‌ها).
    """
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=700,
        manager_ids_of_evaluator=[],
        manager_targets_by_manager_id={},
        department_supervisor_of_departments=["C"],
        shift_lead_of_shift_lead_ids=[],
        shift_lead_employees_by_department={"C": [600, 601]},
        all_employees_by_department={"C": [600, 601, 800, 801, 802]},
        shift_assignments_by_shift_lead={},
        unassigned_employees_by_department={"C": [802]},  # فقط ۸۰۲ به سرشیفتی تخصیص داده نشده
    )
    assert targets == {600, 601, 802}  # سرشیفت‌ها + پرسنل بدون‌تخصیص
    assert 800 not in targets and 801 not in targets  # این‌ها به سرشیفت تخصیص داده شده‌اند - فقط سرشیفتشان آن‌ها را می‌بیند


def test_shift_lead_evaluates_only_own_assigned_subset():
    """
    پرسنل بین سرشیفت‌ها تقسیم می‌شوند - هر سرشیفت
    فقط زیرمجموعه اختصاصی خودش را می‌بیند، نه بقیه پرسنل واحد.
    """
    shift_assignments = {"shift_lead_600": [800, 801], "shift_lead_601": [802]}

    targets_600 = resolve_evaluation_target_ids(
        evaluator_employee_id=600,
        manager_ids_of_evaluator=[],
        manager_targets_by_manager_id={},
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=["shift_lead_600"],
        shift_lead_employees_by_department={},
        all_employees_by_department={},
        shift_assignments_by_shift_lead=shift_assignments,
    )
    assert targets_600 == {800, 801}

    targets_601 = resolve_evaluation_target_ids(
        evaluator_employee_id=601,
        manager_ids_of_evaluator=[],
        manager_targets_by_manager_id={},
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=["shift_lead_601"],
        shift_lead_employees_by_department={},
        all_employees_by_department={},
        shift_assignments_by_shift_lead=shift_assignments,
    )
    assert targets_601 == {802}


def test_shift_leads_never_evaluate_each_other():
    """
    نتیجه غیرمستقیم طراحی داده: چون shift_assignments_by_shift_lead فقط
    پرسنل عادی را نگه می‌دارد (نه سرشیفت‌های دیگر)، سرشیفت‌ها هرگز در
    نتیجه یکدیگر ظاهر نمی‌شوند.
    """
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=600,
        manager_ids_of_evaluator=[],
        manager_targets_by_manager_id={},
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=["shift_lead_600"],
        shift_lead_employees_by_department={},
        all_employees_by_department={},
        shift_assignments_by_shift_lead={"shift_lead_600": [800, 801]},
    )
    assert 601 not in targets


def test_person_with_multiple_roles_gets_union_of_all_targets():
    """یک نفر می‌تواند هم‌زمان چند نقش داشته باشد - نتیجه اجتماع همه اهداف است."""
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=999,
        manager_ids_of_evaluator=[1],
        manager_targets_by_manager_id={1: [200]},
        department_supervisor_of_departments=[10],
        shift_lead_of_shift_lead_ids=[],
        shift_lead_employees_by_department={10: []},
        all_employees_by_department={10: [500, 501]},
        shift_assignments_by_shift_lead={},
    )
    assert targets == {200, 500, 501}


def test_evaluator_never_included_in_own_targets():
    """حتی اگر به هر دلیلی (مثلاً باگ داده) خودش در یکی از فهرست‌ها باشد، هرگز جزو نتیجه نباشد."""
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=500,
        manager_ids_of_evaluator=[],
        manager_targets_by_manager_id={},
        department_supervisor_of_departments=[10],
        shift_lead_of_shift_lead_ids=[],
        shift_lead_employees_by_department={10: []},
        all_employees_by_department={10: [500, 501]},
        shift_assignments_by_shift_lead={},
    )
    assert 500 not in targets
    assert targets == {501}


def test_no_roles_means_no_targets():
    """ارزیاب بدون هیچ نقشی، هدفی ندارد."""
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=1,
        manager_ids_of_evaluator=[],
        manager_targets_by_manager_id={},
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=[],
        shift_lead_employees_by_department={},
        all_employees_by_department={},
        shift_assignments_by_shift_lead={},
    )
    assert targets == set()


# ==============================================================================
# اعتبارسنجی وزن فرم (validate_form_weights)
# ==============================================================================

from app.core.evaluation_rules import validate_form_weights  # noqa: E402


def test_valid_weights_return_no_errors():
    """فرم با مجموع وزن ۱۰۰ در هر دو سطح، بدون خطاست."""
    errors = validate_form_weights(
        [
            {
                "title": "انضباط",
                "weight": 40,
                "is_active": True,
                "questions": [
                    {"text": "q1", "weight": 60, "is_active": True},
                    {"text": "q2", "weight": 40, "is_active": True},
                ],
            },
            {
                "title": "کیفیت",
                "weight": 60,
                "is_active": True,
                "questions": [{"text": "q3", "weight": 100, "is_active": True}],
            },
        ]
    )
    assert errors == []


def test_category_weights_not_summing_to_100_is_invalid():
    """مجموع وزن دسته‌بندی‌ها ۹۰ است: یک خطا."""
    errors = validate_form_weights(
        [
            {
                "title": "انضباط",
                "weight": 40,
                "is_active": True,
                "questions": [{"text": "q1", "weight": 100, "is_active": True}],
            },
            {
                "title": "کیفیت",
                "weight": 50,
                "is_active": True,
                "questions": [{"text": "q2", "weight": 100, "is_active": True}],
            },
        ]
    )
    assert len(errors) == 1


def test_question_weights_not_summing_to_100_is_invalid():
    """مجموع وزن سوالات یک دسته ۶۰ است: یک خطا با نام همان دسته."""
    errors = validate_form_weights(
        [
            {
                "title": "انضباط",
                "weight": 100,
                "is_active": True,
                "questions": [
                    {"text": "q1", "weight": 30, "is_active": True},
                    {"text": "q2", "weight": 30, "is_active": True},
                ],
            }
        ]
    )
    assert len(errors) == 1
    assert "انضباط" in errors[0]


def test_inactive_categories_and_questions_are_ignored():
    """دسته‌بندی‌ها و سوالات غیرفعال در محاسبه وزن نادیده گرفته می‌شوند."""
    errors = validate_form_weights(
        [
            {
                "title": "فعال",
                "weight": 100,
                "is_active": True,
                "questions": [
                    {"text": "q1", "weight": 100, "is_active": True},
                    {"text": "q2", "weight": 999, "is_active": False},
                ],
            },
            {"title": "غیرفعال", "weight": 999, "is_active": False, "questions": []},
        ]
    )
    assert errors == []


def test_no_active_categories_is_invalid():
    """فرم بدون دسته‌بندی فعال نامعتبر است."""
    errors = validate_form_weights([{"title": "غیرفعال", "weight": 100, "is_active": False, "questions": []}])
    assert len(errors) == 1


def test_active_category_with_no_active_questions_is_invalid():
    """دسته‌بندی فعال بدون سوال فعال نامعتبر است."""
    errors = validate_form_weights(
        [{"title": "خالی", "weight": 100, "is_active": True, "questions": []}]
    )
    assert len(errors) == 1
    assert "خالی" in errors[0]


# ==============================================================================
# محاسبه امتیاز (calculate_option_based_question_score / calculate_weighted_average)
# ==============================================================================

from app.core.evaluation_rules import (  # noqa: E402
    calculate_option_based_question_score,
    calculate_weighted_average,
)


def test_single_selected_option_score_normalized_to_100_scale():
    """اگر گزینه‌ها از قبل روی مقیاس ۰-۱۰۰ باشند (max=100)، نتیجه بدون تغییر همان امتیاز خام است."""
    assert calculate_option_based_question_score([80], max_option_score=100) == 80


def test_multiple_selected_options_score_is_average_then_normalized():
    """چند گزینه انتخاب‌شده: میانگین امتیازها سپس نرمالایز."""
    assert calculate_option_based_question_score([80, 60], max_option_score=100) == 70


def test_no_selected_options_score_is_zero():
    """بدون گزینه انتخاب‌شده امتیاز صفر است."""
    assert calculate_option_based_question_score([], max_option_score=100) == 0.0


def test_option_score_normalized_when_scale_is_not_0_to_100():
    """
    گزینه‌ها روی مقیاس دیگری (مثلاً ۰ تا ۵) هم درست نرمالایز می‌شوند:
    انتخاب بهترین گزینه (امتیاز خام = حداکثر) همیشه دقیقاً ۱۰۰ می‌دهد.
    """
    assert calculate_option_based_question_score([5], max_option_score=5) == 100.0
    assert calculate_option_based_question_score([4], max_option_score=5) == 80.0
    assert calculate_option_based_question_score([0], max_option_score=5) == 0.0


def test_option_score_normalization_is_a_no_op_for_correctly_scaled_forms():
    """برای فرم‌هایی با حداکثر امتیاز گزینه = ۱۰۰، نرمالایز همان امتیاز خام را برمی‌گرداند."""
    assert calculate_option_based_question_score([75], max_option_score=100) == 75.0


def test_weighted_average_two_items():
    """میانگین وزنی دو آیتم با وزن‌های ۴۰ و ۶۰."""
    result = calculate_weighted_average([{"weight": 40, "score": 80}, {"weight": 60, "score": 90}])
    assert result == 86.0


def test_weighted_average_single_item_full_weight():
    """یک آیتم با وزن ۱۰۰ همان امتیاز خودش را می‌دهد."""
    result = calculate_weighted_average([{"weight": 100, "score": 75}])
    assert result == 75.0
