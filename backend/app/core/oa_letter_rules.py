"""
قواعد خالص نامه و قالب — فاز ۲ (docs/office-automation-spec.md بخش ۳.۲، ۳.۵، ۶.۲، ۸.۲؛ docs/office-automation.md).
"""
from __future__ import annotations

import hashlib
import json

PAPER_SIZES = {"A4": (210, 297), "A5": (148, 210)}  # میلی‌متر (عرض، ارتفاع) — چیدمان مستقل، نه scale
URGENCIES = {"normal": "عادی", "urgent": "فوری", "immediate": "آنی"}
CONFIDENTIALITY = {"normal": "عادی", "confidential": "محرمانه"}
MAX_SUBJECT = 300


class LetterRulesError(ValueError):
    """خطای قابل نمایش (پیام فارسی)."""


def default_layout(size: str) -> dict:
    a5 = size == "A5"
    return {
        "margins_mm": {"top": 12 if a5 else 15, "right": 14 if a5 else 20, "bottom": 12 if a5 else 15,
                       "left": 14 if a5 else 20},
        "font_size_pt": 11 if a5 else 12,
        "header": {
            "logo_file_id": None,
            "title": "",
            "subtitle": "",
            "show_number": True,
            "show_date": True,
            "show_attachment": True,
            "height_mm": 28 if a5 else 35,
        },
        "footer": {"text": "", "height_mm": 10 if a5 else 12},
        "signature": {"align": "left"},
    }


def default_layouts() -> dict:
    return {size: default_layout(size) for size in PAPER_SIZES}


def _int(v, lo, hi, label):
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise LetterRulesError(f"{label} باید عدد صحیح باشد") from None
    if not lo <= n <= hi:
        raise LetterRulesError(f"{label} باید بین {lo} و {hi} باشد")
    return n


def _text(v, limit, label) -> str:
    s = "" if v is None else str(v)
    s = "".join(ch for ch in s if ch == "\n" or ch >= " ").strip()
    if len(s) > limit:
        raise LetterRulesError(f"{label} حداکثر {limit} نویسه است")
    return s


def validate_layout(size: str, raw: dict) -> dict:
    """چیدمان یک اندازه‌ی کاغذ را بررسی و نرمال می‌کند (فقط کلیدهای شناخته‌شده می‌مانند)."""
    if size not in PAPER_SIZES:
        raise LetterRulesError("اندازه‌ی کاغذ نامعتبر است")
    if not isinstance(raw, dict):
        raise LetterRulesError("چیدمان قالب نامعتبر است")
    d = default_layout(size)
    m = raw.get("margins_mm") or {}
    h = raw.get("header") or {}
    f = raw.get("footer") or {}
    sig = raw.get("signature") or {}
    w, ht = PAPER_SIZES[size]
    out = {
        "margins_mm": {k: _int(m.get(k, d["margins_mm"][k]), 5, 60, f"حاشیه‌ی {lbl}")
                       for k, lbl in (("top", "بالا"), ("right", "راست"), ("bottom", "پایین"), ("left", "چپ"))},
        "font_size_pt": _int(raw.get("font_size_pt", d["font_size_pt"]), 8, 18, "اندازه‌ی قلم"),
        "header": {
            "logo_file_id": (int(h["logo_file_id"]) if h.get("logo_file_id") not in (None, "", 0) else None),
            "title": _text(h.get("title"), 120, "عنوان سربرگ"),
            "subtitle": _text(h.get("subtitle"), 200, "زیرعنوان سربرگ"),
            "show_number": bool(h.get("show_number", True)),
            "show_date": bool(h.get("show_date", True)),
            "show_attachment": bool(h.get("show_attachment", True)),
            "height_mm": _int(h.get("height_mm", d["header"]["height_mm"]), 10, 90, "ارتفاع سربرگ"),
        },
        "footer": {
            "text": _text(f.get("text"), 300, "متن پابرگ"),
            "height_mm": _int(f.get("height_mm", d["footer"]["height_mm"]), 0, 40, "ارتفاع پابرگ"),
        },
        "signature": {"align": sig.get("align") if sig.get("align") in ("left", "center", "right") else "left"},
    }
    mm = out["margins_mm"]
    if mm["left"] + mm["right"] > w - 60:
        raise LetterRulesError("مجموع حاشیه‌های چپ و راست برای این اندازه‌ی کاغذ زیاد است")
    if mm["top"] + mm["bottom"] + out["header"]["height_mm"] + out["footer"]["height_mm"] > ht - 60:
        raise LetterRulesError("سربرگ، پابرگ و حاشیه‌ها جای کافی برای متن نامه نمی‌گذارند")
    return out


def validate_layouts(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise LetterRulesError("چیدمان قالب نامعتبر است")
    return {size: validate_layout(size, raw.get(size) or {}) for size in PAPER_SIZES}


def body_area_mm(size: str, layout: dict) -> tuple[float, float]:
    """عرض و ارتفاع ناحیه‌ی متن یک صفحه (برای شمارش صفحه در پیش‌نمایش)."""
    w, h = PAPER_SIZES[size]
    m = layout["margins_mm"]
    return (w - m["left"] - m["right"],
            h - m["top"] - m["bottom"] - layout["header"]["height_mm"] - layout["footer"]["height_mm"])


def clean_subject(subject: str | None) -> str:
    s = _text(subject, MAX_SUBJECT, "موضوع").replace("\n", " ")
    return s


def content_hash(*, subject: str, body_html: str, paper_size: str, template_version_id: int | None,
                 recipients: list | None = None, attachments: list | None = None) -> str:
    """
    SHA-256 محتوای مؤثر یک نسخه (بخش ۳.۲): موضوع، متن، اندازه، نسخه‌ی قالب، گیرندگان رسمی و فهرست مرتب پیوست‌ها.
    هر تغییر در این‌ها یعنی «تغییر مؤثر» و تأیید دوباره (از فاز ۳ب).
    """
    payload = {
        "subject": subject or "",
        "body_html": body_html or "",
        "paper_size": paper_size,
        "template_version_id": template_version_id,
        "recipients": sorted(recipients or []),
        "attachments": list(attachments or []),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
