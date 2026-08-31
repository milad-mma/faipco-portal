"""
تست‌های واحد برای app.core.profanity_filter و app.core.persian_text_normalize.

اجرا: از پوشه backend/  ->  pytest tests/test_profanity_filter.py -v
"""
from app.core.persian_text_normalize import (
    collapse_repeated_letters,
    normalize_persian_text,
    tokenize,
)
from app.core.profanity_filter import contains_prohibited_phrase

# فهرست کوچک و ثابت برای تست - مستقل از فهرست واقعی دیتابیس، تا این
# تست‌ها با تغییر فهرست واقعی خراب نشوند.
PHRASES = ["کیر", "خر", "کس", "بی شرف", "کونی", "احمق"]


# ---------- normalize_persian_text ----------


def test_normalize_arabic_yeh_to_persian():
    assert normalize_persian_text("علي") == "علی"


def test_normalize_arabic_kaf_to_persian():
    assert normalize_persian_text("كتاب") == "کتاب"


def test_normalize_teh_marbuta_to_heh():
    assert normalize_persian_text("خانة") == "خانه"


def test_normalize_zwnj_becomes_space():
    result = normalize_persian_text("می‌روم")
    assert "\u200c" not in result


def test_normalize_kashida_removed():
    assert "\u0640" not in normalize_persian_text("سلاـم")


def test_collapse_repeated_letters():
    assert collapse_repeated_letters("کوووووس") == "کوس"


def test_collapse_repeated_letters_does_not_break_clean_word():
    assert collapse_repeated_letters("سلام") == "سلام"


def test_tokenize_basic():
    assert tokenize(normalize_persian_text("این یک متن   تست است.")) == ["این", "یک", "متن", "تست", "است"]


# ---------- contains_prohibited_phrase - حالت‌های درخواستی کاربر ----------


def test_normal_case_detected():
    assert contains_prohibited_phrase("این پیام حاوی کیر است", PHRASES) is True


def test_normal_clean_text_not_flagged():
    assert contains_prohibited_phrase("سلام همکار گرامی", PHRASES) is False


def test_letter_spacing_detected():
    assert contains_prohibited_phrase("ک ی ر", PHRASES) is True


def test_zwnj_in_clean_text_not_flagged():
    assert contains_prohibited_phrase("می‌روم به خانه و می‌آیم", PHRASES) is False


def test_arabic_persian_chars_detected():
    assert contains_prohibited_phrase("كوني هستی", PHRASES) is True  # ك و ي عربی


def test_kashida_detected():
    assert contains_prohibited_phrase("کـیر", PHRASES) is True


def test_punctuation_between_letters_detected():
    assert contains_prohibited_phrase("ک.ی.ر", PHRASES) is True
    assert contains_prohibited_phrase("ک-ی-ر", PHRASES) is True
    assert contains_prohibited_phrase("ک_ی_ر", PHRASES) is True


def test_repeated_letters_detected():
    assert contains_prohibited_phrase("کیررررر", PHRASES) is True
    assert contains_prohibited_phrase("احمممقق", PHRASES) is True


def test_clean_text_with_ambiguous_substrings_not_flagged():
    """
    مهم‌ترین دسته تست: کلمات کوتاه فهرست (خر، کس) زیررشته تصادفی کلمات
    کاملاً سالم و رایج دیگری هم هستند - نباید Flag شوند (اثبات
    Token-aware بودن، نه صرفاً substring matching).
    """
    assert contains_prohibited_phrase("امروز خرید رفتم", PHRASES) is False  # "خر" در "خرید"
    assert contains_prohibited_phrase("کسی نیامد", PHRASES) is False  # "کس" در "کسی"
    assert contains_prohibited_phrase("خرداد ماه خوبی است", PHRASES) is False  # "خر" در "خرداد"
    assert contains_prohibited_phrase("این کار کسل‌کننده است", PHRASES) is False  # "کس" در "کسل"
    assert contains_prohibited_phrase("کوهنوردی کردیم", PHRASES) is False


def test_multi_word_phrase_detected():
    assert contains_prohibited_phrase("تو واقعا بی شرف هستی", PHRASES) is True


def test_multi_word_phrase_wrong_order_not_flagged():
    assert contains_prohibited_phrase("بی نهایت شرف داری", PHRASES) is False


def test_empty_text_not_flagged():
    assert contains_prohibited_phrase("", PHRASES) is False


def test_empty_phrase_list_never_flags():
    assert contains_prohibited_phrase("هر متنی حتی کیر", []) is False


def test_combined_evasion_techniques():
    """ترکیب چند تکنیک هم‌زمان: نویسه عربی + تکرار حرف + علامت بین حروف."""
    assert contains_prohibited_phrase("ك.ي.ررر", PHRASES) is True
