"""
تشخیص کلمات/عبارات نامناسب در متن فارسی - مستقل از منبع فهرست کلمات
(که در دیتابیس، جدول ProhibitedPhrase، نگهداری و توسط Admin واقعی
مدیریت می‌شود؛ به app/models/feedback.py مراجعه کنید).

طبق درخواست صریح، این ماژول Token-aware است، نه صرفاً substring-محور:
    - برای عبارات کوتاه/مبهم (مثلاً کلمات ۲-۳ حرفی که می‌توانند زیررشته
      تصادفی کلمات کاملاً بی‌ربط دیگر هم باشند)، فقط تطبیق کامل با یک
      توکن (کلمه مستقل، نه بخشی از یک کلمه دیگر) پذیرفته می‌شود.
    - تشخیص «شکل شکسته‌شده» (حروف جداشده با فاصله/علامت، مثل «ک ی ر»
      یا «ک.ی.ر») فقط برای کلمات نسبتاً بلندتر (۴+ حرف) فعال است - برای
      کلمات کوتاه، این حالت به‌شدت مستعد False Positive است.
    - عبارات چندکلمه‌ای (مثل «بی شرف») به‌صورت دنباله‌ای از توکن‌های
      متوالی بررسی می‌شوند، نه یک عبارت خام.

کارایی: هیچ حالت نوشتاری‌ای از پیش تولید/ذخیره نمی‌شود - برای هر پیام،
متن یک‌بار نرمال‌سازی و توکنایز می‌شود، و هر عبارت هم یک‌بار (در لحظه
بررسی) نرمال می‌شود؛ الگوهای Regex شکل‌شکسته هم فقط برای همان یک پیام،
در حافظه ساخته می‌شوند - نه برای کل فهرست از قبل.
"""
from __future__ import annotations

import re

from app.core.persian_text_normalize import collapse_repeated_letters, normalize_persian_text, tokenize

# حداقل طول کلمه (بعد از نرمال‌سازی) برای فعال‌شدن تشخیص «شکل شکسته‌شده»
# (حروف جداشده با فاصله/علامت). زیر این طول، ریسک False Positive
# (تطبیق تصادفی با متن سالم) خیلی بالا می‌رود. ۳ انتخاب شد (نه ۴) چون
# چند کلمه فحش‌آمیز رایج (مثل «کیر») دقیقاً ۳ حرفی‌اند و شکل جداشده‌شان
# ("ک ی ر") باید تشخیص داده شود؛ محدودیت مرز کلمه (\\b مانند) و اجازه
# فقط به نویز غیرحرفی بین حروف (نه حرف دیگر)، ریسک False Positive را در
# همین طول هم به‌قدر کافی پایین نگه می‌دارد.
_MIN_LENGTH_FOR_BROKEN_FORM_DETECTION = 3


def _normalize_word(word: str) -> str:
    return collapse_repeated_letters(normalize_persian_text(word))


def _build_broken_form_pattern(normalized_word: str) -> re.Pattern[str]:
    """
    Regex ای که بین هر حرفِ کلمه، هر مقدار نویز غیرحرفی (فاصله، نقطه،
    خط‌تیره، ...) را اختیاری می‌پذیرد - برای تشخیص «ک ی ر» یا «ک.ی.ر».
    \\W در حالت Unicode پایتون، حروف فارسی را «حرف» (نه نویز) در نظر
    می‌گیرد، پس این Regex هرگز با یک حرف فارسیِ دیگر به‌عنوان «نویز بین
    دو حرف» تطبیق پیدا نمی‌کند - فقط با فاصله/علائم نگارشی واقعی.
    """
    escaped_letters = [re.escape(ch) for ch in normalized_word]
    inner = r"[\W_]*".join(escaped_letters)
    # (?<!\w) / (?!\w) : مرز کلمه از هر دو طرف - این‌طور شکل شکسته یک
    # کلمه کوتاه در وسط یک کلمه بلندتر و کاملاً بی‌ربط تشخیص داده نمی‌شود
    return re.compile(rf"(?<!\w){inner}(?!\w)")


def contains_prohibited_phrase(text: str, prohibited_phrases: list[str]) -> bool:
    """
    آیا متن حاوی هرکدام از عبارات فهرست است - با در نظر گرفتن نویسه‌های
    عربی/فارسی معادل، نیم‌فاصله، کشیده، تکرار حروف، و فاصله/علامت بین حروف.
    """
    if not text or not prohibited_phrases:
        return False

    normalized_text = normalize_persian_text(text)
    text_tokens = [collapse_repeated_letters(t) for t in tokenize(normalized_text)]
    # برای تشخیص شکل شکسته‌شده، به کل متنِ نرمال‌شده (نه فقط توکن‌ها) نیاز داریم
    collapsed_normalized_text = collapse_repeated_letters(normalized_text)

    for phrase in prohibited_phrases:
        normalized_phrase = normalize_persian_text(phrase)
        phrase_tokens = [_normalize_word(t) for t in tokenize(normalized_phrase)]
        if not phrase_tokens:
            continue

        if _matches_as_token_sequence(text_tokens, phrase_tokens):
            return True

        # تشخیص شکل شکسته‌شده فقط برای عبارات تک‌کلمه‌ای و نسبتاً بلند
        if len(phrase_tokens) == 1 and len(phrase_tokens[0]) >= _MIN_LENGTH_FOR_BROKEN_FORM_DETECTION:
            pattern = _build_broken_form_pattern(phrase_tokens[0])
            if pattern.search(collapsed_normalized_text):
                return True

    return False


def _matches_as_token_sequence(text_tokens: list[str], phrase_tokens: list[str]) -> bool:
    """آیا phrase_tokens به‌صورت یک دنباله متوالی، دقیقاً همان‌طور، در text_tokens ظاهر می‌شود."""
    n, m = len(text_tokens), len(phrase_tokens)
    if m == 0 or m > n:
        return False
    for start in range(n - m + 1):
        if text_tokens[start : start + m] == phrase_tokens:
            return True
    return False
