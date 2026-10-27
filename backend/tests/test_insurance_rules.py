"""تست‌های واحد قواعد ماژول بیمه تکمیلی (app/core/insurance_rules.py):
اعتبارسنجی کد ملی، نرمال‌سازها، فیلدهای شخص اصلی و قواعد اعضای خانواده."""
import pytest

from app.core import insurance_rules as r


# کد ملی: الگوریتم رقم کنترل، تکمیل صفر ابتدایی، رد ارقام تکراری و تبدیل ارقام فارسی
def test_national_id():
    assert r.is_valid_national_id("0499370899")
    assert r.is_valid_national_id("499370899")  # ۹ رقمی → صفر ابتدایی
    assert not r.is_valid_national_id("1111111111")
    assert not r.is_valid_national_id("0012345678")
    assert r.normalize_national_id("۰۴۹۹۳۷۰۸۹۹") == "0499370899"


# نرمال‌سازها: حذف IR از شبا، افزودن صفر به موبایل، تبدیل تاریخ فشرده به YYYY/MM/DD
def test_normalizers():
    assert r.normalize_sheba("IR123456789012345678901234") == "123456789012345678901234"
    assert r.normalize_mobile("9121234567") == "09121234567"
    assert r.format_jalali_compact("13700521") == "1370/05/21"
    assert r.is_valid_jalali_date("1370/05/21") and not r.is_valid_jalali_date("13700521")


# داده‌ی معتبر شخص اصلی که با over می‌توان فیلدهایش را برای هر تست تغییر داد
def _main(**over):
    base = {
        "father_name": "علی", "birth_certificate_no": "123", "mobile_number": "09121234567",
        "marital_status": 3, "insurance_no": "1234567890", "bank_code": 16, "account_number": "1",
        "sheba": "IR123456789012345678901234", "account_type": 1, "account_owner": "x",
        "account_owner_national_id": "0499370899",
    }  # fmt: skip
    base.update(over)
    return base


# validate_main: ورودی معتبر می‌گذرد و هر فیلد نادرست خطای مربوط به خودش را می‌دهد
def test_validate_main_ok_and_errors():
    out = r.validate_main(_main(), "0499370899")
    assert out["sheba"] == "123456789012345678901234" and out["marital_status"] == 3
    with pytest.raises(r.InsuranceRuleError, match="صاحب حساب"):
        r.validate_main(_main(account_owner_national_id="0013542419"), "0499370899")
    with pytest.raises(r.InsuranceRuleError, match="شبا"):
        r.validate_main(_main(sheba="123"), "0499370899")
    with pytest.raises(r.InsuranceRuleError, match="۱۰ رقم"):
        r.validate_main(_main(insurance_no="12"), "0499370899")


# پرسنل نمونه با جنسیت داده‌شده
def _emp(gender):
    return {"gender": gender, "first_name": "رضا", "last_name": "احمدی"}


# عضو خانواده‌ی معتبر که با over قابل تغییر است
def _member(**over):
    m = {
        "member_type": "son", "first_name": "امیر", "last_name": "", "father_name": "", "birth_date": "1395/01/01",
        "marital_status": 2, "national_id": "0499370899", "birth_certificate_no": "5", "kafala_status": None,
    }  # fmt: skip
    m.update(over)
    return m


# پرسنل مرد: نام خانوادگی/نام پدر فرزندان از پرسنل پر می‌شود و کفالت پرسیده نمی‌شود
def test_members_rules_for_male_employee():
    out = r.validate_members([_member()], _emp(r.GENDER_MALE), r.MARITAL_MARRIED, "09121234567")
    m = out[0]
    assert m["father_name"] == "رضا" and m["last_name"] == "احمدی" and m["gender"] == r.GENDER_MALE
    assert m["relation_code"] == 7 and m["dependency_code"] == 1 and m["mobile_number"] == "09121234567"
    assert m["kafala_status"] is None  # مرد: فرزند بدون کفالت


# قواعد کفالت، محدودیت تعداد هر نوع عضو و قواعد همسر
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


def test_normalize_mobile_formats_from_kara():
    """قالب‌های رایج موبایل در کاراوب به ۱۱ رقم «09...» تبدیل می‌شوند؛ داده‌ی غیرقابل‌تبدیل رد می‌شود (نه خطای ۵۰۰)."""
    from app.core import insurance_rules as r

    for raw in ("09121234567", "9121234567", "+989121234567", "00989121234567", "989121234567",
                "0912-123-4567", "0912 123 4567", "(0912) 1234567", "۰۹۱۲۱۲۳۴۵۶۷"):
        assert r.normalize_mobile(raw) == "09121234567", raw
        assert r.is_valid_mobile(r.normalize_mobile(raw)), raw
    two_numbers = "09121234567-09351234567"
    assert not r.is_valid_mobile(r.normalize_mobile(two_numbers))


# ---------- کد تکفل پدر و مادر ----------
# داده‌های دیتابیس قبلاً دستی اصلاح شده‌اند؛ این تست‌ها فقط منطق عملیات آینده (ثبت/ویرایش/رد مدرک) را می‌سنجند.

from types import SimpleNamespace  # noqa: E402

PARENTS = (("father", 3), ("mother", 4))


def _parent(mtype, kafala, **over):
    return _member(member_type=mtype, last_name="x", father_name="y", marital_status=3, kafala_status=kafala, **over)


def _save(members_in, gender=r.GENDER_MALE):
    """شبیه‌سازی ذخیره: خروجی validate_members همان چیزی است که در ستون‌ها نوشته و بعداً خوانده/اکسل می‌شود."""
    return r.validate_members(members_in, _emp(gender), r.MARITAL_MARRIED, "09121234567")


@pytest.mark.parametrize("gender", [r.GENDER_MALE, r.GENDER_FEMALE])
@pytest.mark.parametrize("mtype,relation", PARENTS)
def test_parent_dependency_code_from_kafala(mtype, relation, gender):
    no = _save([_parent(mtype, "no")], gender)[0]
    assert (no["kafala_status"], no["dependency_code"], no["relation_code"]) == ("no", 2, relation)
    yes = _save([_parent(mtype, "yes")], gender)[0]
    assert (yes["kafala_status"], yes["dependency_code"], yes["relation_code"]) == ("yes", 1, relation)


@pytest.mark.parametrize("mtype,_relation", PARENTS)
@pytest.mark.parametrize("bad", [None, "", "  ", "maybe", "YES", "1", 2])
def test_parent_empty_or_invalid_kafala_rejected(mtype, _relation, bad):
    """پاسخ خالی/نامعتبر رد می‌شود و خودکار «خیر» در نظر گرفته نمی‌شود."""
    with pytest.raises(r.InsuranceRuleError, match="تکفل"):
        _save([_parent(mtype, bad)])
    with pytest.raises(r.InsuranceRuleError, match="تکفل"):
        r.member_dependency_code(mtype, bad)


@pytest.mark.parametrize("mtype,_relation", PARENTS)
def test_parent_code_ignores_client_supplied_code(mtype, _relation):
    """کد ارسالی کلاینت (یا مقدار قبلی) نادیده گرفته می‌شود؛ فقط پاسخ تکفل تعیین‌کننده است."""
    out = _save([_parent(mtype, "no", dependency_code=1)])[0]
    assert out["dependency_code"] == 2
    out = _save([_parent(mtype, "yes", dependency_code=2)])[0]
    assert out["dependency_code"] == 1


@pytest.mark.parametrize("mtype,_relation", PARENTS)
def test_parent_status_change_both_directions(mtype, _relation):
    first = _save([_parent(mtype, "no")])[0]
    assert first["dependency_code"] == 2
    to_yes = _save([_parent(mtype, "yes")])[0]  # no → yes
    assert (to_yes["kafala_status"], to_yes["dependency_code"]) == ("yes", 1)
    back = _save([_parent(mtype, "no")])[0]  # yes → no
    assert (back["kafala_status"], back["dependency_code"]) == ("no", 2)


def _stored(spec, rejected_at=None):
    """یک «عضو ذخیره‌شده» (شبیه ردیف دیتابیس) از خروجی اعتبارسنجی."""
    return SimpleNamespace(
        member_type=spec["member_type"], kafala_status=spec["kafala_status"],
        dependency_code=spec["dependency_code"], relation_code=spec["relation_code"], document_rejected_at=rejected_at,
    )  # fmt: skip


@pytest.mark.parametrize("mtype,relation", PARENTS)
def test_admin_reject_then_resubmit_with_new_document(mtype, relation):
    stored = _stored(_save([_parent(mtype, "yes")])[0])
    assert (stored.kafala_status, stored.dependency_code) == ("yes", 1)

    # رد مدرک توسط ادمین: زمان رد + غیر تحت کفالت + کد ۲ (کد نسبت دست نمی‌خورد)
    r.apply_document_rejection(stored, "2026-10-27T10:00")
    assert stored.document_rejected_at == "2026-10-27T10:00"
    assert (stored.kafala_status, stored.dependency_code, stored.relation_code) == ("no", 2, relation)

    # ویرایش بدون تغییر وضعیت (هنوز «خیر»): علامت رد حفظ می‌شود تا هشدار بماند
    kept = _save([_parent(mtype, "no")])[0]
    assert r.carried_rejection_mark(stored, mtype, kept["kafala_status"]) == "2026-10-27T10:00"
    assert kept["dependency_code"] == 2

    # انتخاب مجدد «تحت کفالت» + مدرک جدید (وجود مدرک در سرویس بررسی می‌شود): yes/۱ و علامت رد پاک
    again = _save([_parent(mtype, "yes")])[0]
    assert (again["kafala_status"], again["dependency_code"]) == ("yes", 1)
    assert r.carried_rejection_mark(stored, mtype, again["kafala_status"]) is None


def test_rejection_does_not_change_other_members():
    """رد مدرک همسر/فرزند (پرسنل زن) فقط علامت رد می‌گذارد؛ وضعیت و کدهایشان مثل قبل می‌ماند."""
    for mtype, relation in (("spouse", 2), ("son", 7), ("daughter", 8)):
        spec = _save([_member(member_type=mtype, last_name="x", father_name="y", kafala_status="yes")], r.GENDER_FEMALE)[0]
        stored = _stored(spec)
        r.apply_document_rejection(stored, "t")
        assert (stored.kafala_status, stored.dependency_code, stored.relation_code) == ("yes", 1, relation)
        assert r.carried_rejection_mark(stored, mtype, "no") is None


def test_other_members_codes_unchanged():
    """کد نسبت/تکفل همسر و فرزندان (حتی متأهل، حتی «غیر تحت کفالت» برای پرسنل زن) مثل قبل است."""
    for gender in (r.GENDER_MALE, r.GENDER_FEMALE):
        kafala = "no" if gender == r.GENDER_FEMALE else None
        members = [
            _member(member_type="spouse", last_name="x", father_name="y", kafala_status=kafala),
            _member(member_type="son", last_name="x", father_name="y", marital_status=3, kafala_status=kafala),
            _member(member_type="daughter", last_name="x", father_name="y", kafala_status=kafala),
        ]
        out = _save(members, gender)
        assert [(m["relation_code"], m["dependency_code"]) for m in out] == [(2, 1), (7, 1), (8, 1)]


# ---------- مبلغ حق بیمه (ستون‌های Excel) ----------


def test_parse_age_range_from_labels_and_explicit_numbers():
    assert r.parse_age_range({"age_label": "۱ تا ۶۰ سال"}) == (1, 60)
    assert r.parse_age_range({"age_label": "۶۱ تا ۷۰ سال"}) == (61, 70)
    assert r.parse_age_range({"age_label": "بالاتر از ۷۱ سال"}) == (71, None)
    assert r.parse_age_range({"age_label": "۷۱ سال به بالا"}) == (71, None)
    assert r.parse_age_range({"age_label": "تا ۶۰ سال"}) == (None, 60)
    # عدد صریح بر برچسب مقدم است
    assert r.parse_age_range({"age_label": "۱ تا ۶۰", "age_from": 0, "age_to": 65}) == (0, 65)
    assert r.parse_age_range({"age_label": "گروه سالمند", "age_from": "۶۶"}) == (66, None)


def test_age_in_years():
    assert r.age_in_years("1370/05/21", (1405, 5, 21)) == 35
    assert r.age_in_years("1370/05/21", (1405, 5, 20)) == 34
    assert r.age_in_years("13700521", (1405, 8, 1)) == 35
    assert r.age_in_years("1405/03/01", (1405, 8, 1)) == 0  # نوزاد
    assert r.age_in_years("", (1405, 8, 1)) is None
    assert r.age_in_years("bad", (1405, 8, 1)) is None


def test_premium_amount_by_age_and_dependency():
    t = r.DEFAULT_RATE_TABLE
    assert r.premium_amount(35, True, t) == 690000
    assert r.premium_amount(35, False, t) == 1380000
    assert r.premium_amount(61, True, t) == 1035000
    assert r.premium_amount(70, False, t) == 2070000
    assert r.premium_amount(71, True, t) == 1380000
    assert r.premium_amount(95, False, t) == 2760000
    assert r.premium_amount(0, True, t) == 690000  # کمتر از سطر اول → سطر اول
    assert r.premium_amount(None, True, t) is None
    assert r.premium_amount(30, True, {"rows": []}) is None


def test_member_is_dependent():
    assert r.member_is_dependent("self", None, 3)
    assert r.member_is_dependent("spouse", None, 1)  # پرسنل مرد: همسر تحت تکفل
    assert not r.member_is_dependent("spouse", "no", 1)  # پرسنل زن بدون مدرک: غیر تحت تکفل
    assert r.member_is_dependent("son", "yes", 1)
    assert not r.member_is_dependent("father", "no", 2)
    assert r.member_is_dependent("mother", "yes", 1)


def test_family_premiums_and_total():
    t = r.DEFAULT_RATE_TABLE
    people = [
        {"member_type": "self", "birth_date": "1365/01/01"},  # 40 → تحت تکفل 690000
        {"member_type": "spouse", "kafala_status": None, "dependency_code": 1, "birth_date": "1368/01/01"},  # 690000
        {"member_type": "father", "kafala_status": "no", "dependency_code": 2, "birth_date": "1340/01/01"},  # 65 → 2070000
        {"member_type": "mother", "kafala_status": "yes", "dependency_code": 1, "birth_date": "1330/01/01"},  # 75 → 1380000
        {"member_type": "son", "kafala_status": None, "dependency_code": 1, "birth_date": ""},  # نامعلوم
    ]
    amounts, total = r.family_premiums(people, t, (1405, 8, 1))
    assert amounts == [690000, 690000, 2070000, 1380000, None]
    assert total == 690000 + 690000 + 2070000 + 1380000
