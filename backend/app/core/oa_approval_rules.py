"""
قواعد خالص گردش تأیید ترتیبی (فاز ۳ب، سند مرجع ۳.۴ و ۶.۴؛ تصمیم ۱۴۰۵/۰۸/۱۲):
- نویسنده (یا منشی) پیش از ارسال، مسیر را به ترتیب تعیین می‌کند: هر مرحله یک شخص و یک نوع (پاراف / تأیید / امضا).
- مراحل یکی‌یکی فعال می‌شوند؛ هر کس فقط نوبت خودش را می‌بیند و اقدام می‌کند.
- «برگشت برای اصلاح» با توضیح اجباری نامه را به پیش‌نویس برمی‌گرداند؛ ارسال دوباره دور تازه‌ای از تأیید است.
- با تأیید آخرین مرحله نامه خودکار شماره می‌گیرد و ارسال می‌شود.
- نامه‌ای که منشی «از طرف» مدیر می‌نویسد: مرحله‌ی آخر همیشه «امضا»ی خود مدیر است (حذف‌شدنی نیست).
"""
from __future__ import annotations

KINDS = {"paraph": "پاراف", "approve": "تأیید", "sign": "امضا"}
ACTION_LABELS = {"paraph": "پاراف", "approve": "تأیید", "sign": "تأیید و امضا"}
MAX_STEPS = 10
APPROVAL_TASK_KINDS = tuple(KINDS)


class ApprovalRulesError(ValueError):
    """خطای قابل نمایش."""


def clean_plan(steps: list[dict], *, author_id: int, principal_id: int | None) -> list[dict]:
    """
    ورودی: [{employee_id, kind}] به ترتیب. خروجی: مسیر پاک‌شده‌ی صریح (بدون مرحله‌ی خودکار مدیر).
    قواعد: حداکثر ۱۰ مرحله، هر شخص یک بار، نویسنده در مسیر نیست، مدیرِ «از طرف» فقط در مرحله‌ی خودکار آخر.
    """
    out: list[dict] = []
    seen: set[int] = set()
    for s in steps or []:
        try:
            eid = int(s.get("employee_id") or 0)
        except (TypeError, ValueError):
            eid = 0
        kind = s.get("kind")
        if not eid:
            raise ApprovalRulesError("شخص یکی از مراحل تأیید مشخص نیست")
        if kind not in KINDS:
            raise ApprovalRulesError("نوع مرحله‌ی تأیید نامعتبر است")
        if eid == author_id:
            raise ApprovalRulesError("نویسنده‌ی نامه نمی‌تواند در مسیر تأیید نامه‌ی خودش باشد")
        if principal_id and eid == principal_id:
            continue  # مرحله‌ی امضای مدیر خودکار و همیشه آخر است
        if eid in seen:
            raise ApprovalRulesError("هر شخص فقط یک بار در مسیر تأیید می‌آید")
        seen.add(eid)
        out.append({"employee_id": eid, "kind": kind})
    if len(out) + (1 if principal_id else 0) > MAX_STEPS:
        raise ApprovalRulesError(f"حداکثر {MAX_STEPS} مرحله‌ی تأیید")
    return out


def effective_plan(explicit: list[dict], principal_id: int | None) -> list[dict]:
    """مسیر نهایی: مراحل صریح + «امضا»ی خودکار مدیر در آخر (برای نامه‌ی «از طرف»)."""
    plan = [{**s, "required": False} for s in explicit]
    if principal_id:
        plan.append({"employee_id": principal_id, "kind": "sign", "required": True})
    return plan


def next_index(statuses: list[str]) -> int | None:
    """اولین مرحله‌ای که هنوز تأیید نشده (pending)؛ None یعنی همه تأیید شده‌اند."""
    for i, st in enumerate(statuses):
        if st != "approved":
            return i if st == "pending" else None
    return None


def check_return_note(note: str | None) -> str:
    note = (note or "").strip()
    if not note:
        raise ApprovalRulesError("برای برگشت برای اصلاح، توضیح بنویسید")
    return note[:2000]
