"""
قواعد خالص (بدون دیتابیس) ماژول «درخواست وام» — docs/loans.md.

- سابقه: فقط از تاریخ استخدامِ دوره‌ی فعلی (شرط «طلب سنوات»؛ دوره‌های قبلی کسی که ترک کار کرده و برگشته
  حساب نمی‌شود). مالی می‌تواند برای یک نفر «تاریخ شروع سابقه» را دستی اصلاح کند (مثلاً انتقال بین سایت‌ها).
- مسیر تأیید: فهرست مرتب از STEP_KEYS؛ «مالی» همیشه آخر و اجباری است (مبلغ و اقساط را مالی تعیین می‌کند).
- اقساط: مالی یا تعداد قسط یا مبلغ هر قسط را می‌دهد؛ باقیمانده‌ی تقسیم روی قسط آخر می‌رود.
"""
from __future__ import annotations

from app.core.family_rules import format_jalali, parse_jalali

# کلید مراحل مسیر تأیید (به ترتیب پیش‌فرض) و عنوان فارسی هر کدام
STEP_GUARANTORS = "guarantors"
STEP_UNIT_MANAGER = "unit_manager"
STEP_SITE_MANAGER = "site_manager"
STEP_FINANCE = "finance"
STEP_KEYS = (STEP_GUARANTORS, STEP_UNIT_MANAGER, STEP_SITE_MANAGER, STEP_FINANCE)
STEP_LABELS = {
    STEP_GUARANTORS: "ضامن‌ها",
    STEP_UNIT_MANAGER: "مدیر واحد",
    STEP_SITE_MANAGER: "مدیر سایت",
    STEP_FINANCE: "واحد مالی",
}
DEFAULT_STEPS = list(STEP_KEYS)

# وضعیت‌های درخواست
STATUS_IN_REVIEW = "in_review"  # در یکی از مراحل تأیید پیش از مالی
STATUS_WAITING_FINANCE = "waiting_finance"  # همه تأیید کرده‌اند؛ در صف پرداخت واحد مالی
STATUS_ACTIVE = "active"  # پرداخت شده؛ در حال بازپرداخت اقساط
STATUS_SETTLED = "settled"  # تسویه شده
STATUS_REJECTED = "rejected"
STATUS_CANCELLED = "cancelled"
OPEN_STATUSES = (STATUS_IN_REVIEW, STATUS_WAITING_FINANCE)  # درخواست باز (هر پرسنل حداکثر یکی)
UNSETTLED_STATUSES = (STATUS_IN_REVIEW, STATUS_WAITING_FINANCE, STATUS_ACTIVE)

MAX_AMOUNT = 10**15  # سقف منطقی مبلغ (ریال) برای جلوگیری از ورودی بی‌معنی
MAX_INSTALLMENTS = 120


class LoanRuleError(ValueError):
    """خطای قابل نمایش به کاربر (متن فارسی)."""


def normalize_steps(steps) -> list[str]:
    """
    مسیر تأیید ذخیره‌شده/ورودی را تمیز می‌کند: فقط کلیدهای شناخته‌شده، بدون تکرار، و «مالی» همیشه آخر.
    None/غیرفهرست → مسیر پیش‌فرض؛ فهرست خالی → فقط «مالی».
    """
    if not isinstance(steps, (list, tuple)):
        return list(DEFAULT_STEPS)
    out: list[str] = []
    for key in steps:
        if key in STEP_KEYS and key != STEP_FINANCE and key not in out:
            out.append(key)
    out.append(STEP_FINANCE)
    return out


def effective_steps(
    policy_steps,
    *,
    guarantor_count: int,
    requester_id: int,
    unit_manager_id: int | None,
    site_manager_id: int | None,
) -> list[str]:
    """
    مراحل واقعی یک درخواست هنگام ثبت (snapshot روی خود درخواست):
    - «ضامن‌ها» وقتی نوع وام ضامن نمی‌خواهد حذف می‌شود؛
    - «مدیر واحد» وقتی خودِ درخواست‌دهنده است حذف می‌شود؛
    - «مدیر سایت» وقتی خودِ درخواست‌دهنده یا همان مدیر واحد است حذف می‌شود (یک نفر دو بار تأیید نمی‌کند).
    نبودنِ تأییدکننده‌ی لازم را این تابع بررسی نمی‌کند (سرویس پیش از این خطا می‌دهد).
    """
    steps = normalize_steps(policy_steps)
    # نوعی که ضامن می‌خواهد بدون مرحله‌ی ضامن معنی ندارد (ضامن‌ها هرگز پرسیده نمی‌شدند): اول مسیر اضافه می‌شود
    if guarantor_count > 0 and STEP_GUARANTORS not in steps:
        steps.insert(0, STEP_GUARANTORS)
    out: list[str] = []
    for key in steps:
        if key == STEP_GUARANTORS and guarantor_count <= 0:
            continue
        if key == STEP_UNIT_MANAGER and unit_manager_id == requester_id:
            continue
        if key == STEP_SITE_MANAGER and site_manager_id == requester_id:
            continue
        out.append(key)
    # مدیر واحد و مدیر سایت یک نفر: فقط اولین مرحله (به هر ترتیبی که چیده شده) می‌ماند
    if STEP_UNIT_MANAGER in out and STEP_SITE_MANAGER in out and unit_manager_id == site_manager_id:
        later = max(out.index(STEP_UNIT_MANAGER), out.index(STEP_SITE_MANAGER))
        out.pop(later)
    return out


def months_between(start, today) -> int | None:
    """
    تعداد ماه‌های کامل از تاریخ شمسی start تا today (هر دو رشته یا تاپل). مثال: 1404/01/10 تا 1405/03/09 → ۱۳.
    تاریخ نامعتبر/خالی → None؛ تاریخ آینده → ۰.
    """
    s = start if isinstance(start, tuple) else parse_jalali(start)
    t = today if isinstance(today, tuple) else parse_jalali(today)
    if not s or not t:
        return None
    months = (t[0] - s[0]) * 12 + (t[1] - s[1])
    if t[2] < s[2]:
        months -= 1
    return max(months, 0)


def format_service(months: int | None) -> str:
    """۲۶ → «۲ سال و ۲ ماه»؛ None → «نامشخص»."""
    if months is None:
        return "نامشخص"
    years, rem = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} سال")
    if rem or not years:
        parts.append(f"{rem} ماه")
    return " و ".join(parts)


def type_ineligibility(loan_type: dict, service_months: int | None) -> str | None:
    """
    چرا پرسنل این نوع وام را نمی‌تواند بگیرد (None = می‌تواند). loan_type: dict با is_active و min_service_months.
    """
    if not loan_type.get("is_active", True):
        return "این نوع وام فعلاً غیرفعال است"
    need = int(loan_type.get("min_service_months") or 0)
    if need > 0:
        if service_months is None:
            return "تاریخ استخدام شما در سامانه ثبت نشده است؛ با منابع انسانی تماس بگیرید"
        if service_months < need:
            return f"حداقل {format_service(need)} سابقه لازم است (سابقه‌ی شما: {format_service(service_months)})"
    return None


def validate_amount(amount, max_amount) -> int:
    """مبلغ درخواستی (ریال) باید عدد صحیح مثبت و حداکثر سقف نوع وام باشد."""
    try:
        value = int(amount)
    except (TypeError, ValueError) as e:
        raise LoanRuleError("مبلغ نامعتبر است") from e
    if value <= 0:
        raise LoanRuleError("مبلغ باید بیشتر از صفر باشد")
    if value > MAX_AMOUNT:
        raise LoanRuleError("مبلغ نامعتبر است")
    if max_amount and value > int(max_amount):
        raise LoanRuleError(f"حداکثر مبلغ این نوع وام {int(max_amount):,} ریال است")
    return value


def parse_month(value) -> tuple[int, int] | None:
    """«1405/08» یا «1405-8» → (1405, 8)؛ نامعتبر → None."""
    from app.core.family_rules import to_english_digits

    text = to_english_digits(value).strip()
    parts = text.replace("-", "/").split("/")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return None
    y, m = int(parts[0]), int(parts[1])
    if not (1300 <= y <= 1500 and 1 <= m <= 12):
        return None
    return y, m


def build_installments(
    total: int, *, count: int | None = None, per_amount: int | None = None, first_month
) -> list[dict]:
    """
    جدول اقساط: [{seq, due_month: "YYYY/MM", amount}]. دقیقاً یکی از count یا per_amount.
    - count: اقساط مساوی؛ باقیمانده‌ی تقسیم به قسط آخر (۱۰۰ در ۳ قسط → ۳۳، ۳۳، ۳۴).
    - per_amount: تعداد = سقف(total / per_amount)؛ قسط آخر باقیمانده (۱۰۰ با قسط ۴۰ → ۴۰، ۴۰، ۲۰).
    """
    if total is None or int(total) <= 0:
        raise LoanRuleError("مبلغ پرداختی باید بیشتر از صفر باشد")
    total = int(total)
    start = parse_month(first_month)
    if start is None:
        raise LoanRuleError("ماه شروع اقساط نامعتبر است (مثال: 1405/08)")
    if (count is None) == (per_amount is None):
        raise LoanRuleError("یا تعداد اقساط یا مبلغ هر قسط را وارد کنید")
    if count is not None:
        count = int(count)
        if not (1 <= count <= MAX_INSTALLMENTS):
            raise LoanRuleError(f"تعداد اقساط باید بین ۱ و {MAX_INSTALLMENTS} باشد")
        if count > total:
            raise LoanRuleError("تعداد اقساط از مبلغ بیشتر است")
        base = total // count
        amounts = [base] * count
        amounts[-1] += total - base * count
    else:
        per_amount = int(per_amount)
        if per_amount <= 0:
            raise LoanRuleError("مبلغ هر قسط باید بیشتر از صفر باشد")
        n = -(-total // per_amount)
        if n > MAX_INSTALLMENTS:
            raise LoanRuleError(f"با این مبلغ قسط، تعداد اقساط بیش از {MAX_INSTALLMENTS} می‌شود")
        amounts = [per_amount] * n
        amounts[-1] = total - per_amount * (n - 1)
    y, m = start
    out = []
    for i, amount in enumerate(amounts, start=1):
        out.append({"seq": i, "due_month": f"{y:04d}/{m:02d}", "amount": amount})
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def normalize_date(value) -> str | None:
    """تاریخ شمسی ورودی به قالب «YYYY/MM/DD» (برای مقایسه‌ی رشته‌ای effective_from)؛ نامعتبر → None."""
    return format_jalali(parse_jalali(value))


def status_label(status: str, step: str | None, queue_position: int | None = None, out_of_queue: bool = False) -> str:
    """متن فارسی وضعیت برای پرسنل و مدیران."""
    if status == STATUS_IN_REVIEW:
        return f"در انتظار تأیید {STEP_LABELS.get(step or '', '')}".strip()
    if status == STATUS_WAITING_FINANCE:
        if out_of_queue:
            return "تأیید شد — خارج از نوبت، در انتظار پرداخت واحد مالی"
        if queue_position:
            return f"تأیید شد — در صف پرداخت (نوبت {queue_position})"
        return "تأیید شد — در صف پرداخت"
    return {
        STATUS_ACTIVE: "پرداخت شد — در حال بازپرداخت",
        STATUS_SETTLED: "تسویه شد",
        STATUS_REJECTED: "رد شد",
        STATUS_CANCELLED: "لغو شد",
    }.get(status, status)


# ---------- فیش حقوقی (تیک خودکار اقساط؛ Migration 108) ----------

_MONTH_NAMES = ("فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند")


def _to_int(value) -> int | None:
    """«۲۰,۰۰۰,۰۰۰» یا «20000000» → 20000000؛ غیرعددی → None."""
    from app.core.family_rules import to_english_digits

    text = to_english_digits(value).replace(",", "").replace("٬", "").replace("،", "").strip()
    return int(text) if text.isdigit() else None


def payslip_month(fields: list[dict]) -> str | None:
    """
    ماه فیش از ردیف‌های مشخصات (section خالی): برچسب شامل «سال» و «ماه»؛ ماه عدد یا نام فارسی.
    مثال: سال=1405، ماه=مهر → «1405/07». پیدا نشد → None.
    """
    year = month = None
    for row in fields:
        if row.get("section"):
            continue
        label = str(row.get("label") or "")
        value = str(row.get("value") or "").strip()
        if "سال" in label and year is None:
            y = _to_int(value)
            year = y if y and 1300 <= y <= 1500 else None
        elif "ماه" in label and month is None:
            m = _to_int(value)
            if m and 1 <= m <= 12:
                month = m
            else:
                month = next((i for i, n in enumerate(_MONTH_NAMES, start=1) if n in value), None)
    return f"{year:04d}/{month:02d}" if year and month else None


def payslip_loans(fields: list[dict]) -> list[dict]:
    """
    ردیف‌های بخش «وام» فیش → [{name, amount, remaining}]: مبلغ قسطی که این ماه کسر شده و مانده‌ی وام بعد از آن
    (remaining=None اگر فیش مانده نداشت). دو شکل پشتیبانی می‌شود:
    - سرستون‌دار (XML): «نام وام» / «مبلغ قسط» / «مانده» پشت سر هم برای هر وام؛
    - برچسب/مقدار (XLSX): برچسب = نام وام، مقدار = مبلغ قسط؛ ردیف «مانده…» بلافاصله بعدش مانده‌ی همان وام است
      (ردیف «جمع…» نادیده).
    """
    rows = [
        r
        for r in fields
        if "وام" in str(r.get("section") or "") and not str(r.get("section") or "").startswith("__")
    ]
    out: list[dict] = []
    has_columns = any("قسط" in str(r.get("label") or "") for r in rows)
    if has_columns:
        current: dict = {}

        def flush():
            nonlocal current
            if current:
                out.append(current)
            current = {}

        for r in rows:
            label = str(r.get("label") or "")
            value = r.get("value")
            if "نام" in label:
                if "name" in current:
                    flush()
                current["name"] = str(value or "").strip()
            elif "قسط" in label:
                if "amount" in current:
                    flush()
                current["amount"] = _to_int(value)
            elif "مانده" in label:
                if "remaining" in current:
                    flush()
                current["remaining"] = _to_int(value)
        flush()
    else:
        for r in rows:
            label = str(r.get("label") or "").strip()
            if not label or label.startswith("جمع"):
                continue
            if "مانده" in label:
                if out and out[-1].get("remaining") is None:
                    out[-1]["remaining"] = _to_int(r.get("value"))
                continue
            out.append({"name": label, "amount": _to_int(r.get("value")), "remaining": None})
    return [
        {"name": x.get("name") or "", "amount": x["amount"], "remaining": x.get("remaining")}
        for x in out
        if x.get("amount")
    ]


def match_payslip_row(rows: list[dict], taken: set[int], amount: int, remaining_after: int, title: str = "") -> int | None:
    """
    اندیس ردیف وام فیش که قسط این وام است (None = پیدا نشد). شرط: همان مبلغ قسط، نام شامل title (اگر تنظیم شده)،
    و اگر فیش «مانده» دارد باید با مانده‌ی پرتال بعد از همین قسط (remaining_after) برابر باشد — تا دو وام هم‌مبلغ
    (مثلاً وام پرتال و وام بانکی) از هم جدا شوند. ردیفِ مانده‌دارِ منطبق بر ردیف بدون مانده ترجیح دارد.
    """
    fallback = None
    for idx, row in enumerate(rows):
        if idx in taken or row["amount"] != amount or (title and title not in row["name"]):
            continue
        if row.get("remaining") is None:
            if fallback is None:
                fallback = idx
            continue
        if row["remaining"] == remaining_after:
            return idx
    return fallback
