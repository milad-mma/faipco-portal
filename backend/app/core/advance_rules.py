"""
قواعد خالص (بدون دیتابیس) ماژول «درخواست مساعده» — docs/advances.md.

- مبلغ: پلکانی با مبلغ ثابت؛ پرسنل مبلغ بالاترین پله‌ای را می‌گیرد که سابقه‌اش (ماه کامل) به min_months آن می‌رسد.
  اگر به هیچ پله‌ای نرسد، نمی‌تواند درخواست بدهد.
- گروه: پرسنل (staff) / سرپرستان (supervisor) / مدیران (manager)؛ هر گروه پله‌های خودش را دارد و گروه بدون پله از
  پله‌های «پرسنل» استفاده می‌کند. سرپرست = تأییدکننده‌ی مرخصی (خودکار) یا تعیین دستی؛ مدیر فقط با تعیین دستی.
- بازه‌ی ثبت: روزهای مجاز هر ماه شمسی [from, to] شامل دو سر؛ from > to یعنی بازه از آخر ماه به اول ماه بعد می‌چرخد
  (مثلاً ۲۵ تا ۵). «ماه درخواست» همیشه ماه شمسی روز ثبت است.
- دفعات: حداکثر max_per_month درخواست در ماه (رد/لغوشده‌ها حساب نمی‌شوند).
- مسیر: مدیر واحد ← مدیر سایت ← واحد مالی (مرحله‌ی کسی که خودِ درخواست‌دهنده است حذف می‌شود؛ اگر مدیر واحد و مدیر
  سایت یک نفر باشند یک بار تأیید می‌کند). مالی اول «تأیید» و بعد جداگانه «ثبت پرداخت» می‌کند.
"""
from __future__ import annotations

from app.core.family_rules import parse_jalali
from app.core.loan_rules import months_between  # noqa: F401 - سابقه با همان قاعده‌ی وام

STEP_UNIT_MANAGER = "unit_manager"
STEP_SITE_MANAGER = "site_manager"
STEP_FINANCE = "finance"
STEP_LABELS = {STEP_UNIT_MANAGER: "مدیر واحد", STEP_SITE_MANAGER: "مدیر سایت", STEP_FINANCE: "واحد مالی"}
ALL_STEPS = [STEP_UNIT_MANAGER, STEP_SITE_MANAGER, STEP_FINANCE]

STATUS_IN_REVIEW = "in_review"  # در انتظار مدیر واحد یا مدیر سایت
STATUS_WAITING_FINANCE = "waiting_finance"  # در انتظار تأیید واحد مالی
STATUS_APPROVED = "approved"  # مالی تأیید کرده، در انتظار ثبت پرداخت
STATUS_PAID = "paid"
STATUS_REJECTED = "rejected"
STATUS_CANCELLED = "cancelled"
OPEN_STATUSES = (STATUS_IN_REVIEW, STATUS_WAITING_FINANCE, STATUS_APPROVED)
COUNTED_STATUSES = (STATUS_IN_REVIEW, STATUS_WAITING_FINANCE, STATUS_APPROVED, STATUS_PAID)  # در «دفعات ماه» شمرده می‌شوند
STATUS_LABELS = {
    STATUS_APPROVED: "تأیید شد — در انتظار پرداخت",
    STATUS_PAID: "پرداخت شد",
    STATUS_REJECTED: "رد شد",
    STATUS_CANCELLED: "لغو شد",
}

GROUP_STAFF = "staff"
GROUP_SUPERVISOR = "supervisor"
GROUP_MANAGER = "manager"
GROUPS = (GROUP_STAFF, GROUP_SUPERVISOR, GROUP_MANAGER)
GROUP_LABELS = {GROUP_STAFF: "پرسنل", GROUP_SUPERVISOR: "سرپرستان", GROUP_MANAGER: "مدیران"}

MAX_AMOUNT = 10**15


class AdvanceRuleError(ValueError):
    """خطای قابل نمایش به کاربر (متن فارسی)."""


def tier_amount(months: int | None, tiers: list[dict]) -> int | None:
    """
    مبلغ ثابت مساعده برای این سابقه: بالاترین پله‌ای که min_months آن ≤ months است.
    tiers: [{"min_months": int, "amount": int}, ...] با هر ترتیبی. سابقه‌ی نامشخص یا بدون پله‌ی مناسب → None.
    """
    if months is None:
        return None
    best = None
    for tier in tiers:
        try:
            need, amount = int(tier["min_months"]), int(tier["amount"])
        except (KeyError, TypeError, ValueError):
            continue
        if need <= months and (best is None or need > best[0]):
            best = (need, amount)
    return best[1] if best else None


def group_tiers(tiers: list[dict], group: str) -> list[dict]:
    """پله‌های یک گروه؛ اگر برای آن گروه پله‌ای تعریف نشده، پله‌های «پرسنل»."""
    own = [t for t in tiers if t.get("group", GROUP_STAFF) == group]
    if own or group == GROUP_STAFF:
        return own
    return [t for t in tiers if t.get("group", GROUP_STAFF) == GROUP_STAFF]


def validate_tiers(tiers) -> list[dict]:
    """پله‌ها را تمیز می‌کند: گروه معتبر، ماه ≥ ۰، مبلغ > ۰، بدون ماه تکراری در هر گروه، مرتب بر اساس گروه و ماه."""
    if not isinstance(tiers, (list, tuple)):
        raise AdvanceRuleError("فهرست پله‌ها نامعتبر است")
    out: dict[tuple[str, int], int] = {}
    for tier in tiers:
        try:
            group = str(tier.get("group") or GROUP_STAFF)
            months = int(tier.get("min_months"))
            amount = int(tier.get("amount"))
        except (AttributeError, TypeError, ValueError) as e:
            raise AdvanceRuleError("هر پله باید «حداقل سابقه (ماه)» و «مبلغ» عددی داشته باشد") from e
        if group not in GROUPS:
            raise AdvanceRuleError("گروه پله نامعتبر است")
        if months < 0:
            raise AdvanceRuleError("حداقل سابقه نمی‌تواند منفی باشد")
        if amount <= 0 or amount > MAX_AMOUNT:
            raise AdvanceRuleError("مبلغ پله باید بزرگ‌تر از صفر باشد")
        if (group, months) in out:
            raise AdvanceRuleError(f"پله‌ی «{months} ماه» در گروه «{GROUP_LABELS[group]}» دو بار تعریف شده است")
        out[(group, months)] = amount
    order = {g: i for i, g in enumerate(GROUPS)}
    return [
        {"group": g, "min_months": m, "amount": a}
        for (g, m), a in sorted(out.items(), key=lambda kv: (order[kv[0][0]], kv[0][1]))
    ]


def validate_window(from_day, to_day, max_per_month) -> tuple[int, int, int]:
    """بازه‌ی روزهای ۱..۳۱ و حداکثر دفعات ≥ ۱ را بررسی می‌کند."""
    try:
        f, t, n = int(from_day), int(to_day), int(max_per_month)
    except (TypeError, ValueError) as e:
        raise AdvanceRuleError("روزهای بازه و تعداد دفعات باید عدد باشند") from e
    if not (1 <= f <= 31 and 1 <= t <= 31):
        raise AdvanceRuleError("روزهای بازه باید بین ۱ و ۳۱ باشند")
    if n < 1:
        raise AdvanceRuleError("حداکثر دفعات در ماه باید دست‌کم ۱ باشد")
    return f, t, n


def in_window(day: int, from_day: int, to_day: int) -> bool:
    """آیا روز day (۱..۳۱) داخل بازه‌ی مجاز است؟ from > to یعنی بازه از آخر ماه می‌چرخد (۲۵ تا ۵)."""
    if from_day <= to_day:
        return from_day <= day <= to_day
    return day >= from_day or day <= to_day


def window_label(from_day: int, to_day: int) -> str:
    """«از ۵ تا ۱۵ هر ماه» / «همه‌ی روزهای ماه»."""
    if from_day == 1 and to_day == 31:
        return "همه‌ی روزهای ماه"
    if from_day > to_day:
        return f"از {from_day}ام هر ماه تا {to_day}ام ماه بعد"
    return f"از {from_day}ام تا {to_day}ام هر ماه"


def month_key(today) -> str:
    """تاریخ شمسی (رشته یا تاپل) → «YYYY/MM»."""
    t = today if isinstance(today, tuple) else parse_jalali(today)
    if not t:
        raise AdvanceRuleError("تاریخ نامعتبر است")
    return f"{t[0]:04d}/{t[1]:02d}"


def request_month(today: tuple, from_day: int, to_day: int) -> str:
    """
    «ماه درخواست» برای شمارش دفعات: در بازه‌ی چرخان (مثلاً ۲۵ تا ۵)، روزهای اول ماه بعد به همان بازه‌ی ماه قبل تعلق
    دارند (۲ مهر در بازه‌ی «۲۵ شهریور تا ۵ مهر» → ماه شهریور)؛ وگرنه ماه خودِ تاریخ.
    """
    y, m, d = today
    if from_day > to_day and d <= to_day:
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return f"{y:04d}/{m:02d}"


def effective_steps(*, requester_id: int, unit_manager_id: int | None, site_manager_id: int | None) -> list[str]:
    """
    مسیر واقعی یک درخواست: مدیر واحد ← مدیر سایت ← مالی؛ مرحله‌ی کسی که خودِ درخواست‌دهنده است حذف می‌شود
    و اگر مدیر واحد و مدیر سایت یک نفر باشند فقط مدیر واحد می‌ماند.
    """
    out: list[str] = []
    if unit_manager_id is not None and unit_manager_id != requester_id:
        out.append(STEP_UNIT_MANAGER)
    if site_manager_id is not None and site_manager_id != requester_id and site_manager_id != unit_manager_id:
        out.append(STEP_SITE_MANAGER)
    out.append(STEP_FINANCE)
    return out


def status_label(status: str, step: str | None) -> str:
    """متن فارسی وضعیت برای پرسنل و مدیران."""
    if status == STATUS_IN_REVIEW:
        return f"در انتظار تأیید {STEP_LABELS.get(step or '', '')}".strip()
    if status == STATUS_WAITING_FINANCE:
        return "در انتظار تأیید واحد مالی"
    return STATUS_LABELS.get(status, status)
