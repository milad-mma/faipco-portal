"""
تست‌های واحد الگوریتم خالص Resolve کردن اهداف ارزیابی
(app/services/evaluation_structure_service.py::resolve_evaluation_target_ids)
- بدون I/O، بدون نیاز به دیتابیس واقعی.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.evaluation_rules import resolve_evaluation_target_ids


def test_site_manager_evaluates_department_supervisors_and_other_managers():
    """مدیر سایت: سرپرست‌های واحدهای همان سایت + سایر مدیران همان سایت (اجتماع)."""
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=100,
        site_manager_of_sites=[1],
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=[],
        department_supervisors_by_site={1: [200, 300]},
        other_managers_by_site={1: [400]},
        shift_lead_employees_by_department={},
        all_employees_by_department={},
        shift_assignments_by_shift_lead={},
    )
    assert targets == {200, 300, 400}


def test_manager_added_as_both_supervisor_and_other_manager_appears_once():
    """
    طبق تصمیم صریح کاربر: اگر فردی هم سرپرست یک واحد و هم به‌عنوان
    «سایر مدیران» اضافه شده باشد، در نتیجه نهایی فقط یک‌بار ظاهر شود.
    """
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=100,
        site_manager_of_sites=[1],
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=[],
        department_supervisors_by_site={1: [200]},
        other_managers_by_site={1: [200]},
        shift_lead_employees_by_department={},
        all_employees_by_department={},
        shift_assignments_by_shift_lead={},
    )
    assert targets == {200}


def test_department_supervisor_evaluates_all_employees_when_no_shift_leads():
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=200,
        site_manager_of_sites=[],
        department_supervisor_of_departments=[10],
        shift_lead_of_shift_lead_ids=[],
        department_supervisors_by_site={},
        other_managers_by_site={},
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
        site_manager_of_sites=[],
        department_supervisor_of_departments=["C"],
        shift_lead_of_shift_lead_ids=[],
        department_supervisors_by_site={},
        other_managers_by_site={},
        shift_lead_employees_by_department={"C": [600, 601]},
        all_employees_by_department={"C": [600, 601, 800, 801, 802]},
        shift_assignments_by_shift_lead={},
    )
    assert targets == {600, 601}
    assert 800 not in targets and 801 not in targets and 802 not in targets


def test_shift_lead_evaluates_only_own_assigned_subset():
    """
    طبق تصمیم صریح کاربر: پرسنل بین سرشیفت‌ها تقسیم می‌شوند - هر سرشیفت
    فقط زیرمجموعه اختصاصی خودش را می‌بیند، نه بقیه پرسنل واحد.
    """
    shift_assignments = {"shift_lead_600": [800, 801], "shift_lead_601": [802]}

    targets_600 = resolve_evaluation_target_ids(
        evaluator_employee_id=600,
        site_manager_of_sites=[],
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=["shift_lead_600"],
        department_supervisors_by_site={},
        other_managers_by_site={},
        shift_lead_employees_by_department={},
        all_employees_by_department={},
        shift_assignments_by_shift_lead=shift_assignments,
    )
    assert targets_600 == {800, 801}

    targets_601 = resolve_evaluation_target_ids(
        evaluator_employee_id=601,
        site_manager_of_sites=[],
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=["shift_lead_601"],
        department_supervisors_by_site={},
        other_managers_by_site={},
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
        site_manager_of_sites=[],
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=["shift_lead_600"],
        department_supervisors_by_site={},
        other_managers_by_site={},
        shift_lead_employees_by_department={},
        all_employees_by_department={},
        shift_assignments_by_shift_lead={"shift_lead_600": [800, 801]},
    )
    assert 601 not in targets


def test_person_with_multiple_roles_gets_union_of_all_targets():
    """یک نفر می‌تواند هم‌زمان چند نقش داشته باشد - نتیجه اجتماع همه اهداف است."""
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=999,
        site_manager_of_sites=[1],
        department_supervisor_of_departments=[10],
        shift_lead_of_shift_lead_ids=[],
        department_supervisors_by_site={1: [200]},
        other_managers_by_site={1: []},
        shift_lead_employees_by_department={10: []},
        all_employees_by_department={10: [500, 501]},
        shift_assignments_by_shift_lead={},
    )
    assert targets == {200, 500, 501}


def test_evaluator_never_included_in_own_targets():
    """حتی اگر به هر دلیلی (مثلاً باگ داده) خودش در یکی از فهرست‌ها باشد، هرگز جزو نتیجه نباشد."""
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=500,
        site_manager_of_sites=[],
        department_supervisor_of_departments=[10],
        shift_lead_of_shift_lead_ids=[],
        department_supervisors_by_site={},
        other_managers_by_site={},
        shift_lead_employees_by_department={10: []},
        all_employees_by_department={10: [500, 501]},
        shift_assignments_by_shift_lead={},
    )
    assert 500 not in targets
    assert targets == {501}


def test_no_roles_means_no_targets():
    targets = resolve_evaluation_target_ids(
        evaluator_employee_id=1,
        site_manager_of_sites=[],
        department_supervisor_of_departments=[],
        shift_lead_of_shift_lead_ids=[],
        department_supervisors_by_site={},
        other_managers_by_site={},
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
    errors = validate_form_weights([{"title": "غیرفعال", "weight": 100, "is_active": False, "questions": []}])
    assert len(errors) == 1


def test_active_category_with_no_active_questions_is_invalid():
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


def test_single_selected_option_score():
    assert calculate_option_based_question_score([80]) == 80


def test_multiple_selected_options_score_is_average():
    assert calculate_option_based_question_score([80, 60]) == 70


def test_no_selected_options_score_is_zero():
    assert calculate_option_based_question_score([]) == 0.0


def test_weighted_average_two_items():
    result = calculate_weighted_average([{"weight": 40, "score": 80}, {"weight": 60, "score": 90}])
    assert result == 86.0


def test_weighted_average_single_item_full_weight():
    result = calculate_weighted_average([{"weight": 100, "score": 75}])
    assert result == 75.0
