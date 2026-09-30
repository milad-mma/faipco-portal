"""تست قواعد ماژول «مشخصات خانوادگی» (اعتبارسنجی فرم و محاسبه‌ی شمول بر اساس تنظیمات HR)."""
import copy

import pytest

from app.core import family_rules as r

TODAY = (1405, 7, 8)
NID1, NID2, NID3, NID4 = "0012345679", "0084575948", "1234567891", "0499370899"


def settings(**rules_child):
    s = r.sanitize_settings(None)
    s["rules"]["child"].update(rules_child)
    return s


def married_payload(**extra):
    p = {
        "marital_status": "married",
        "marriage_date": "1395/01/15",
        "has_children": True,
        "members": [
            {"member_type": "spouse", "first_name": "مریم", "last_name": "احمدی", "father_name": "علی",
             "national_id": NID1, "birth_date": "1370/02/03", "is_employed": False},
            {"member_type": "son", "first_name": "علی", "last_name": "رضایی", "national_id": NID2,
             "birth_date": "1398/05/01", "relation": "biological", "is_student": False},
            {"member_type": "daughter", "first_name": "سارا", "last_name": "رضایی", "national_id": NID3,
             "birth_date": "۱۴۰۰/۰۱/۰۱", "relation": "biological", "is_married": False, "is_employed": False},
        ],
    }  # fmt: skip
    p.update(extra)
    return p


# ---------- تاریخ ----------


def test_parse_and_age():
    assert r.parse_jalali("۱۴۰۳/۷/۵") == (1403, 7, 5)
    assert r.parse_jalali("14030705") == (1403, 7, 5)
    assert r.parse_jalali("1403/07/31") is None  # مهر ۳۰ روزه
    assert r.parse_jalali("abc") is None
    assert r.age_on((1387, 7, 9), TODAY) == 17
    assert r.age_on((1387, 7, 8), TODAY) == 18
    assert r.add_months((1404, 11, 30), 1) == (1404, 12, 29)
    assert r.add_months((1404, 7, 1), 12) == (1405, 7, 1)


# ---------- تنظیمات ----------


def test_sanitize_defaults_and_merge():
    s = r.sanitize_settings({"fields": {"spouse.national_id": "hidden", "bad.key": "required"}, "rules": {"child": {"son_max_age": "۲۰", "max_children": ""}}})
    assert s["fields"]["spouse.national_id"] == "hidden"
    assert "bad.key" not in s["fields"]
    assert s["rules"]["child"]["son_max_age"] == 20
    assert s["rules"]["child"]["max_children"] is None
    assert s["documents"]["student_certificate"]["renewal_months"] == 12
    m = r.merge_settings(s, {"rules": {"marriage": {"female_mode": "married"}}, "documents": {"custody_ruling": {"mode": "required"}}})
    assert m["rules"]["marriage"]["female_mode"] == "married"
    assert m["rules"]["child"]["son_max_age"] == 20  # بقیه دست‌نخورده
    assert m["documents"]["custody_ruling"]["mode"] == "required"


# ---------- اعتبارسنجی ----------


def test_validate_ok_and_normalizes():
    out = r.validate_payload(married_payload(), r.sanitize_settings(None), TODAY)
    assert out["marital_status"] == "married"
    assert [m["member_type"] for m in out["members"]] == ["spouse", "son", "daughter"]
    assert out["members"][2]["birth_date"] == "1400/01/01"
    assert out["members"][0]["employer_name"] is None  # غیرشاغل → فیلد وابسته خالی


def test_validate_errors():
    s = r.sanitize_settings(None)
    with pytest.raises(r.FamilyRuleError, match="همسر"):
        r.validate_payload(married_payload(members=[]), s, TODAY)
    p = married_payload()
    p["members"][1]["national_id"] = "1111111111"
    with pytest.raises(r.FamilyRuleError, match="کد ملی"):
        r.validate_payload(p, s, TODAY)
    p = married_payload()
    p["members"][2]["national_id"] = NID2
    with pytest.raises(r.FamilyRuleError, match="تکراری"):
        r.validate_payload(p, s, TODAY)
    p = married_payload()
    p["members"][1]["birth_date"] = "1406/01/01"
    with pytest.raises(r.FamilyRuleError, match="آینده"):
        r.validate_payload(p, s, TODAY)
    p = married_payload()
    p["members"][1]["birth_date"] = "1385/01/01"  # بالای ۱۸ سال → وضعیت تحصیل اجباری
    del p["members"][1]["is_student"]
    with pytest.raises(r.FamilyRuleError, match="وضعیت تحصیل"):
        r.validate_payload(p, s, TODAY)
    with pytest.raises(r.FamilyRuleError, match="فرزند"):
        r.validate_payload({"marital_status": "single", "has_children": True, "members": []}, s, TODAY)


def test_hidden_field_is_dropped_and_not_required():
    s = r.sanitize_settings({"fields": {"spouse.national_id": "hidden", "son.is_student": "optional"}})
    p = married_payload()
    del p["members"][1]["is_student"]
    out = r.validate_payload(p, s, TODAY)
    assert out["members"][0]["national_id"] is None


# ---------- مدارک ----------


def test_missing_documents_conditional():
    s = r.sanitize_settings(None)
    data = r.validate_payload(married_payload(), s, TODAY)
    missing = r.missing_documents(s, data, TODAY)
    assert "سند ازدواج" in missing
    assert any("شناسنامه" in x for x in missing)
    assert not any("تحصیل" in x for x in missing)
    s["documents"]["birth_certificate"]["mode"] = "optional"
    data["docs"] = [{"doc_type": "marriage_certificate"}]
    assert r.missing_documents(s, data, TODAY) == []


# ---------- شمول ----------


def _data(payload=None, s=None):
    s = s or r.sanitize_settings(None)
    return r.validate_payload(payload or married_payload(), s, TODAY), s


def test_male_married_with_children():
    data, s = _data()
    ev = r.evaluate(data, r.GENDER_MALE, 1000, s, TODAY)
    assert ev["marriage"]["eligible"] is True
    assert ev["child"]["eligible_count"] == 2


def test_min_insurance_days_blocks_children_only():
    data, s = _data()
    ev = r.evaluate(data, r.GENDER_MALE, 300, s, TODAY)
    assert ev["marriage"]["eligible"] is True
    assert ev["child"]["eligible_count"] == 0
    assert "720" in ev["child"]["blocked_reason"]
    ev = r.evaluate(data, r.GENDER_MALE, None, s, TODAY)
    assert ev["child"]["blocked_reason"] == "سابقه بیمه ثبت نشده"


def test_son_age_and_student_extension():
    p = married_payload()
    p["members"][1]["birth_date"] = "1385/01/01"  # ۲۰ ساله
    data, s = _data(p)
    ev = r.evaluate(data, r.GENDER_MALE, 1000, s, TODAY)
    son = next(c for c in ev["child"]["children"] if c["member_type"] == "son")
    assert son["eligible"] is False and "18" in son["reason"]
    # دانشجو ولی گواهی معتبر ندارد
    p["members"][1]["is_student"] = True
    data, s = _data(p)
    son = next(c for c in r.evaluate(data, r.GENDER_MALE, 1000, s, TODAY)["child"]["children"] if c["member_type"] == "son")
    assert son["eligible"] is False and "گواهی" in son["reason"]
    # گواهی تازه → مشمول؛ گواهی قدیمی (بیش از ۱۲ ماه) → غیرمشمول
    data["members"][1]["docs"] = [{"doc_type": "student_certificate", "uploaded": "1405/01/10"}]
    son = next(c for c in r.evaluate(data, r.GENDER_MALE, 1000, s, TODAY)["child"]["children"] if c["member_type"] == "son")
    assert son["eligible"] is True
    data["members"][1]["docs"] = [{"doc_type": "student_certificate", "uploaded": "1403/01/10"}]
    son = next(c for c in r.evaluate(data, r.GENDER_MALE, 1000, s, TODAY)["child"]["children"] if c["member_type"] == "son")
    assert son["eligible"] is False
    # HR سقف سن پسر را ۲۵ می‌کند
    s2 = settings(son_max_age=25)
    son = next(c for c in r.evaluate(data, r.GENDER_MALE, 1000, s2, TODAY)["child"]["children"] if c["member_type"] == "son")
    assert son["eligible"] is True


def test_daughter_married_or_employed():
    p = married_payload()
    p["members"][2].update(is_married=True, marriage_date="1405/01/01")
    data, s = _data(p)
    d = next(c for c in r.evaluate(data, r.GENDER_MALE, 1000, s, TODAY)["child"]["children"] if c["member_type"] == "daughter")
    assert d["eligible"] is False and d["reason"] == "ازدواج کرده"
    s2 = settings(daughter_stop_on_marriage=False)
    d = next(c for c in r.evaluate(data, r.GENDER_MALE, 1000, s2, TODAY)["child"]["children"] if c["member_type"] == "daughter")
    assert d["eligible"] is True


def test_female_employee_modes():
    data, s = _data()
    # همسر غیرشاغل → با حالت پیش‌فرض spouse_unable مشمول حق اولاد؛ حق تاهل فقط سرپرست خانوار
    ev = r.evaluate(data, r.GENDER_FEMALE, 1000, s, TODAY)
    assert ev["child"]["eligible_count"] == 2
    assert ev["marriage"]["eligible"] is False
    data["members"][0]["is_employed"] = True
    ev = r.evaluate(data, r.GENDER_FEMALE, 1000, s, TODAY)
    assert ev["child"]["eligible_count"] == 0
    data["is_head_of_household"] = True
    ev = r.evaluate(data, r.GENDER_FEMALE, 1000, s, TODAY)
    assert ev["child"]["eligible_count"] == 2 and ev["marriage"]["eligible"] is True
    s2 = copy.deepcopy(s)
    s2["rules"]["child"]["female_mode"] = "none"
    assert r.evaluate(data, r.GENDER_FEMALE, 1000, s2, TODAY)["child"]["eligible_count"] == 0


def test_spouse_receives_and_cap_and_disabled_rules():
    data, s = _data()
    data["members"][0]["receives_child_allowance"] = True
    assert r.evaluate(data, r.GENDER_MALE, 1000, s, TODAY)["child"]["eligible_count"] == 0
    data["members"][0]["receives_child_allowance"] = False
    s2 = settings(max_children=1)
    ev = r.evaluate(data, r.GENDER_MALE, 1000, s2, TODAY)
    assert ev["child"]["eligible_count"] == 1
    # سقف روی فرزند بزرگ‌تر اعمال می‌شود (پسر ۱۳۹۸ مشمول، دختر ۱۴۰۰ خارج از سقف)
    assert [c["eligible"] for c in ev["child"]["children"]] == [True, False]
    s3 = copy.deepcopy(s)
    s3["rules"]["child"]["enabled"] = False
    s3["rules"]["marriage"]["enabled"] = False
    ev = r.evaluate(data, r.GENDER_MALE, 1000, s3, TODAY)
    assert ev["marriage"]["eligible"] is None and ev["child"]["eligible_count"] == 0


def test_divorced_custody_and_step_child():
    p = {
        "marital_status": "divorced", "separation_date": "1402/01/01", "has_children": True,
        "members": [
            {"member_type": "son", "first_name": "الف", "last_name": "ب", "national_id": NID2, "birth_date": "1398/01/01",
             "relation": "biological", "custody": "other_parent", "is_student": False},
            {"member_type": "daughter", "first_name": "ج", "last_name": "د", "national_id": NID4, "birth_date": "1399/01/01",
             "relation": "step", "custody": "employee", "is_married": False, "is_employed": False},
        ],
    }  # fmt: skip
    data, s = _data(p)
    ev = r.evaluate(data, r.GENDER_MALE, 1000, s, TODAY)
    assert ev["marriage"]["eligible"] is False
    reasons = [c["reason"] for c in ev["child"]["children"]]
    assert reasons == ["حضانت با کارمند نیست", "فرزند همسر طبق تنظیمات مشمول نیست"]


def test_warnings_son_age_and_expiry():
    p = married_payload()
    p["members"][1]["birth_date"] = "1387/08/20"  # ۱۸ سالگی در ۱۴۰۵/۰۸/۲۰
    data, s = _data(p)
    data["members"][1]["docs"] = [{"doc_type": "student_certificate", "uploaded": "1404/07/01"}]
    w = r.warnings(data, s, TODAY)
    assert any("18 سالگی" in x for x in w)
    assert any("منقضی شده" in x for x in w)


def test_son_study_only_after_max_age():
    s = r.sanitize_settings(None)
    p = married_payload()
    p["members"][1]["is_student"] = True  # پسر ۷ ساله: سؤال تحصیل موضوعیت ندارد
    data = r.validate_payload(p, s, TODAY)
    assert data["members"][1]["is_student"] is None
    assert not any("تحصیل" in x for x in r.missing_documents(s, data, TODAY))
    # پسر ۱۹ ساله‌ی محصل → گواهی اشتغال به تحصیل اجباری
    p["members"][1].update(birth_date="1386/01/01", is_student=True)
    data = r.validate_payload(p, s, TODAY)
    assert data["members"][1]["is_student"] is True
    assert any("گواهی اشتغال به تحصیل" in x for x in r.missing_documents(s, data, TODAY))
    # HR سن سقف را ۲۰ کند → برای همین پسر دیگر لازم نیست
    s2 = settings(son_max_age=20)
    data = r.validate_payload(p, s2, TODAY)
    assert data["members"][1]["is_student"] is None
    assert not any("تحصیل" in x for x in r.missing_documents(s2, data, TODAY))


def test_warning_son_over_age_without_study_status():
    s = r.sanitize_settings(None)
    data = {"members": [{"member_type": "son", "first_name": "علی", "last_name": "ب", "birth_date": "1385/01/01", "is_student": None}]}
    assert any("وضعیت تحصیل" in w for w in r.warnings(data, s, TODAY))
