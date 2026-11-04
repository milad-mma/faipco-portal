"""
قواعد خالص «انتقال کارهای باز» (سند مرجع ۴.۳):
- همه‌ی taskهای open فرد قبلی (عادی و محرمانه) منتقل می‌شوند، جز:
  اگر جایگزین خودِ انجام‌دهنده باشد، taskهای محرمانه‌ی نامه‌هایی که او قبلاً به آن‌ها دسترسی نداشته (جلوگیری از دورزدن).
- گزارش قابل نمایش فقط موارد غیرمحرمانه؛ درباره‌ی محرمانه فقط عبارت ثابت، بدون تعداد/موضوع/طرفین.
"""
from __future__ import annotations

CONFIDENTIAL_MOVED_NOTE = "کارهای محرمانه، در صورت وجود، نیز منتقل شدند."
CONFIDENTIAL_SELF_NOTE = "کارهای محرمانه به خودتان قابل انتقال نیست؛ در صورت وجود باقی مانده‌اند."


class TransferRulesError(ValueError):
    """خطای قابل نمایش."""


def check_request(from_id: int, to_id: int, reason: str | None) -> str:
    if not from_id or not to_id:
        raise TransferRulesError("فرد قبلی و جایگزین را انتخاب کنید")
    if from_id == to_id:
        raise TransferRulesError("جایگزین نمی‌تواند همان فرد قبلی باشد")
    reason = (reason or "").strip()
    if not reason:
        raise TransferRulesError("دلیل انتقال را بنویسید")
    return reason[:2000]


def plan(tasks: list[dict], *, performer_id: int | None, to_id: int, prior_access: set[int]) -> dict:
    """
    tasks: [{id, letter_id, confidential, subject, number, kind}]؛ prior_access: نامه‌هایی که انجام‌دهنده از قبل به آن‌ها
    دسترسی داشته. خروجی: {move: [task ids], visible: [غیرمحرمانه‌های منتقل‌شونده], note: عبارت ثابت محرمانه}
    """
    self_transfer = performer_id is not None and performer_id == to_id
    move, visible = [], []
    for t in tasks:
        if t["confidential"] and self_transfer and t["letter_id"] not in prior_access:
            continue
        move.append(t["id"])
        if not t["confidential"]:
            visible.append({"letter_id": t["letter_id"], "subject": t["subject"], "number": t.get("number"), "kind": t.get("kind")})
    return {"move": move, "visible": visible, "note": CONFIDENTIAL_SELF_NOTE if self_transfer else CONFIDENTIAL_MOVED_NOTE}
