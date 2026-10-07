"""
گزارش خطاها (docs/error-logs.md): جمع‌آوری همه‌ی خطاهای پرتال در دیتابیس تا مدیر بدون SSH و journalctl ببیند.

منابع:
- **خطاهای سرور:** هر logger.error / logger.exception در هر جای بک‌اند (کاراوب، همگام‌سازی، زمان‌بندی‌ها، ایمیل، پیامک،
  بکاپ، ...) و هر خطای پیش‌بینی‌نشده‌ی Endpointها (Middleware در main.py) با DbErrorHandler روی logger ریشه.
- **درخواست‌های کند:** هر درخواست API بیش از SLOW_REQUEST_SECONDS (Middleware).
- **خطاهای مرورگر:** خطای JavaScript، صفحه‌ی سفید (ErrorBoundary) و درخواست‌هایی که به سرور نرسیدند (POST /error-logs/client).
- **خطاهای اپ اندروید:** بخش بومی اپ (POST /mobile/device/errors؛ فقط وقتی قابلیت اپ روشن است).

ثبت هیچ‌وقت درخواست کاربر را کند نمی‌کند: رکورد در یک صف حافظه گذاشته می‌شود و هر چند ثانیه یک Task جدا آن را در
دیتابیس می‌نویسد. خطاهای یکسان (همان بخش و متن، بدون اعداد) یک «گروه» با تعداد و اولین/آخرین زمان‌اند؛ هر رخداد هم با
کد پیگیری جدا ثبت می‌شود. خطای «جدید» (یا خطای حل‌شده‌ای که دوباره رخ داده) اگر SMTP و گیرنده تنظیم شده باشد ایمیل
می‌شود. همه‌چیز بعد از RETENTION_DAYS روز پاک می‌شود. رمز، توکن و کلید از متن‌ها حذف می‌شوند.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import sys
import threading
import time
import traceback
from collections import deque
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, delete, func, literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_context import (
    current_client_ip,
    current_request_id,
    current_request_label,
    current_user_ref,
)
from app.models.error_log import ErrorLog, ErrorLogOccurrence
from app.models.system_setting import SystemSetting

RETENTION_DAYS = 30
SLOW_REQUEST_SECONDS = 3.0
FLUSH_INTERVAL_SECONDS = 3.0
MAX_QUEUE = 2000
MAX_OCCURRENCES_PER_FLUSH = 20  # برای هر گروه در هر نوبت؛ تعداد کل همچنان دقیق شمرده می‌شود
ALERT_MAX_PER_HOUR = 10  # سقف ایمیل هشدار در هر ساعت (هر Worker)
SETTINGS_KEY = "error_alert_settings"
INTERNAL_LOGGER = "faipco.errorlog"  # خطاهای خودِ این سرویس دوباره ثبت نمی‌شوند (حلقه نسازد)

logger = logging.getLogger(INTERNAL_LOGGER)

_queue: deque = deque(maxlen=MAX_QUEUE)
_queue_lock = threading.Lock()
_flush_task: asyncio.Task | None = None
_alert_times: deque = deque()
_alert_tasks: set = set()

KIND_LABELS = {"error": "خطای سرور", "slow": "درخواست کند", "client": "خطای مرورگر", "android": "خطای اپ اندروید"}
CATEGORY_LABELS = {
    "kara": "کاراوب",
    "sync": "همگام‌سازی پرسنل",
    "scheduler": "کارهای زمان‌بندی‌شده",
    "email": "ایمیل",
    "sms": "پیامک",
    "backup": "پشتیبان‌گیری",
    "push": "اعلان (Push)",
    "attendance": "حضور و غیاب",
    "leave": "مرخصی/ماموریت",
    "notices": "اطلاعیه‌ها",
    "insurance": "بیمه تکمیلی",
    "family": "مشخصات خانوادگی",
    "auth": "ورود و حساب کاربری",
    "mobile": "اپ اندروید (سرور)",
    "database": "دیتابیس پرتال",
    "server": "سرور",
    "slow": "درخواست کند",
    "frontend": "خطای صفحه",
    "frontend_crash": "صفحه‌ی سفید / از کار افتادن صفحه",
    "network": "ارتباط مرورگر با سرور",
    "android": "اپ اندروید",
}

# ---------------------------------------------------------------- پاک‌سازی اطلاعات حساس

_SECRET_KEY = r"[\w-]*(?:password|passwd|pwd|secret|token|api[_-]?key|authorization)[\w-]*"
_SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+"), r"\1 ***"),  # هدر Authorization
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "***JWT***"),  # توکن JWT
    # مقدار داخل کوتیشن: password="a b" ، {'hashed_password': '$2b$...'} ، "token": "..."
    (re.compile(r"(?i)([\"']?" + _SECRET_KEY + r"[\"']?\s*[:=]\s*)([\"'])(?:(?!\2).)*\2"), r"\1\2***\2"),
    # مقدار بدون کوتیشن: password=abc ، token: abc (به‌جز موارد بالا که *** شده‌اند)
    (re.compile(r"(?i)(" + _SECRET_KEY + r"\s*[:=]\s*)(?![\"'*]|(?:bearer|basic) \*)([^\s&,;)}\]]+)"), r"\1***"),
    (re.compile(r"://([^:/@\s]+):([^@\s]+)@"), r"://\1:***@"),  # رمز در آدرس اتصال
]


def redact(text: str | None) -> str | None:
    if not text:
        return text
    for pattern, repl in _SENSITIVE_PATTERNS:
        text = pattern.sub(repl, text)
    return text


# ---------------------------------------------------------------- دسته‌بندی و راهنما

_CATEGORY_RULES = [
    ("kara", ("pymssql", "mssql", "kara", "sql server", "adaptive server")),
    ("sync", ("sync_engine", "sync_service", "همگام")),
    ("email", ("smtp", "email")),
    ("sms", ("sms", "پیامک")),
    ("backup", ("backup", "بکاپ", "پشتیبان")),
    ("push", ("push", "webpush", "vapid")),
    ("leave", ("leave_request", "مرخصی")),
    ("attendance", ("attendance", "presence", "gps", "تردد")),
    ("notices", ("notice", "اطلاعیه")),
    ("insurance", ("insurance", "بیمه")),
    ("family", ("family", "خانوادگی")),
    ("mobile", ("mobile_app", "geofence")),
    ("auth", ("auth", "login", "password_reset")),
    ("database", ("asyncpg", "sqlalchemy", "queuepool", "postgres")),
    ("scheduler", ("apscheduler", "scheduler")),
]


def _category_for(logger_name: str, text: str) -> str:
    haystack = f"{logger_name} {text}".lower()
    for category, needles in _CATEGORY_RULES:
        if any(n in haystack for n in needles):
            return category
    return "server"


# (الگو، توضیح فارسی) — اولین الگوی منطبق؛ {0} = اولین گروه الگو
_HINTS = [
    (r"Invalid column name '([^']+)'", "ستون «{0}» در جدول کاراوب وجود ندارد. نگاشت‌های سایت (تردد، مرخصی/ماموریت، پرسنل) را بررسی کنید که نام ستون درست باشد."),
    (r"Invalid object name '([^']+)'", "جدول «{0}» در دیتابیس کاراوب وجود ندارد. نام جدول را در نگاشت‌های سایت بررسی کنید."),
    (r"Login failed for user", "نام کاربری یا رمز اتصال به SQL Server کاراوب اشتباه است (تنظیمات اتصال سایت)."),
    (r"(?i)(Unable to connect|Adaptive Server is unavailable|timed out|timeout|Connection refused|DB-Lib error message 20009)", "اتصال به سرور مقصد برقرار نشد یا خیلی طول کشید (شبکه، خاموش بودن سرور یا فایروال). اگر کاراوب است، تنظیمات اتصال سایت و در دسترس بودن SQL Server را بررسی کنید."),
    (r"(?i)QueuePool limit", "همه‌ی اتصال‌های دیتابیس پرتال مشغول‌اند؛ معمولاً یعنی کارهای کند (مثلاً کاراوب) اتصال‌ها را نگه داشته‌اند. درخواست‌های کند هم‌زمان را ببینید."),
    (r"(?i)(SMTPAuthenticationError|Username and Password not accepted)", "نام کاربری/رمز ایمیل (SMTP) اشتباه است — تنظیمات سامانه ← ایمیل."),
    (r"(?i)smtp", "ارسال ایمیل ناموفق بود — تنظیمات سامانه ← ایمیل (آدرس سرور، پورت، رمزنگاری) را بررسی کنید."),
    (r"(?i)(ChunkLoadError|Loading chunk|Failed to fetch dynamically imported module)", "مرورگر کاربر نسخه‌ی قدیمی پرتال را داشت و فایل‌های جدید را پیدا نکرد (معمولاً بعد از آپدیت). با یک بار رفرش درست می‌شود."),
    (r"(?i)(Network Error|ECONNABORTED|timeout of \d+ms)", "درخواست مرورگر به سرور نرسید یا جواب در زمان مجاز نیامد. اگر برای همه است: سرور/پروکسی/شبکه؛ اگر فقط یک کاربر: اینترنت همان کاربر."),
    (r"(?i)MissingGreenlet", "خطای داخلی برنامه در خواندن داده (برنامه‌نویسی). متن کامل را برای پشتیبانی بفرستید."),
    (r"(?i)disk|No space left", "فضای دیسک سرور پر است."),
]


def hint_for(kind: str, category: str, message: str) -> str | None:
    if kind == "slow":
        return "این درخواست بیش از حد طول کشید. اگر مربوط به کاراوب است (گزارش تردد، مرخصی، همگام‌سازی) معمولاً کندی SQL Server یا شبکه است؛ اگر همه‌ی درخواست‌ها کندند، بار سرور پرتال را ببینید."
    for pattern, text in _HINTS:
        match = re.search(pattern, message or "")
        if match:
            return text.format(*(match.groups() or ("",)))
    if category == "frontend_crash":
        return "صفحه در مرورگر کاربر از کار افتاد (صفحه‌ی سفید). متن کامل و صفحه‌ی مربوط را برای پشتیبانی بفرستید."
    return None


# ---------------------------------------------------------------- صف

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fingerprint(kind: str, category: str, source: str | None, message: str, extra: str = "") -> str:
    normalized = re.sub(r"0x[0-9a-fA-F]+|[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}|\d+", "#", message or "")[:400]
    raw = f"{kind}|{category}|{source or ''}|{extra}|{normalized}"
    return hashlib.sha1(raw.encode("utf-8", "ignore")).hexdigest()


def _clean(text: str | None) -> str | None:
    """کاراکتر NUL را Postgres در متن نمی‌پذیرد؛ یک گزارش مرورگر با \\u0000 کل نوبت نوشتن را خراب می‌کرد."""
    return text.replace("\x00", "") if isinstance(text, str) else text


def _clean_context(context: dict | None) -> dict | None:
    if not context:
        return context
    return {_clean(str(k)): (_clean(v) if isinstance(v, str) else v) for k, v in context.items()}


def enqueue(
    kind: str,
    category: str,
    source: str | None,
    message: str,
    detail: str | None = None,
    *,
    context: dict | None = None,
    fingerprint_extra: str = "",
    request_id: str | None = None,
    request: str | None = None,
    user: tuple[int, str] | None = None,
    ip: str | None = None,
) -> None:
    """یک رخداد را در صف حافظه می‌گذارد (بدون I/O؛ از هر Thread قابل‌صدا زدن)."""
    message = _clean(redact((message or "").strip()))[:4000] or "(بدون متن)"
    detail = _clean(redact(detail))[-20000:] if detail else None
    source = _clean(source)
    request = _clean(request)
    if request_id is None:
        request_id = current_request_id.get() or None
    if request is None:
        request = current_request_label.get() or None
    if user is None:
        user = current_user_ref.get()
    if ip is None:
        ip = current_client_ip.get() or None
    item = {
        "fp": _fingerprint(kind, category, source, message, fingerprint_extra),
        "kind": kind,
        "category": category,
        "source": (source or "")[:120] or None,
        "message": message,
        "detail": detail,
        "context": _clean_context(context) or None,
        "request_id": request_id,
        "request": (request or "")[:300] or None,
        "user_id": user[0] if user else None,
        "user_label": _clean(user[1] if user else None),
        "ip": (ip or "")[:64] or None,
        "at": _now(),
    }
    with _queue_lock:
        _queue.append(item)


class DbErrorHandler(logging.Handler):
    """هر رکورد ERROR (و بالاتر) هر logger را در صف گزارش خطاها می‌گذارد."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.name.startswith(INTERNAL_LOGGER):
                return
            message = record.getMessage()
            detail = None
            exc_type = ""
            if record.exc_info and record.exc_info[0] is not None:
                detail = "".join(traceback.format_exception(*record.exc_info))
                exc_type = record.exc_info[0].__name__
                exc_text = str(record.exc_info[1] or "").strip()
                if exc_text and exc_text not in message:
                    message = f"{message} — {exc_type}: {exc_text}"
            enqueue(
                "error",
                _category_for(record.name, f"{message}\n{detail or ''}"),
                record.name,
                message,
                detail,
                fingerprint_extra=exc_type,
            )
        except Exception:  # noqa: BLE001 - ثبت خطا هرگز نباید خودش خطا بدهد
            pass


def install_logging() -> None:
    """
    DbErrorHandler روی logger ریشه و uvicorn.error. چون logger ریشه تا الان Handler نداشت و پیام‌ها با «lastResort»
    پایتون به journalctl می‌رفتند، یک StreamHandler هم اضافه می‌شود تا خروجی journalctl مثل قبل بماند.
    """
    root = logging.getLogger()
    if any(isinstance(h, DbErrorHandler) for h in root.handlers):
        return
    if not root.handlers:
        stream = logging.StreamHandler(sys.stderr)
        stream.setLevel(logging.WARNING)
        stream.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root.addHandler(stream)
    root.addHandler(DbErrorHandler())
    logging.getLogger("uvicorn.error").addHandler(DbErrorHandler())


# ---------------------------------------------------------------- منابع دیگر

def record_slow_request(method: str, route: str, path: str, seconds: float, status: int, request_id: str,
                        user: tuple[int, str] | None, ip: str | None) -> None:
    enqueue(
        "slow",
        "slow",
        f"{method} {route}",
        f"درخواست کند: {method} {route} — {seconds:.1f} ثانیه (پاسخ {status})",
        context={"seconds": round(seconds, 2), "status": status, "path": path[:300]},
        request_id=request_id,
        request=f"{method} {path}"[:300],
        user=user,
        ip=ip,
    )


def record_client_error(payload: dict, user: tuple[int, str] | None, ip: str | None, user_agent: str | None) -> None:
    kind_map = {"crash": "frontend_crash", "network": "network"}
    category = kind_map.get(payload.get("type") or "", "frontend")
    page = (payload.get("page") or "")[:300]
    message = (payload.get("message") or "")[:2000]
    source = (payload.get("source") or page.split("?")[0] or "مرورگر")[:120]
    enqueue(
        "client",
        category,
        source,
        message,
        payload.get("stack"),
        context={
            "page": page,
            "user_agent": (user_agent or "")[:300],
            "app_version": (payload.get("app_version") or "")[:40],
            "in_android_app": bool(payload.get("in_android_app")),
            **({"api": str(payload.get("api"))[:300]} if payload.get("api") else {}),
        },
        request_id=(payload.get("request_id") or None),
        request=(f"صفحه {page}" if page else None),
        user=user,
        ip=ip,
    )


def record_android_error(payload: dict, user: tuple[int, str] | None, device_label: str, ip: str | None) -> None:
    enqueue(
        "android",
        "android",
        (payload.get("where") or "اپ")[:120],
        (payload.get("message") or "")[:2000],
        payload.get("stack"),
        context={
            "device": device_label[:120],
            "app_version": (payload.get("app_version") or "")[:40],
            "sdk": payload.get("sdk"),
            "occurred_on_phone": payload.get("occurred_at"),
        },
        request=f"اپ: {(payload.get('where') or '')[:100]}",
        user=user,
        ip=ip,
    )


# ---------------------------------------------------------------- نوشتن در دیتابیس

def _drain() -> list[dict]:
    with _queue_lock:
        items = list(_queue)
        _queue.clear()
    return items


MAX_FLUSH_TRIES = 3


def _requeue(items: list[dict]) -> None:
    """
    نوشتن ناموفق (قطعی دیتابیس، پر بودن اتصال‌ها، تداخل دو Worker): رخدادها به اول صف برمی‌گردند تا در نوبت بعد نوشته
    شوند — همان لحظه‌هایی که بیشترین نیاز به ثبت خطا هست. هر رخداد حداکثر MAX_FLUSH_TRIES بار (رخداد خراب صف را گیر ندهد).
    """
    keep = []
    for item in items:
        item["tries"] = item.get("tries", 0) + 1
        if item["tries"] < MAX_FLUSH_TRIES:
            keep.append(item)
    with _queue_lock:
        _queue.extendleft(reversed(keep))


async def flush() -> int:
    """صف را در دیتابیس می‌نویسد؛ خروجی: تعداد رخدادها. خطاها فقط لاگ داخلی می‌شوند."""
    items = _drain()
    if not items:
        return 0
    from app.db.session import AsyncSessionLocal

    groups: dict[str, list[dict]] = {}
    for item in items:
        groups.setdefault(item["fp"], []).append(item)
    alerts: list[dict] = []
    try:
        async with AsyncSessionLocal() as db:
            existing = {
                fp: resolved
                for fp, resolved in (
                    await db.execute(
                        select(ErrorLog.fingerprint, ErrorLog.resolved_at).where(ErrorLog.fingerprint.in_(list(groups)))
                    )
                ).all()
            }
            # ترتیب ثابت قفل ردیف‌ها: دو Worker که هم‌زمان چند گروه مشترک می‌نویسند به بن‌بست (deadlock) نمی‌خورند
            for fp in sorted(groups):
                group = groups[fp]
                last = group[-1]
                values = {
                    "fingerprint": fp,
                    "kind": last["kind"],
                    "category": last["category"],
                    "source": last["source"],
                    "message": last["message"],
                    "detail": last["detail"],
                    "count": len(group),
                    "first_seen": group[0]["at"],
                    "last_seen": last["at"],
                    "last_request": last["request"],
                    "last_user_id": last["user_id"],
                    "last_user_label": last["user_label"],
                    "last_ip": last["ip"],
                    "last_context": last["context"],
                }
                stmt = pg_insert(ErrorLog).values(**values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[ErrorLog.fingerprint],
                    set_={
                        "count": ErrorLog.count + len(group),
                        "first_seen": func.least(ErrorLog.first_seen, stmt.excluded.first_seen),
                        "last_seen": func.greatest(ErrorLog.last_seen, stmt.excluded.last_seen),
                        # جزئیات «آخرین رخداد» فقط با رخداد واقعاً جدیدتر عوض می‌شود (نوبت دیرتر Worker دیگر عقب نبرد)
                        **{
                            col: case((newer, getattr(stmt.excluded, col)), else_=getattr(ErrorLog, col))
                            for col, newer in (
                                (c, stmt.excluded.last_seen >= ErrorLog.last_seen)
                                for c in ("message", "last_request", "last_user_id", "last_user_label", "last_ip", "last_context")
                            )
                        },
                        "detail": case(
                            (stmt.excluded.last_seen >= ErrorLog.last_seen, func.coalesce(stmt.excluded.detail, ErrorLog.detail)),
                            else_=ErrorLog.detail,
                        ),
                        # دوباره رخ داد ← دوباره باز؛ ولی رخدادی که پیش از «حل شد» بوده (در صف چندثانیه‌ای) بازش نمی‌کند
                        "resolved_at": case((stmt.excluded.last_seen > ErrorLog.resolved_at, None), else_=ErrorLog.resolved_at),
                        "resolved_by_user_id": case(
                            (stmt.excluded.last_seen > ErrorLog.resolved_at, None), else_=ErrorLog.resolved_by_user_id
                        ),
                    },
                ).returning(ErrorLog.id, literal_column("(xmax = 0)").label("inserted"))
                error_id, inserted = (await db.execute(stmt)).one()
                for occ in group[-MAX_OCCURRENCES_PER_FLUSH:]:
                    db.add(
                        ErrorLogOccurrence(
                            error_id=error_id,
                            occurred_at=occ["at"],
                            request_id=occ["request_id"],
                            request=occ["request"],
                            user_id=occ["user_id"],
                            user_label=occ["user_label"],
                            ip=occ["ip"],
                            context=occ["context"],
                        )
                    )
                # «جدید» از خود نتیجه‌ی upsert (اگر هر دو Worker هم‌زمان ببینند، فقط یکی درج کرده) — یک ایمیل، نه دو
                is_new = bool(inserted)
                reopened = not is_new and existing.get(fp) is not None and last["at"] > existing[fp]
                if (is_new or reopened) and _alert_worthy(last):
                    alerts.append({**last, "id": error_id, "count": len(group), "reopened": reopened})
            await db.commit()
    except asyncio.CancelledError:
        _requeue(items)
        raise
    except Exception:  # noqa: BLE001
        logger.exception("نوشتن گزارش خطاها در دیتابیس ناموفق بود (%s رخداد)", len(items))
        _requeue(items)
        return 0
    if alerts:
        task = asyncio.create_task(_send_alerts(alerts))
        _alert_tasks.add(task)  # نگه داشتن ارجاع (Task بی‌ارجاع ممکن است نیمه‌کاره جمع شود) و انتظار در stop
        task.add_done_callback(_alert_tasks.discard)
    return len(items)


def _alert_worthy(item: dict) -> bool:
    """ایمیل فوری فقط برای خطاهای واقعی: سرور، اپ، و از کار افتادن صفحه (نه درخواست کند یا قطعی اینترنت کاربر)."""
    return item["kind"] in ("error", "android") or item["category"] == "frontend_crash"


async def _flush_loop() -> None:
    while True:
        await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
        try:
            await flush()
        except Exception:  # noqa: BLE001
            logger.exception("حلقه‌ی گزارش خطاها")


def start() -> None:
    global _flush_task
    if _flush_task is None or _flush_task.done():
        _flush_task = asyncio.create_task(_flush_loop())


async def stop() -> None:
    global _flush_task
    if _flush_task is not None:
        _flush_task.cancel()
        try:
            await _flush_task  # نوبت نیمه‌کاره تمام (و صفش برگردانده) شود، بعد نوبت آخر
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        _flush_task = None
    await flush()
    if _alert_tasks:
        await asyncio.wait(list(_alert_tasks), timeout=10)


async def purge_old(db: AsyncSession) -> int:
    """رخدادها و گروه‌های قدیمی‌تر از RETENTION_DAYS روز پاک می‌شوند."""
    cutoff = _now() - timedelta(days=RETENTION_DAYS)
    await db.execute(delete(ErrorLogOccurrence).where(ErrorLogOccurrence.occurred_at < cutoff))
    result = await db.execute(delete(ErrorLog).where(ErrorLog.last_seen < cutoff))
    await db.commit()
    return result.rowcount or 0


# ---------------------------------------------------------------- تنظیمات و ایمیل هشدار

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def get_alert_settings(db: AsyncSession) -> dict:
    row = await db.get(SystemSetting, SETTINGS_KEY)
    data: dict = {}
    if row is not None:
        try:
            data = json.loads(row.value) or {}
        except (ValueError, TypeError):
            data = {}
    recipients = [r for r in (data.get("recipients") or []) if isinstance(r, str) and _EMAIL_RE.match(r)]
    return {"enabled": bool(data.get("enabled", True)), "recipients": recipients}


async def save_alert_settings(db: AsyncSession, enabled: bool, recipients: list[str]) -> dict:
    clean = []
    for r in recipients:
        r = (r or "").strip()
        if not r:
            continue
        if not _EMAIL_RE.match(r):
            raise ValueError(f"آدرس ایمیل نامعتبر است: {r}")
        if r not in clean:
            clean.append(r)
    value = json.dumps({"enabled": bool(enabled), "recipients": clean[:10]}, ensure_ascii=False)
    row = await db.get(SystemSetting, SETTINGS_KEY)
    if row is None:
        db.add(SystemSetting(key=SETTINGS_KEY, value=value))
    else:
        row.value = value
    await db.commit()
    return await get_alert_settings(db)


async def smtp_ready(db: AsyncSession) -> bool:
    from app.services.email_service import get_smtp_settings

    smtp = await get_smtp_settings(db)
    return bool(smtp.enabled and smtp.host and smtp.from_address)


def _tehran(dt: datetime) -> str:
    from zoneinfo import ZoneInfo

    return dt.astimezone(ZoneInfo("Asia/Tehran")).strftime("%Y-%m-%d %H:%M:%S")


def _alert_body(items: list[dict]) -> str:
    lines = ["خطای جدید در پرتال ثبت شد. جزئیات کامل: پنل مدیریت ← سیستم ← گزارش خطاها.", ""]
    for item in items:
        title = "دوباره رخ داد" if item.get("reopened") else "جدید"
        lines.append(f"• [{title}] {KIND_LABELS.get(item['kind'], item['kind'])} — {CATEGORY_LABELS.get(item['category'], item['category'])}")
        lines.append(f"  زمان (تهران): {_tehran(item['at'])}")
        lines.append(f"  متن: {item['message'][:500]}")
        hint = hint_for(item["kind"], item["category"], item["message"])
        if hint:
            lines.append(f"  راهنما: {hint}")
        if item.get("request"):
            lines.append(f"  درخواست: {item['request']}")
        if item.get("user_label"):
            lines.append(f"  کاربر: {item['user_label']}")
        if item.get("request_id"):
            lines.append(f"  کد پیگیری: {item['request_id']}")
        lines.append(f"  شماره‌ی خطا در پنل: {item['id']}")
        lines.append("")
    return "\n".join(lines)


async def _send_alerts(items: list[dict]) -> None:
    """ایمیل هشدار؛ اگر هشدار خاموش، گیرنده‌ای تعریف نشده یا SMTP تنظیم نشده باشد، بی‌صدا چیزی ارسال نمی‌شود."""
    from app.db.session import AsyncSessionLocal
    from app.services.email_service import EmailError, send_email

    now = time.monotonic()
    while _alert_times and now - _alert_times[0] > 3600:
        _alert_times.popleft()
    if len(_alert_times) >= ALERT_MAX_PER_HOUR:
        return
    _alert_times.append(now)  # پیش از اولین await: چند Task هم‌زمان از سقف رد نشوند
    try:
        async with AsyncSessionLocal() as db:
            cfg = await get_alert_settings(db)
            if not cfg["enabled"] or not cfg["recipients"] or not await smtp_ready(db):
                if now in _alert_times:
                    _alert_times.remove(now)  # چیزی فرستاده نشد؛ سهم ساعت مصرف نشود
                return
            first = items[0]
            subject = f"خطای جدید در پرتال: {CATEGORY_LABELS.get(first['category'], first['category'])}"
            if len(items) > 1:
                subject += f" (+{len(items) - 1} مورد دیگر)"
            body = _alert_body(items)
            for address in cfg["recipients"]:
                try:
                    await send_email(db, to_address=address, subject=subject, body_text=body)
                except EmailError:
                    # خطای ارسال ایمیل فقط در لاگ داخلی (نه گزارش خطاها، تا حلقه‌ی ایمیل نسازد)
                    logger.warning("ارسال ایمیل هشدار خطا به %s ناموفق بود", address)
    except Exception:  # noqa: BLE001
        logger.warning("ارسال هشدار خطاها ناموفق بود", exc_info=True)
