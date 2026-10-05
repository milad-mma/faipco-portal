"""
امنیت ورود و بازیابی رمز (docs/login-security.md):

- تنظیمات قابل ویرایش از پنل (LoginSecuritySettings، کلید login_security در system_settings).
- قفل پلکانی هر شناسه با تعداد و مدت‌های قابل تنظیم (زیرساخت app/core/rate_limit.py).
- محدودیت IP: اگر از یک IP در بازه‌ی ip_window_minutes حداقل ip_max_failures تلاش ناموفق (روی هر شناسه‌ای)
  ثبت شود، آن IP به مدت ip_block_minutes مسدود می‌شود (کلید ip:<آدرس> در login_attempts).
  IPهای معاف (مثلاً IP مشترک کارخانه) محدودیت IP و کپچای مبتنی بر IP ندارند؛ قفل هر شناسه برایشان برقرار است.
- کپچای تصویری داخلی: برای ورود بعد از captcha_after_failures تلاش ناموفق روی همان شناسه یا همان IP؛
  برای فراموشی رمز همیشه (اگر روشن باشد). یک‌بارمصرف، انقضای ۳ دقیقه، فقط هش HMAC پاسخ ذخیره می‌شود.
- گزارش: هر رویداد ناموفق در login_security_events. هشدار Push به دارندگان system.login_security و
  superuserها وقتی تعداد تلاش ناموفق در alert_window_minutes به alert_threshold برسد (حداکثر یک‌بار در هر بازه).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.captcha import random_answer, render_captcha_png
from app.core.config import get_settings
from app.core.rate_limit import (
    check_login_lockout,
    get_fail_count,
    lock_key_for,
    record_failed_login,
)
from app.core.text_normalize import normalize_search_text
from app.models.login_security import CaptchaChallenge, LoginSecurityEvent
from app.models.rate_limit import LoginAttempt
from app.models.system_setting import SystemSetting
from app.models.user import Permission, RolePermission, User, UserRole
from app.schemas.login_security import LoginSecuritySettings

logger = logging.getLogger(__name__)

SETTINGS_KEY = "login_security"
LAST_ALERT_KEY = "login_security_last_alert_at"
CAPTCHA_TTL_SECONDS = 180
PERMISSION_CODE = "system.login_security"
IP_KEY_PREFIX = "ip:"
RESET_KEY_PREFIX = "reset-password:"

# رویدادهایی که «تلاش ناموفق» حساب می‌شوند (محدودیت IP، کپچای IP و هشدار)
FAILURE_KINDS = ("login_failed", "captcha_failed", "reset_code_failed")
# سقف درخواست‌های «فراموشی رمز» از یک IP در بازه‌ی ip_window_minutes (جدا از تلاش‌های ناموفق؛
# درخواست موفق هم شمرده می‌شود تا نتوان با شناسه‌های متفاوت، وجود حساب‌ها را انبوه بررسی یا پیامک انبوه فرستاد)
FORGOT_PASSWORD_IP_MAX = 10
EVENT_LABELS = {
    "login_failed": "ورود ناموفق",
    "login_locked": "تلاش روی شناسه‌ی قفل",
    "ip_blocked": "مسدود شدن IP",
    "captcha_failed": "کد امنیتی اشتباه",
    "reset_code_failed": "کد بازیابی اشتباه",
    "forgot_password": "درخواست بازیابی رمز",
}


# ---------- تنظیمات ----------


async def _get_raw(db: AsyncSession, key: str) -> str | None:
    result = await db.execute(select(SystemSetting.value).where(SystemSetting.key == key))
    return result.scalar_one_or_none()


async def _set_raw(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(SystemSetting, key)
    if row is None:
        db.add(SystemSetting(key=key, value=value))
    else:
        row.value = value
    await db.commit()


async def get_login_security_settings(db: AsyncSession) -> LoginSecuritySettings:
    """تنظیمات ذخیره‌شده؛ مقدار خراب یا ناموجود = پیش‌فرض‌ها (کلیدهای معتبر حفظ می‌شوند)."""
    raw = await _get_raw(db, SETTINGS_KEY)
    if not raw:
        return LoginSecuritySettings()
    try:
        return LoginSecuritySettings.model_validate(json.loads(raw))
    except Exception:  # noqa: BLE001 - تنظیم خراب نباید ورود را از کار بیندازد
        logger.warning("تنظیمات امنیت ورود نامعتبر است؛ پیش‌فرض‌ها اعمال شد")
        return LoginSecuritySettings()


async def save_login_security_settings(db: AsyncSession, data: LoginSecuritySettings) -> LoginSecuritySettings:
    await _set_raw(db, SETTINGS_KEY, data.model_dump_json())
    return data


def lock_seconds(cfg: LoginSecuritySettings) -> list[int]:
    return [m * 60 for m in cfg.lock_minutes]


def is_exempt_ip(cfg: LoginSecuritySettings, ip: str) -> bool:
    """آیا IP در فهرست معاف است؟ (IPv4-mapped IPv6 هم پشتیبانی می‌شود)"""
    if not cfg.exempt_ips:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    for cidr in cfg.exempt_ips:
        try:
            if addr in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def ip_limit_applies(cfg: LoginSecuritySettings, ip: str) -> bool:
    return cfg.ip_limit_enabled and ip not in ("", "unknown") and not is_exempt_ip(cfg, ip)


# ---------- رویدادها، محدودیت IP و هشدار ----------


async def log_event(
    db: AsyncSession, kind: str, ip: str, identifier: str | None = None, user_agent: str | None = None
) -> None:
    db.add(
        LoginSecurityEvent(
            created_at=datetime.now(timezone.utc),
            kind=kind,
            identifier=(normalize_search_text(identifier).lower()[:255] or None) if identifier else None,
            ip=(ip or "unknown")[:64],
            user_agent=(user_agent or "")[:200] or None,
            counted=True,
        )
    )
    await db.commit()


async def ip_failure_count(db: AsyncSession, ip: str, window_minutes: int) -> int:
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    result = await db.execute(
        select(func.count(LoginSecurityEvent.id)).where(
            LoginSecurityEvent.ip == ip,
            LoginSecurityEvent.created_at >= since,
            LoginSecurityEvent.counted.is_(True),
            LoginSecurityEvent.kind.in_(FAILURE_KINDS),
        )
    )
    return int(result.scalar_one() or 0)


async def forgot_password_ip_exceeded(db: AsyncSession, cfg: LoginSecuritySettings, ip: str) -> bool:
    """
    True اگر این IP (غیرمعاف، با محدودیت IP روشن) در بازه‌ی ip_window_minutes به سقف FORGOT_PASSWORD_IP_MAX
    درخواست «فراموشی رمز» رسیده باشد؛ رویدادهای forgot_password که قبلاً از پنل آزاد شده‌اند (counted=False) شمرده نمی‌شوند.
    """
    if not ip_limit_applies(cfg, ip):
        return False
    since = datetime.now(timezone.utc) - timedelta(minutes=cfg.ip_window_minutes)
    result = await db.execute(
        select(func.count(LoginSecurityEvent.id)).where(
            LoginSecurityEvent.ip == ip,
            LoginSecurityEvent.created_at >= since,
            LoginSecurityEvent.counted.is_(True),
            LoginSecurityEvent.kind == "forgot_password",
        )
    )
    return int(result.scalar_one() or 0) >= FORGOT_PASSWORD_IP_MAX


async def ip_block_remaining(db: AsyncSession, cfg: LoginSecuritySettings, ip: str) -> float | None:
    """ثانیه‌های باقی‌مانده از مسدودیت این IP (None = آزاد یا محدودیت برایش اعمال نمی‌شود)."""
    if not ip_limit_applies(cfg, ip):
        return None
    return await check_login_lockout(db, IP_KEY_PREFIX + ip)


async def _after_failure(db: AsyncSession, cfg: LoginSecuritySettings, ip: str, user_agent: str | None) -> None:
    """بعد از هر رویداد ناموفق: بررسی سقف IP و هشدار حجم غیرعادی."""
    if ip_limit_applies(cfg, ip):
        if await ip_failure_count(db, ip, cfg.ip_window_minutes) >= cfg.ip_max_failures:
            if await check_login_lockout(db, IP_KEY_PREFIX + ip) is None:
                await lock_key_for(db, IP_KEY_PREFIX + ip, cfg.ip_block_minutes * 60)
                await log_event(db, "ip_blocked", ip, user_agent=user_agent)
                logger.warning("IP %s به‌خاطر تلاش‌های ناموفق زیاد %s دقیقه مسدود شد", ip, cfg.ip_block_minutes)
    await maybe_send_alert(db, cfg)


async def record_login_failure(
    db: AsyncSession, cfg: LoginSecuritySettings, identifier: str, ip: str, user_agent: str | None
) -> None:
    """ورود ناموفق: شمارنده‌ی پلکانی شناسه، ثبت رویداد، محدودیت IP و هشدار."""
    await record_failed_login(db, identifier, cfg.attempts_per_tier, lock_seconds(cfg))
    await log_event(db, "login_failed", ip, identifier, user_agent)
    await _after_failure(db, cfg, ip, user_agent)


async def record_other_failure(
    db: AsyncSession, cfg: LoginSecuritySettings, kind: str, ip: str, identifier: str | None, user_agent: str | None
) -> None:
    """کپچای اشتباه یا کد بازیابی اشتباه: ثبت رویداد، محدودیت IP و هشدار (بدون قفل شناسه)."""
    await log_event(db, kind, ip, identifier, user_agent)
    await _after_failure(db, cfg, ip, user_agent)


async def captcha_required_for_login(db: AsyncSession, cfg: LoginSecuritySettings, identifier: str, ip: str) -> bool:
    """کپچا لازم است اگر: روشن باشد و (آستانه ۰ باشد، یا شناسه، یا IP غیرمعاف به آستانه رسیده باشد)."""
    if not cfg.captcha_enabled:
        return False
    if cfg.captcha_after_failures == 0:
        return True
    if identifier and await get_fail_count(db, identifier) >= cfg.captcha_after_failures:
        return True
    # IP معاف (مثلاً IP مشترک کارخانه): فقط شمارنده‌ی خود شناسه ملاک است، نه خطای بقیه‌ی همکاران
    if ip not in ("", "unknown") and not is_exempt_ip(cfg, ip):
        return await ip_failure_count(db, ip, cfg.ip_window_minutes) >= cfg.captcha_after_failures
    return False


async def alert_recipient_ids(db: AsyncSession) -> set[int]:
    """superuserها و دارندگان system.login_security (فعال)."""
    result = await db.execute(
        select(User.id)
        .outerjoin(UserRole, UserRole.user_id == User.id)
        .outerjoin(RolePermission, RolePermission.role_id == UserRole.role_id)
        .outerjoin(Permission, Permission.id == RolePermission.permission_id)
        .where(User.is_active.is_(True), or_(User.is_superuser.is_(True), Permission.code == PERMISSION_CODE))
        .distinct()
    )
    return {row[0] for row in result.all()}


async def maybe_send_alert(db: AsyncSession, cfg: LoginSecuritySettings) -> None:
    """اگر تلاش‌های ناموفق در بازه‌ی هشدار به آستانه رسید و در همین بازه هشداری نرفته، Push می‌فرستد."""
    if not cfg.alert_enabled:
        return
    now = datetime.now(timezone.utc)
    since = now - timedelta(minutes=cfg.alert_window_minutes)
    last_raw = await _get_raw(db, LAST_ALERT_KEY)
    if last_raw:
        try:
            if datetime.fromisoformat(last_raw) > since:
                return
        except ValueError:
            pass
    result = await db.execute(
        select(func.count(LoginSecurityEvent.id)).where(
            LoginSecurityEvent.created_at >= since, LoginSecurityEvent.kind.in_(FAILURE_KINDS)
        )
    )
    count = int(result.scalar_one() or 0)
    if count < cfg.alert_threshold:
        return
    await _set_raw(db, LAST_ALERT_KEY, now.isoformat())
    logger.warning("هشدار امنیت ورود: %s تلاش ناموفق در %s دقیقه‌ی اخیر", count, cfg.alert_window_minutes)
    try:
        from app.services.push_background import schedule_push

        # گیرندگان با Session درخواست حساب می‌شوند؛ ارسال در پس‌زمینه تا پاسخ ورود منتظر Push نماند
        schedule_push(
            await alert_recipient_ids(db),
            url="/login-security",
            priority="high",
            body=f"هشدار امنیتی: {count} تلاش ناموفق ورود در {cfg.alert_window_minutes} دقیقه‌ی اخیر. گزارش امنیت ورود را بررسی کنید.",
        )
    except Exception:  # noqa: BLE001 - خطای Push نباید پاسخ ورود را خراب کند
        logger.exception("ارسال هشدار امنیت ورود ناموفق بود")


# ---------- کپچا ----------


def _answer_hash(challenge_id: str, answer: str) -> str:
    key = get_settings().SECRET_KEY.encode()
    return hmac.new(key, f"captcha:{challenge_id}:{answer}".encode(), hashlib.sha256).hexdigest()


async def create_captcha(db: AsyncSession) -> dict:
    """چالش تازه: {captcha_id, image (data URL)، expires_in}. چالش‌های منقضی همان‌جا پاک می‌شوند."""
    now = datetime.now(timezone.utc)
    await db.execute(delete(CaptchaChallenge).where(CaptchaChallenge.expires_at < now))
    challenge_id = str(uuid.uuid4())
    answer = random_answer()
    db.add(
        CaptchaChallenge(
            id=challenge_id,
            answer_hash=_answer_hash(challenge_id, answer),
            expires_at=now + timedelta(seconds=CAPTCHA_TTL_SECONDS),
            attempts=0,
        )
    )
    await db.commit()
    png = await asyncio.to_thread(render_captcha_png, answer)  # رندر Pillow همگام؛ حلقه‌ی async معطل نشود
    return {
        "captcha_id": challenge_id,
        "image": "data:image/png;base64," + base64.b64encode(png).decode(),
        "expires_in": CAPTCHA_TTL_SECONDS,
    }


async def verify_captcha(db: AsyncSession, challenge_id: str | None, answer: str | None) -> bool:
    """پاسخ را بررسی و چالش را (درست یا غلط) حذف می‌کند؛ یک‌بارمصرف. ارقام فارسی/عربی پذیرفته می‌شوند."""
    if not challenge_id or not answer:
        return False
    row = await db.get(CaptchaChallenge, str(challenge_id)[:36])
    if row is None:
        return False
    await db.delete(row)
    await db.commit()
    if row.expires_at < datetime.now(timezone.utc):
        return False
    normalized = "".join(ch for ch in normalize_search_text(answer) if not ch.isspace())
    return hmac.compare_digest(row.answer_hash, _answer_hash(row.id, normalized))


# ---------- مدیریت (پنل) ----------


def describe_key(key: str) -> tuple[str, str]:
    """کلید login_attempts → (نوع، مقدار نمایشی)."""
    if key.startswith(IP_KEY_PREFIX):
        return "ip", key[len(IP_KEY_PREFIX):]
    if key.startswith(RESET_KEY_PREFIX):
        return "reset", key[len(RESET_KEY_PREFIX):]
    return "identifier", key


async def list_active_locks(db: AsyncSession) -> list[dict]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(LoginAttempt).where(LoginAttempt.locked_until > now).order_by(LoginAttempt.locked_until.desc())
    )
    out = []
    for row in result.scalars().all():
        kind, value = describe_key(row.identifier)
        out.append(
            {"key": row.identifier, "kind": kind, "value": value, "fail_count": row.fail_count, "locked_until": row.locked_until}
        )
    return out


async def unlock_key(db: AsyncSession, key: str) -> None:
    """قفل و شمارنده‌ی یک کلید را پاک می‌کند؛ برای IP رویدادهای اخیرش هم دیگر در سقف IP شمرده نمی‌شوند."""
    await db.execute(delete(LoginAttempt).where(LoginAttempt.identifier == key))
    kind, value = describe_key(key)
    if kind in ("ip", "reset"):
        await db.execute(update(LoginSecurityEvent).where(LoginSecurityEvent.ip == value).values(counted=False))
    await db.commit()


async def unlock_employee(db: AsyncSession, employee) -> list[str]:
    """قفل‌های کد پرسنلی و نام کاربری حساب متصل به یک پرسنل را پاک می‌کند. خروجی: کلیدهای پاک‌شده."""
    keys = set()
    if employee.personnel_code:
        keys.add(normalize_search_text(employee.personnel_code).lower())
    result = await db.execute(select(User.username).where(User.employee_id == employee.id))
    keys.update(normalize_search_text(u).lower() for u in result.scalars().all() if u)
    if not keys:
        return []
    result = await db.execute(select(LoginAttempt.identifier).where(LoginAttempt.identifier.in_(keys)))
    found = [row[0] for row in result.all()]
    if found:
        await db.execute(delete(LoginAttempt).where(LoginAttempt.identifier.in_(found)))
        await db.commit()
    return found


async def list_events(
    db: AsyncSession, kind: str | None, search: str | None, hours: int, limit: int, offset: int
) -> tuple[list[LoginSecurityEvent], int]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    conds = [LoginSecurityEvent.created_at >= since]
    if kind:
        conds.append(LoginSecurityEvent.kind == kind)
    term = normalize_search_text(search).lower()
    if term:
        pattern = f"%{term}%"
        conds.append(or_(LoginSecurityEvent.ip.ilike(pattern), LoginSecurityEvent.identifier.ilike(pattern)))
    total = (await db.execute(select(func.count(LoginSecurityEvent.id)).where(*conds))).scalar_one()
    result = await db.execute(
        select(LoginSecurityEvent).where(*conds).order_by(LoginSecurityEvent.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), int(total or 0)


async def summary(db: AsyncSession, hours: int) -> dict:
    """شمارش هر نوع رویداد، پرتکرارترین IPها و شناسه‌های ناموفق در بازه."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    by_kind_rows = await db.execute(
        select(LoginSecurityEvent.kind, func.count(LoginSecurityEvent.id))
        .where(LoginSecurityEvent.created_at >= since)
        .group_by(LoginSecurityEvent.kind)
    )
    by_kind = {k: int(c) for k, c in by_kind_rows.all()}

    fail_cond = [LoginSecurityEvent.created_at >= since, LoginSecurityEvent.kind.in_(FAILURE_KINDS)]
    top_ip_rows = await db.execute(
        select(LoginSecurityEvent.ip, func.count(LoginSecurityEvent.id).label("c"), func.count(func.distinct(LoginSecurityEvent.identifier)))
        .where(*fail_cond)
        .group_by(LoginSecurityEvent.ip)
        .order_by(func.count(LoginSecurityEvent.id).desc())
        .limit(10)
    )
    top_id_rows = await db.execute(
        select(LoginSecurityEvent.identifier, func.count(LoginSecurityEvent.id))
        .where(*fail_cond, LoginSecurityEvent.identifier.is_not(None))
        .group_by(LoginSecurityEvent.identifier)
        .order_by(func.count(LoginSecurityEvent.id).desc())
        .limit(10)
    )
    return {
        "hours": hours,
        "by_kind": by_kind,
        "failures": sum(by_kind.get(k, 0) for k in FAILURE_KINDS),
        "top_ips": [{"ip": ip, "count": int(c), "identifiers": int(d)} for ip, c, d in top_ip_rows.all()],
        "top_identifiers": [{"identifier": i, "count": int(c)} for i, c in top_id_rows.all()],
        "labels": EVENT_LABELS,
    }


async def cleanup(db: AsyncSession) -> tuple[int, int]:
    """حذف رویدادهای قدیمی‌تر از retention_days و چالش‌های منقضی کپچا. خروجی: (رویداد، کپچا)."""
    cfg = await get_login_security_settings(db)
    now = datetime.now(timezone.utc)
    ev = await db.execute(delete(LoginSecurityEvent).where(LoginSecurityEvent.created_at < now - timedelta(days=cfg.retention_days)))
    cap = await db.execute(delete(CaptchaChallenge).where(CaptchaChallenge.expires_at < now))
    await db.commit()
    return ev.rowcount or 0, cap.rowcount or 0
