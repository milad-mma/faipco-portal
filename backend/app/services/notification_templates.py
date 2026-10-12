"""
متن اعلان‌های (Push) ماژول‌های «کارتابل درخواست» که مدیر هر سایت از صفحه‌ی همان ماژول تغییر می‌دهد.

- TEMPLATES: همه‌ی اعلان‌ها با متن پیش‌فرض، عنوان، گیرنده، زمان ارسال و متغیرهای قابل استفاده (مثل {amount}).
- متن تغییرداده‌شده‌ی هر سایت در system_settings با کلید «notify_tpl:<ماژول>:<site_id>» (JSON {کلید: متن}) ذخیره
  می‌شود؛ کلیدی که نیست یا خالی است = متن پیش‌فرض. بدون Migration.
- render: متن نهایی؛ متغیرها با replace ساده جایگزین می‌شوند (آکولاد اشتباه در متن مدیر خطا نمی‌دهد).
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting

logger = logging.getLogger(__name__)

MAX_TEXT = 500
_VIEW = "\nجهت مشاهده روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید."
_REVIEW = "\nجهت بررسی روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید."
_DETAILS = "\nجهت مشاهده جزئیات روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید."

# module → کلید → {label, recipient, when, default, vars}
TEMPLATES: dict[str, dict[str, dict]] = {
    "leave": {
        "leave.approver_new": {
            "label": "درخواست جدید در انتظار تصمیم",
            "recipient": "تأییدکننده (سرپرست)",
            "when": "ثبت درخواست مرخصی/ماموریت",
            "default": "یک درخواست مرخصی/ماموریت در انتظار تصمیم شماست." + _REVIEW,
        },
        "leave.requester_decided": {
            "label": "نتیجه‌ی درخواست",
            "recipient": "درخواست‌دهنده",
            "when": "تأیید یا رد مرخصی/ماموریت",
            "default": "درخواست مرخصی/ماموریت شما بررسی شد.\nجهت مشاهده نتیجه روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید.",
        },
        "leave.forgotten_supervisor": {
            "label": "تردد فراموش‌شده — تأیید سرپرست",
            "recipient": "درخواست‌دهنده",
            "when": "سرپرست تردد فراموش‌شده را تأیید کرد",
            "default": "درخواست تردد فراموش‌شده شما توسط سرپرست تأیید شد و برای تأیید نهایی به منابع انسانی ارسال شد."
            + _DETAILS,
        },
        "leave.hr_forgotten_pending": {
            "label": "تردد فراموش‌شده در انتظار منابع انسانی",
            "recipient": "مسئول نیروی انسانی",
            "when": "بعد از تأیید سرپرستِ تردد فراموش‌شده",
            "default": "یک درخواست تردد فراموش‌شده (تأییدشده توسط سرپرست) در انتظار تأیید شماست." + _REVIEW,
        },
        "leave.forgotten_approved": {
            "label": "تردد فراموش‌شده — تأیید نهایی",
            "recipient": "درخواست‌دهنده",
            "when": "منابع انسانی تردد فراموش‌شده را تأیید کرد",
            "default": "درخواست تردد فراموش‌شده شما توسط منابع انسانی تأیید و در سیستم حضور و غیاب ثبت شد." + _DETAILS,
        },
        "leave.forgotten_rejected": {
            "label": "تردد فراموش‌شده — رد",
            "recipient": "درخواست‌دهنده",
            "when": "رد تردد فراموش‌شده",
            "default": "درخواست تردد فراموش‌شده شما رد شد." + _DETAILS,
        },
    },
    "loan": {
        "loan.guarantor_requested": {
            "label": "درخواست ضمانت",
            "recipient": "ضامن",
            "when": "ثبت درخواست یا انتخاب ضامن جایگزین",
            "default": "یک همکار شما را ضامن درخواست وام خود کرده است." + _VIEW,
        },
        "loan.guarantor_declined": {
            "label": "ضامن نپذیرفت",
            "recipient": "درخواست‌دهنده",
            "when": "یکی از ضامن‌ها ضمانت را نپذیرفت",
            "default": "{guarantor} ضمانت وام شما را نپذیرفت؛ ضامن دیگری انتخاب کنید." + _VIEW,
            "vars": {"guarantor": "نام ضامن"},
        },
        "loan.approver_pending": {
            "label": "در انتظار تأیید مدیر",
            "recipient": "مدیر واحد / مدیر سایت",
            "when": "نوبت تأیید به او رسید",
            "default": "یک درخواست وام در انتظار تصمیم شماست." + _VIEW,
        },
        "loan.to_finance_queue": {
            "label": "رفتن به صف پرداخت",
            "recipient": "درخواست‌دهنده",
            "when": "همه تأیید کردند",
            "default": "درخواست وام شما تأیید شد و به صف پرداخت واحد مالی رفت." + _VIEW,
        },
        "loan.rejected": {
            "label": "رد درخواست",
            "recipient": "درخواست‌دهنده",
            "when": "رد توسط مدیر واحد، مدیر سایت یا واحد مالی",
            "default": "درخواست وام شما رد شد." + _VIEW,
        },
        "loan.paid": {
            "label": "پرداخت وام",
            "recipient": "درخواست‌دهنده",
            "when": "واحد مالی پرداخت و اقساط را ثبت کرد",
            "default": "وام شما به مبلغ {amount} ریال پرداخت شد؛ جدول اقساط در پرتال است." + _VIEW,
            "vars": {"amount": "مبلغ پرداختی (ریال)"},
        },
        "loan.settled": {
            "label": "تسویه‌ی وام",
            "recipient": "درخواست‌دهنده",
            "when": "آخرین قسط پرداخت شد یا تسویه‌ی یکجا",
            "default": "وام شما تسویه شد." + _VIEW,
        },
    },
}


def _module_of(key: str) -> str:
    return key.split(".", 1)[0]


def _setting_key(module: str, site_id: int) -> str:
    return f"notify_tpl:{module}:{site_id}"


async def _overrides(db: AsyncSession, module: str, site_id: int | None) -> dict[str, str]:
    if site_id is None:
        return {}
    row = (
        await db.execute(select(SystemSetting).where(SystemSetting.key == _setting_key(module, site_id)))
    ).scalar_one_or_none()
    if row is None:
        return {}
    try:
        data = json.loads(row.value)
        return {k: v for k, v in data.items() if isinstance(v, str) and v.strip()} if isinstance(data, dict) else {}
    except ValueError:
        return {}


def _fill(text: str, values: dict) -> str:
    for name, value in values.items():
        text = text.replace("{" + name + "}", str(value))
    return text


async def render(db: AsyncSession, site_id: int | None, key: str, **values) -> str:
    """متن نهایی اعلان key برای سایت (متن سایت، وگرنه پیش‌فرض) با جایگزینی متغیرها. هیچ‌وقت خطا نمی‌دهد."""
    module = _module_of(key)
    default = TEMPLATES[module][key]["default"]
    try:
        text = (await _overrides(db, module, site_id)).get(key) or default
    except Exception:  # noqa: BLE001 - اعلان نباید به‌خاطر خواندن تنظیمات از دست برود
        logger.exception("خواندن متن اعلان سفارشی ناموفق بود")
        text = default
    return _fill(text, values)


async def list_templates(db: AsyncSession, module: str, site_id: int) -> list[dict]:
    overrides = await _overrides(db, module, site_id)
    return [
        {
            "key": key,
            "label": t["label"],
            "recipient": t["recipient"],
            "when": t["when"],
            "default": t["default"],
            "text": overrides.get(key) or t["default"],
            "customized": key in overrides,
            "vars": t.get("vars", {}),
        }
        for key, t in TEMPLATES[module].items()
    ]


async def save_templates(db: AsyncSession, module: str, site_id: int, texts: dict[str, str | None]) -> list[dict]:
    """texts: {کلید: متن}؛ متن خالی یا برابر پیش‌فرض = برگشت به پیش‌فرض. کلید ناشناخته نادیده گرفته می‌شود."""
    known = TEMPLATES[module]
    current = await _overrides(db, module, site_id)
    for key, text in texts.items():
        if key not in known:
            continue
        value = (text or "").strip()[:MAX_TEXT]
        if not value or value == known[key]["default"]:
            current.pop(key, None)
        else:
            current[key] = value
    skey = _setting_key(module, site_id)
    row = (await db.execute(select(SystemSetting).where(SystemSetting.key == skey))).scalar_one_or_none()
    if current:
        payload = json.dumps(current, ensure_ascii=False)
        if row is None:
            db.add(SystemSetting(key=skey, value=payload))
        else:
            row.value = payload
    elif row is not None:
        await db.delete(row)
    await db.commit()
    return await list_templates(db, module, site_id)
