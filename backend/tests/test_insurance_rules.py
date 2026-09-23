"""تست‌های قوانین بیمه تکمیلی - مطابق سامانه قدیمی (save.php / form.js)."""
import pytest

from app.core import insurance_rules as r


def test_national_id():
    assert r.is_valid_national_id("0499370899")
    assert r.is_valid_national_id("499370899")  # ۹ رقمی → صفر ابتدایی
    assert not r.is_valid_national_id("1111111111")
    assert not r.is_valid_national_id("0012345678")
    assert r.normalize_national_id("۰۴۹۹۳۷۰۸۹۹") == "0499370899"


def test_normalizers():
    assert r.normalize_sheba("IR123456789012345678901234") == "123456789012345678901234"
    assert r.normalize_mobile("9121234567") == "09121234567"
    assert r.format_jalali_compact("13700521") == "1370/05/21"
    assert r.is_valid_jalali_date("1370/05/21") and not r.is_valid_jalali_date("13700521")


def _main(**over):
    base = {
        "father_name": "علی", "birth_certificate_no": "123", "mobile_number": "09121234567",
        "marital_status": 3, "insurance_no": "1234567890", "bank_code": 16, "account_number": "1",
        "sheba": "IR123456789012345678901234", "account_type": 1, "account_owner": "x",
        "account_owner_national_id": "0499370899",
    }  # fmt: skip
    base.update(over)
    return base


def test_validate_main_ok_and_errors():
    out = r.validate_main(_main(), "0499370899")
    assert out["sheba"] == "123456789012345678901234" and out["marital_status"] == 3
    with pytest.raises(r.InsuranceRuleError, match="صاحب حساب"):
        r.validate_main(_main(account_owner_national_id="0013542419"), "0499370899")
    with pytest.raises(r.InsuranceRuleError, match="شبا"):
        r.validate_main(_main(sheba="123"), "0499370899")
    with pytest.raises(r.InsuranceRuleError, match="۱۰ رقم"):
        r.validate_main(_main(insurance_no="12"), "0499370899")


def _emp(gender):
    return {"gender": gender, "first_name": "رضا", "last_name": "احمدی"}


def _member(**over):
    m = {
        "member_type": "son", "first_name": "امیر", "last_name": "", "father_name": "", "birth_date": "1395/01/01",
        "marital_status": 2, "national_id": "0499370899", "birth_certificate_no": "5", "kafala_status": None,
    }  # fmt: skip
    m.update(over)
    return m


def test_members_rules_for_male_employee():
    out = r.validate_members([_member()], _emp(r.GENDER_MALE), r.MARITAL_MARRIED, "09121234567")
    m = out[0]
    assert m["father_name"] == "رضا" and m["last_name"] == "احمدی" and m["gender"] == r.GENDER_MALE
    assert m["relation_code"] == 7 and m["dependency_code"] == 1 and m["mobile_number"] == "09121234567"
    assert m["kafala_status"] is None  # مرد: فرزند بدون کفالت


def test_members_kafala_and_limits():
    # زن: همه اعضا کفالت می‌خواهند
    with pytest.raises(r.InsuranceRuleError, match="تکفل"):
        r.validate_members([_member(last_name="x", father_name="y")], _emp(r.GENDER_FEMALE), r.MARITAL_MARRIED, "0912")
    # همسر برای مجرد ممنوع
    with pytest.raises(r.InsuranceRuleError, match="مجرد"):
        r.validate_members(
            [_member(member_type="spouse", last_name="x", father_name="y")], _emp(r.GENDER_MALE), r.MARITAL_SINGLE, "0912"
        )
    # دو پدر ممنوع
    fathers = [_member(member_type="father", father_name="y", marital_status=3, kafala_status="no")] * 2
    with pytest.raises(r.InsuranceRuleError, match="حداکثر"):
        r.validate_members(fathers, _emp(r.GENDER_MALE), r.MARITAL_MARRIED, "0912")
    # همسر: جنسیت برعکس و متاهل
    out = r.validate_members(
        [_member(member_type="spouse", last_name="x", father_name="y", kafala_status="no")],
        _emp(r.GENDER_FEMALE), r.MARITAL_MARRIED, "0912",
    )  # fmt: skip
    assert out[0]["gender"] == r.GENDER_MALE and out[0]["marital_status"] == r.MARITAL_MARRIED
