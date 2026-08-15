"""
Reshape/Bidi حداقلی و بدون هیچ وابستگی خارجی — Fallback برای وقتی که
arabic-reshaper و/یا python-bidi روی سرور نصب نشده باشند (یا نصبشان به هر
دلیلی شکست بخورد). کتابخانه‌های واقعی (در requirements.txt) دقیق‌تر و
استانداردند و همیشه اول امتحان می‌شوند؛ این پیاده‌سازی فقط شبکه ایمنی است.

پیاده‌سازی می‌کند:
1. Presentation-Form Shaping: هر حرف عربی/فارسی بسته به همسایه‌هایش (شروع/میانی/
   پایانی/مجزا) به Codepoint شکل‌گرفته خودش (بازه U+FE70..U+FEFF و بخشی از
   U+FB50..U+FDFF) تبدیل می‌شود تا در فونت‌هایی مثل DejaVu Sans (که این
   Codepoint ها را دارد ولی خودش Shaping انجام نمی‌دهد) متصل نمایش داده شود.
2. Bidi حداقلی: بخش‌های متوالی راست‌به‌چپ (فارسی/عربی) در رشته را معکوس
   می‌کند تا وقتی موتور رسم متن (ReportLab) فقط چپ‌به‌راست رسم می‌کند، ترتیب
   خواندن درست باشد. این پیاده‌سازی الگوریتم کامل Unicode Bidi (UAX #9)
   نیست؛ اعداد/لاتین داخل یک بخش فارسی به‌درستی مدیریت می‌شوند ولی حالت‌های
   بسیار تودرتوی چندزبانه ممکن است دقیق نباشند.
"""
from __future__ import annotations

import re

# نگاشت حرف پایه فارسی/عربی -> (مجزا، شروع، میانی، پایانی)
# فقط حروفی که در Presentation Form-B هستند؛ حروف غیرمتصل‌شونده (ا،د،ذ،ر،ز،ژ،و)
# فقط دو حالت مجزا/پایانی دارند.
_SHAPES: dict[str, tuple[str, str, str, str]] = {
    "\u0627": ("\uFE8D", "\uFE8D", "\uFE8E", "\uFE8E"),  # ا
    "\u0628": ("\uFE8F", "\uFE91", "\uFE92", "\uFE90"),  # ب
    "\u067E": ("\uFB56", "\uFB58", "\uFB59", "\uFB57"),  # پ
    "\u062A": ("\uFE95", "\uFE97", "\uFE98", "\uFE96"),  # ت
    "\u062B": ("\uFE99", "\uFE9B", "\uFE9C", "\uFE9A"),  # ث
    "\u062C": ("\uFE9D", "\uFE9F", "\uFEA0", "\uFE9E"),  # ج
    "\u0686": ("\uFB7A", "\uFB7C", "\uFB7D", "\uFB7B"),  # چ
    "\u062D": ("\uFEA1", "\uFEA3", "\uFEA4", "\uFEA2"),  # ح
    "\u062E": ("\uFEA5", "\uFEA7", "\uFEA8", "\uFEA6"),  # خ
    "\u062F": ("\uFEA9", "\uFEA9", "\uFEAA", "\uFEAA"),  # د
    "\u0630": ("\uFEAB", "\uFEAB", "\uFEAC", "\uFEAC"),  # ذ
    "\u0631": ("\uFEAD", "\uFEAD", "\uFEAE", "\uFEAE"),  # ر
    "\u0632": ("\uFEAF", "\uFEAF", "\uFEB0", "\uFEB0"),  # ز
    "\u0698": ("\uFB8A", "\uFB8A", "\uFB8B", "\uFB8B"),  # ژ
    "\u0633": ("\uFEB1", "\uFEB3", "\uFEB4", "\uFEB2"),  # س
    "\u0634": ("\uFEB5", "\uFEB7", "\uFEB8", "\uFEB6"),  # ش
    "\u0635": ("\uFEB9", "\uFEBB", "\uFEBC", "\uFEBA"),  # ص
    "\u0636": ("\uFEBD", "\uFEBF", "\uFEC0", "\uFEBE"),  # ض
    "\u0637": ("\uFEC1", "\uFEC3", "\uFEC4", "\uFEC2"),  # ط
    "\u0638": ("\uFEC5", "\uFEC7", "\uFEC8", "\uFEC6"),  # ظ
    "\u0639": ("\uFEC9", "\uFECB", "\uFECC", "\uFECA"),  # ع
    "\u063A": ("\uFECD", "\uFECF", "\uFED0", "\uFECE"),  # غ
    "\u0641": ("\uFED1", "\uFED3", "\uFED4", "\uFED2"),  # ف
    "\u0642": ("\uFED5", "\uFED7", "\uFED8", "\uFED6"),  # ق
    "\u06A9": ("\uFB8E", "\uFB90", "\uFB91", "\uFB8F"),  # ک
    "\u0643": ("\uFED9", "\uFEDB", "\uFEDC", "\uFEDA"),  # ك
    "\u06AF": ("\uFB92", "\uFB94", "\uFB95", "\uFB93"),  # گ
    "\u0644": ("\uFEDD", "\uFEDF", "\uFEE0", "\uFEDE"),  # ل
    "\u0645": ("\uFEE1", "\uFEE3", "\uFEE4", "\uFEE2"),  # م
    "\u0646": ("\uFEE5", "\uFEE7", "\uFEE8", "\uFEE6"),  # ن
    "\u0648": ("\uFEED", "\uFEED", "\uFEEE", "\uFEEE"),  # و
    "\u0647": ("\uFEE9", "\uFEEB", "\uFEEC", "\uFEEA"),  # ه
    "\u06CC": ("\uFBFC", "\uFBFE", "\uFBFF", "\uFBFD"),  # ی
    "\u064A": ("\uFEF1", "\uFEF3", "\uFEF4", "\uFEF2"),  # ي
}

# حروف غیرمتصل‌شونده به حرف بعدی (بعد از این حروف، حرف بعدی همیشه با شکل «شروع» خودش می‌آید)
_NON_JOINING_NEXT = {"\u0627", "\u062F", "\u0630", "\u0631", "\u0632", "\u0698", "\u0648"}

_RTL_CHAR_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))

# رشته اعداد (فارسی یا لاتین، با جداکننده هزارگان/اعشار) — این‌ها با این‌که در
# بازه یونیکد فارسی/عربی هم افتاده باشند (ارقام ۰-۹)، نباید حرف‌به‌حرف معکوس
# شوند؛ فقط ترتیب کل عدد نسبت به متن اطرافش (به‌عنوان یک بلوک) عوض می‌شود.
_DIGIT_RUN_RE = re.compile(r"[0-9۰-۹]+([.,٫٬][0-9۰-۹]+)*")


def _is_rtl_letter(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _RTL_CHAR_RANGES) or ch in _SHAPES


def simple_reshape(text: str) -> str:
    """هر حرف فارسی/عربی را به شکل Presentation Form مناسب موقعیتش (شروع/میانی/پایانی/مجزا) تبدیل می‌کند."""
    chars = list(text)
    out: list[str] = []
    n = len(chars)
    for i, ch in enumerate(chars):
        shapes = _SHAPES.get(ch)
        if shapes is None:
            out.append(ch)
            continue
        prev_ch = chars[i - 1] if i > 0 else None
        next_ch = chars[i + 1] if i + 1 < n else None
        joins_prev = prev_ch in _SHAPES and prev_ch not in _NON_JOINING_NEXT
        joins_next = next_ch in _SHAPES
        isolated, initial, medial, final = shapes
        if joins_prev and joins_next:
            out.append(medial)
        elif joins_prev and not joins_next:
            out.append(final)
        elif not joins_prev and joins_next:
            out.append(initial)
        else:
            out.append(isolated)
    return "".join(out)


def _reverse_rtl_chunk(chunk: str) -> str:
    """
    داخل یک بخش RTL، حروف را حرف‌به‌حرف معکوس می‌کند — به‌جز رشته‌های عددی
    (فارسی یا لاتین) که به‌صورت یک بلوک دست‌نخورده جابه‌جا می‌شوند تا مثلاً
    «۳۱» به‌غلط به «۱۳» تبدیل نشود.
    """
    segments: list[tuple[str, bool]] = []  # (متن, آیا عدد است)
    last = 0
    for m in _DIGIT_RUN_RE.finditer(chunk):
        if m.start() > last:
            segments.append((chunk[last : m.start()], False))
        segments.append((m.group(0), True))
        last = m.end()
    if last < len(chunk):
        segments.append((chunk[last:], False))
    segments.reverse()
    return "".join(seg if is_num else seg[::-1] for seg, is_num in segments)


def simple_bidi(text: str) -> str:
    """
    بخش‌های متوالی راست‌به‌چپ را معکوس می‌کند (اعداد داخل هر بخش دست‌نخورده
    می‌مانند چون رشته‌های عددی نباید حرف‌به‌حرف معکوس شوند).
    """
    if not any(_is_rtl_letter(ch) for ch in text):
        return text

    tokens: list[tuple[bool, str]] = []  # (is_rtl_run, text)
    current_rtl: list[str] = []
    current_ltr: list[str] = []

    def flush_rtl():
        if current_rtl:
            tokens.append((True, "".join(current_rtl)))
            current_rtl.clear()

    def flush_ltr():
        if current_ltr:
            tokens.append((False, "".join(current_ltr)))
            current_ltr.clear()

    for ch in text:
        if _is_rtl_letter(ch) or ch in " \u200c،؛؟٫٬:()[]«»":
            # فاصله و علائم رایج فارسی به بخش RTL جاری می‌چسبند تا از هم نپاشد
            if current_ltr and not current_rtl:
                flush_ltr()
            current_rtl.append(ch)
        else:
            if current_rtl:
                flush_rtl()
            current_ltr.append(ch)
    flush_rtl()
    flush_ltr()

    result: list[str] = []
    for is_rtl, chunk in tokens:
        result.append(_reverse_rtl_chunk(chunk) if is_rtl else chunk)
    # کل دنباله Token ها هم باید معکوس شود چون بخش‌های RTL باید از سمت راست شروع شوند
    result.reverse()
    return "".join(result)
