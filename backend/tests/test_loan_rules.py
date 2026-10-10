"""تست قواعد خالص ماژول وام (app/core/loan_rules.py) با مثال‌های دستورالعمل کارخانه (۱۴۰۵/۰۷/۱۵)."""
import pytest

from app.core import loan_rules as R


def test_months_between_counts_full_months_only():
    assert R.months_between("1404/01/10", "1405/03/09") == 13
    assert R.months_between("1404/01/10", "1405/03/10") == 14
    assert R.months_between("1405/08/01", "1405/07/01") == 0  # تاریخ آینده
    assert R.months_between(None, "1405/07/01") is None
    assert R.months_between("نامعتبر", "1405/07/01") is None


def test_format_service():
    assert R.format_service(26) == "2 سال و 2 ماه"
    assert R.format_service(24) == "2 سال"
    assert R.format_service(3) == "3 ماه"
    assert R.format_service(None) == "نامشخص"


def test_factory_types_by_service():
    # الف: ۲ سال، ب: ۱ سال، ج: ۳ ماه — کسی با ۱۴ ماه سابقه فقط ب و ج را می‌تواند بگیرد
    alef = {"is_active": True, "min_service_months": 24}
    be = {"is_active": True, "min_service_months": 12}
    jim = {"is_active": True, "min_service_months": 3}
    assert "2 سال" in R.type_ineligibility(alef, 14)
    assert R.type_ineligibility(be, 14) is None
    assert R.type_ineligibility(jim, 14) is None
    assert "تاریخ استخدام" in R.type_ineligibility(jim, None)
    assert R.type_ineligibility({"is_active": False, "min_service_months": 0}, 100) is not None


def test_validate_amount():
    assert R.validate_amount(150_000_000, 200_000_000) == 150_000_000
    with pytest.raises(R.LoanRuleError):
        R.validate_amount(250_000_000, 200_000_000)
    with pytest.raises(R.LoanRuleError):
        R.validate_amount(0, 200_000_000)
    with pytest.raises(R.LoanRuleError):
        R.validate_amount("abc", 200_000_000)


def test_normalize_steps_finance_always_last():
    assert R.normalize_steps(None) == R.DEFAULT_STEPS
    assert R.normalize_steps(["finance", "site_manager", "x", "site_manager"]) == ["site_manager", "finance"]
    assert R.normalize_steps([]) == ["finance"]


def test_effective_steps_skips():
    base = R.DEFAULT_STEPS
    # بدون ضامن → مرحله‌ی ضامن حذف
    assert R.effective_steps(base, guarantor_count=0, requester_id=1, unit_manager_id=2, site_manager_id=3) == [
        "unit_manager",
        "site_manager",
        "finance",
    ]
    # مدیر واحد = مدیر سایت → یک بار تأیید
    assert R.effective_steps(base, guarantor_count=2, requester_id=1, unit_manager_id=2, site_manager_id=2) == [
        "guarantors",
        "unit_manager",
        "finance",
    ]
    # درخواست‌دهنده خودش مدیر سایت است
    assert R.effective_steps(base, guarantor_count=2, requester_id=3, unit_manager_id=2, site_manager_id=3) == [
        "guarantors",
        "unit_manager",
        "finance",
    ]


def test_build_installments_by_count_and_amount():
    rows = R.build_installments(100, count=3, first_month="1405/11")
    assert [r["amount"] for r in rows] == [33, 33, 34]
    assert [r["due_month"] for r in rows] == ["1405/11", "1405/12", "1406/01"]
    rows = R.build_installments(100, per_amount=40, first_month="1405/08")
    assert [r["amount"] for r in rows] == [40, 40, 20]
    assert sum(r["amount"] for r in R.build_installments(200_000_000, count=10, first_month="1405/08")) == 200_000_000
    with pytest.raises(R.LoanRuleError):
        R.build_installments(100, count=3, per_amount=40, first_month="1405/08")
    with pytest.raises(R.LoanRuleError):
        R.build_installments(100, count=3, first_month="1405/13")


def test_status_label():
    assert R.status_label("in_review", "guarantors") == "در انتظار تأیید ضامن‌ها"
    assert "نوبت 7" in R.status_label("waiting_finance", None, 7)
    assert "خارج از نوبت" in R.status_label("waiting_finance", None, None, True)


def test_effective_steps_dedupe_any_order_and_forced_guarantors():
    # مدیر سایت قبل از مدیر واحد چیده شده و هر دو یک نفرند → یک بار تأیید (اولی می‌ماند)
    assert R.effective_steps(
        ["site_manager", "unit_manager", "finance"], guarantor_count=0, requester_id=1, unit_manager_id=2, site_manager_id=2
    ) == ["site_manager", "finance"]
    # نوع ضامن‌دار ولی مسیر بدون مرحله‌ی ضامن → ضامن‌ها اول اضافه می‌شوند (وگرنه هرگز پرسیده نمی‌شدند)
    assert R.effective_steps(
        ["unit_manager", "finance"], guarantor_count=2, requester_id=1, unit_manager_id=2, site_manager_id=None
    ) == ["guarantors", "unit_manager", "finance"]


def test_installment_count_larger_than_total_rejected():
    with pytest.raises(R.LoanRuleError):
        R.build_installments(2, count=3, first_month="1405/08")
