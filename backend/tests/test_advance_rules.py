import pytest

from app.core import advance_rules as R


def test_tier_amount_picks_highest_reached_tier():
    tiers = [{"min_months": 24, "amount": 60}, {"min_months": 6, "amount": 30}, {"min_months": 0, "amount": 10}]
    assert R.tier_amount(3, tiers) == 10
    assert R.tier_amount(6, tiers) == 30
    assert R.tier_amount(23, tiers) == 30
    assert R.tier_amount(100, tiers) == 60
    assert R.tier_amount(None, tiers) is None
    # بدون پله‌ی صفر: سابقه‌ی کم واجد شرایط نیست
    assert R.tier_amount(2, tiers[:2]) is None
    assert R.tier_amount(5, []) is None


def test_validate_tiers_sorts_and_rejects_bad_rows():
    assert R.validate_tiers([{"min_months": "12", "amount": "500"}, {"min_months": 0, "amount": 100}]) == [
        {"group": "staff", "min_months": 0, "amount": 100},
        {"group": "staff", "min_months": 12, "amount": 500},
    ]
    with pytest.raises(R.AdvanceRuleError):
        R.validate_tiers([{"min_months": 1, "amount": 0}])
    with pytest.raises(R.AdvanceRuleError):
        R.validate_tiers([{"min_months": 1, "amount": 5}, {"min_months": 1, "amount": 6}])
    with pytest.raises(R.AdvanceRuleError):
        R.validate_tiers([{"min_months": -1, "amount": 5}])


def test_window_and_wraparound():
    assert R.validate_window("5", 15, 1) == (5, 15, 1)
    with pytest.raises(R.AdvanceRuleError):
        R.validate_window(0, 15, 1)
    with pytest.raises(R.AdvanceRuleError):
        R.validate_window(1, 31, 0)
    assert R.in_window(5, 5, 15) and R.in_window(15, 5, 15)
    assert not R.in_window(16, 5, 15)
    # بازه‌ی چرخان ۲۵ تا ۵
    assert R.in_window(28, 25, 5) and R.in_window(3, 25, 5)
    assert not R.in_window(10, 25, 5)
    assert R.window_label(1, 31) == "همه‌ی روزهای ماه"
    assert "۵" not in R.window_label(5, 15) and "5" in R.window_label(5, 15)


def test_request_month_wraparound():
    assert R.request_month((1405, 7, 14), 1, 31) == "1405/07"
    assert R.request_month((1405, 7, 2), 25, 5) == "1405/06"  # اول ماه در بازه‌ی چرخان → ماه قبل
    assert R.request_month((1405, 6, 28), 25, 5) == "1405/06"
    assert R.request_month((1405, 1, 3), 25, 5) == "1404/12"


def test_month_key_and_steps():
    assert R.month_key("1405/07/14") == "1405/07"
    assert R.month_key((1405, 1, 3)) == "1405/01"
    assert R.effective_steps(requester_id=1, unit_manager_id=2, site_manager_id=3) == [
        "unit_manager",
        "site_manager",
        "finance",
    ]
    # مدیر واحد = مدیر سایت → یک بار؛ درخواست‌دهنده خودش مدیر سایت → حذف
    assert R.effective_steps(requester_id=1, unit_manager_id=2, site_manager_id=2) == ["unit_manager", "finance"]
    assert R.effective_steps(requester_id=3, unit_manager_id=2, site_manager_id=3) == ["unit_manager", "finance"]
    assert R.effective_steps(requester_id=1, unit_manager_id=None, site_manager_id=None) == ["finance"]


def test_status_label():
    assert R.status_label("in_review", "unit_manager") == "در انتظار تأیید مدیر واحد"
    assert R.status_label("waiting_finance", None) == "در انتظار تأیید واحد مالی"
    assert R.status_label("paid", None) == "پرداخت شد"


def test_group_tiers_fallback_and_validation():
    tiers = [
        {"group": "staff", "min_months": 0, "amount": 10},
        {"group": "manager", "min_months": 0, "amount": 50},
    ]
    assert R.tier_amount(3, R.group_tiers(tiers, "manager")) == 50
    assert R.tier_amount(3, R.group_tiers(tiers, "supervisor")) == 10  # بدون پله‌ی سرپرست → پله‌های پرسنل
    assert R.tier_amount(3, R.group_tiers(tiers, "staff")) == 10
    cleaned = R.validate_tiers([{"group": "manager", "min_months": 6, "amount": 9}, {"min_months": 0, "amount": 1}])
    assert cleaned == [{"group": "staff", "min_months": 0, "amount": 1}, {"group": "manager", "min_months": 6, "amount": 9}]
    with pytest.raises(R.AdvanceRuleError):
        R.validate_tiers([{"group": "boss", "min_months": 0, "amount": 1}])
    # تکرار ماه فقط داخل یک گروه خطاست
    R.validate_tiers([{"group": "staff", "min_months": 0, "amount": 1}, {"group": "manager", "min_months": 0, "amount": 2}])
