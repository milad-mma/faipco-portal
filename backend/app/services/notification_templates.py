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
MAX_TITLE = 200
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
            "recipient": "مدیر واحد / منابع انسانی / مدیر سایت",
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
    "notices": {
        "notices.new": {
            "label": "اطلاعیه‌ی جدید",
            "recipient": "مخاطبان اطلاعیه",
            "when": "انتشار اطلاعیه (و «ارسال دوباره‌ی اعلان»)، از جمله تبریک تولد و اطلاعیه‌های خودکار ماژول‌ها",
            "default": "یک اطلاعیه جدید برای شما ارسال شده است." + _VIEW,
        },
        "notices.payroll": {
            "label": "فیش حقوقی",
            "recipient": "پرسنل دارای فیش",
            "when": "بارگذاری فیش حقوقی توسط حسابداری",
            "default": "یک اطلاعیه جدید برای شما ارسال شده است." + _VIEW,
        },
        "notices.attendance_card": {
            "label": "فیش کارکرد",
            "recipient": "پرسنل دارای فیش کارکرد",
            "when": "بارگذاری فیش کارکرد توسط منابع انسانی",
            "default": "یک اطلاعیه جدید برای شما ارسال شده است." + _VIEW,
        },
    },
    "evaluation": {
        "evaluation.reminder": {
            "label": "یادآوری ارزیابی انجام‌نشده",
            "recipient": "ارزیاب",
            "when": "یادآوری خودکار نزدیک پایان مهلت دوره",
            "default": "{count} ارزیابی عملکرد انجام‌نشده دارید و مهلت آن رو به پایان است.\nجهت تکمیل روی این پیام بزنید و یا به پرتال سازمانی مراجعه نمائید.",
            "vars": {"count": "تعداد ارزیابی‌های انجام‌نشده"},
        },
        "evaluation.result": {
            "label": "ثبت نتیجه‌ی ارزیابی",
            "recipient": "ارزیابی‌شونده",
            "when": "ثبت نتیجه‌ی ارزیابی عملکرد",
            "default": "نتیجه ارزیابی عملکرد شما ثبت شد." + _VIEW,
        },
    },
    "birthday": {
        "birthday.greeting_title": {
            "label": "عنوان اطلاعیه‌ی خودکار تبریک تولد",
            "recipient": "متولد امروز",
            "when": "ارسال خودکار روزانه‌ی پیام تبریک (متن پیام از «پیام‌های تبریک تولد» انتخاب می‌شود)",
            "default": "تولدت مبارک! 🎉",
        },
        "birthday.reaction": {
            "label": "تبریک همکاران",
            "recipient": "متولد امروز",
            "when": "همکاری روی کارت «متولدین امروز» تبریک گفت",
            "default": "همکارانتان تولد شما را تبریک گفتند." + _VIEW,
        },
        "birthday.reaction_summary": {
            "label": "جمع‌بندی تبریک‌های روز",
            "recipient": "متولد امروز",
            "when": "جمع‌بندی خودکار پایان روز",
            "default": "امروز {count} نفر از همکارانتان تولد شما را تبریک {verb}." + _VIEW,
            "vars": {"count": "تعداد تبریک‌ها", "verb": "«گفت» یا «گفتند»"},
        },
    },
    "feedback": {
        "feedback.new_message": {
            "label": "پیام جدید انتقادات و پیشنهادات",
            "recipient": "بازبین‌ها",
            "when": "ثبت پیام جدید",
            "default": "پیام جدیدی در انتقادات و پیشنهادات ثبت شده است." + _VIEW,
        },
        "feedback.follow_up": {
            "label": "پاسخ فرستنده در گفتگو",
            "recipient": "بازبین‌ها",
            "when": "فرستنده در یک گفتگوی موجود پاسخ داد",
            "default": "پاسخ جدیدی از فرستنده در یکی از گفتگوهای انتقادات و پیشنهادات ثبت شده است." + _VIEW,
        },
        "feedback.reply": {
            "label": "پاسخ به پیام",
            "recipient": "فرستنده‌ی پیام",
            "when": "ثبت پاسخ بازبین",
            "default": "پاسخی به پیام شما در انتقادات و پیشنهادات ثبت شد.\nبرای مشاهده روی این پیام بزنید.",
        },
    },
    "login_security": {
        "login_security.alert": {
            "label": "هشدار تلاش‌های ناموفق ورود",
            "recipient": "گیرندگان هشدار امنیت ورود",
            "when": "تعداد تلاش ناموفق از آستانه گذشت",
            "default": "هشدار امنیتی: {count} تلاش ناموفق ورود در {minutes} دقیقه‌ی اخیر. گزارش امنیت ورود را بررسی کنید.",
            "vars": {"count": "تعداد تلاش ناموفق", "minutes": "بازه (دقیقه)"},
        },
    },
    "family": {
        "family.approved_title": {
            "label": "عنوان اطلاعیه‌ی تأیید",
            "recipient": "پرسنل",
            "when": "منابع انسانی مشخصات خانوادگی را تأیید کرد (اطلاعیه‌ی خودکار)",
            "default": "مشخصات خانوادگی تأیید شد",
        },
        "family.approved_body": {
            "label": "متن اطلاعیه‌ی تأیید",
            "recipient": "پرسنل",
            "when": "منابع انسانی مشخصات خانوادگی را تأیید کرد (اطلاعیه‌ی خودکار)",
            "default": "مشخصات خانوادگی شما توسط واحد منابع انسانی تأیید شد (تاریخ اثر: {effective_date}).\n{note}",
            "vars": {"effective_date": "تاریخ اثر", "note": "توضیح منابع انسانی (اگر نوشته شده)"},
        },
        "family.rejected_title": {
            "label": "عنوان اطلاعیه‌ی رد",
            "recipient": "پرسنل",
            "when": "منابع انسانی مشخصات خانوادگی را رد کرد (اطلاعیه‌ی خودکار)",
            "default": "مشخصات خانوادگی تأیید نشد",
        },
        "family.returned_title": {
            "label": "عنوان اطلاعیه‌ی بازگشت برای ویرایش",
            "recipient": "پرسنل",
            "when": "منابع انسانی فرم را برای ویرایش برگرداند (اطلاعیه‌ی خودکار)",
            "default": "مشخصات خانوادگی نیاز به ویرایش دارد",
        },
        "family.reject_body": {
            "label": "متن اطلاعیه‌ی رد / بازگشت برای ویرایش",
            "recipient": "پرسنل",
            "when": "رد یا بازگشت برای ویرایش (اطلاعیه‌ی خودکار)",
            "default": "{note}\nلطفاً از پنل کاربری، بخش «مشخصات خانوادگی»، فرم را اصلاح و دوباره ثبت کنید.",
            "vars": {"note": "دلیل منابع انسانی"},
        },
    },
}


def _module_of(key: str) -> str:
    return key.split(".", 1)[0]


def _setting_key(module: str, site_id: int | None) -> str:
    """site_id=None: متن سراسری (ماژول‌هایی که به سایت وابسته نیستند)."""
    return f"notify_tpl:{module}:{site_id if site_id is not None else 'global'}"

# ماژول‌های سراسری (یک متن برای همه‌ی سایت‌ها) و مجوز لازم برای ویرایش متن‌شان (سراسری)
GLOBAL_MODULES = {
    "notices": "system.settings",
    "evaluation": "performance.periods.manage",
    "birthday": "hr.birthday_messages",
    "feedback": "feedback.reply",
    "login_security": "system.login_security",
    "family": "family.manage",
}


async def _overrides(db: AsyncSession, module: str, site_id: int | None) -> dict[str, str]:
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


class TemplateError(ValueError):
    """متن نامعتبر (مثلاً طولانی‌تر از سقف)؛ پیام فارسی برای کاربر."""


def max_len(key: str) -> int:
    """عنوان اطلاعیه (کلیدهای *_title) کوتاه‌تر از متن اعلان است."""
    return MAX_TITLE if key.endswith("_title") else MAX_TEXT


async def get_text(site_id: int | None, key: str) -> str:
    """
    متن خام قالب key (متن سایت/سراسری، وگرنه پیش‌فرض) — بدون جایگزینی متغیرها. با Session جدا و کوتاه‌عمر خوانده
    می‌شود تا روی تراکنش فراخواننده (Autoflush، تراکنش خطادار، قفل) هیچ اثری نگذارد؛ هر خطایی ← متن پیش‌فرض.
    """
    from app.db.session import AsyncSessionLocal

    module = _module_of(key)
    default = TEMPLATES[module][key]["default"]
    try:
        async with AsyncSessionLocal() as read_db:
            return (await _overrides(read_db, module, site_id)).get(key) or default
    except Exception:  # noqa: BLE001 - اعلان نباید به‌خاطر خواندن تنظیمات از دست برود
        logger.exception("خواندن متن اعلان سفارشی ناموفق بود")
        return default


def fill(text: str, **values) -> str:
    """جایگزینی متغیرها در متن خام get_text (برای حلقه‌ها: یک بار get_text، برای هر نفر fill)."""
    return _fill(text, values).strip()


async def render(db: AsyncSession | None, site_id: int | None, key: str, **values) -> str:
    """
    متن نهایی اعلان key برای سایت با جایگزینی متغیرها. هیچ‌وقت خطا نمی‌دهد. db فقط برای سازگاری امضا است؛
    خواندن با Session جدا انجام می‌شود (get_text).
    """
    return fill(await get_text(site_id, key), **values)


async def list_templates(db: AsyncSession, module: str, site_id: int | None) -> list[dict]:
    overrides = await _overrides(db, module, site_id)
    return [
        {
            "key": key,
            "label": t["label"],
            "recipient": t["recipient"],
            "when": t["when"],
            "default": t["default"],
            "max_length": max_len(key),
            "text": overrides.get(key) or t["default"],
            "customized": key in overrides,
            "vars": t.get("vars", {}),
        }
        for key, t in TEMPLATES[module].items()
    ]


async def save_templates(db: AsyncSession, module: str, site_id: int | None, texts: dict[str, str | None]) -> list[dict]:
    """
    texts: {کلید: متن}؛ متن خالی یا برابر پیش‌فرض = برگشت به پیش‌فرض. کلید ناشناخته نادیده گرفته می‌شود.
    متن طولانی‌تر از سقف ← TemplateError. ردیف تنظیمات قفل می‌شود تا دو ذخیره‌ی هم‌زمان تغییرات هم را پاک نکنند.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    known = TEMPLATES[module]
    skey = _setting_key(module, site_id)
    # ساخت ردیف خالی اگر نیست (بدون خطای یکتایی هم‌زمان) و قفل آن
    await db.execute(pg_insert(SystemSetting).values(key=skey, value="{}").on_conflict_do_nothing(index_elements=["key"]))
    row = (
        await db.execute(
            select(SystemSetting)
            .where(SystemSetting.key == skey)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    try:
        data = json.loads(row.value or "{}")
        current = {k: v for k, v in data.items() if isinstance(v, str) and v.strip()} if isinstance(data, dict) else {}
    except ValueError:
        current = {}
    for key, text in texts.items():
        if key not in known:
            continue
        value = (text or "").strip()
        if len(value) > max_len(key):
            await db.rollback()
            raise TemplateError(f"متن «{known[key]['label']}» حداکثر {max_len(key)} نویسه است")
        if not value or value == known[key]["default"]:
            current.pop(key, None)
        else:
            current[key] = value
    if current:
        row.value = json.dumps(current, ensure_ascii=False)
    else:
        await db.delete(row)
    await db.commit()
    return await list_templates(db, module, site_id)
