"""
قاعده‌ی متمرکز دسترسی محتوایی به نامه — `can()` (docs/office-automation-spec.md بخش ۵.۲، فاز ۳الف).

دسترسی فقط از ردیف‌های صریح oa_letter_access همان شخص می‌آید (ایجادکننده، فرستنده، گیرنده، رونوشت، گیرنده‌ی ارجاع). هیچ
مجوز ماژول، نقش سازمانی یا ادمین بودن ردیفی نمی‌سازد و استثنایی ندارد؛ برای نامه‌ی محرمانه هم همین است.
تابع خالص است تا بدون دیتابیس تست شود.
"""
from __future__ import annotations

SOURCES = ("creator", "sender", "recipient", "cc", "referral")
ACTIONS = ("view", "download", "print", "manage", "refer", "act", "note", "make_confidential")
SENT_STATUSES = ("dispatched", "closed")


def can(action: str, *, letter: dict, rows: list[dict], open_task: bool = False) -> bool:
    """
    letter: {"status", "confidentiality"}؛ rows: ردیف‌های oa_letter_access همین شخص روی همین نامه
    ({"source", "can_act", "can_refer", "revoked_at"})؛ open_task: آیا مسئولیت باز (اقدام/اطلاع) روی این نامه دارد.
    """
    if action not in ACTIONS:
        raise ValueError(f"اقدام ناشناخته: {action}")
    active = [r for r in rows if not r.get("revoked_at")]
    if not active:
        return False
    sources = {r["source"] for r in active}
    sent = letter.get("status") in SENT_STATUSES
    if action in ("view", "download", "print"):
        return True
    if action == "manage":
        return letter.get("status") == "draft" and "creator" in sources
    if action == "refer":
        return sent and any(r.get("can_refer") for r in active)
    if action == "act":
        return sent and open_task
    if action == "note":
        return sent
    if action == "make_confidential":
        return sent and letter.get("confidentiality") == "normal" and bool(sources & {"creator", "sender"})
    return False


def delivery_grants(role: str) -> dict:
    """ردیف دسترسی و مسئولیت تحویل برای گیرنده: اصلی → اقدام + اجازه‌ی ارجاع؛ رونوشت → فقط مشاهده، بدون مسئولیت."""
    if role == "to":
        return {"source": "recipient", "can_act": True, "can_refer": True, "task_kind": "action"}
    if role == "cc":
        return {"source": "cc", "can_act": False, "can_refer": False, "task_kind": None}
    raise ValueError("نقش گیرنده نامعتبر است")


def referral_grants(kind: str, allow_refer: bool) -> dict:
    """ارجاع: اقدام → can_act؛ اطلاع → فقط «اعلام رؤیت». اجازه‌ی ارجاع دوباره فقط اگر ارجاع‌دهنده بدهد."""
    if kind not in ("action", "info"):
        raise ValueError("نوع ارجاع نامعتبر است")
    return {"source": "referral", "can_act": kind == "action", "can_refer": bool(allow_refer), "task_kind": kind}


def push_text_key(event: str, confidential: bool) -> str:
    """کلید قالب اعلان؛ نامه‌ی محرمانه فقط متن کلی (بدون موضوع/فرستنده)."""
    return "automation.confidential" if confidential else f"automation.{event}"
