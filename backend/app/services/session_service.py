"""
سرویس نشست‌های دستگاه (Migration 115؛ docs/login-security.md «دستگاه‌های من»).

- ورود موفق → create_session: ردیف user_sessions با sid تازه؛ اگر تعداد نشست‌های فعال کاربر به سقف رسیده باشد
  (users.max_sessions یا تنظیمات امنیت ورود؛ ۱ تا ۳)، قدیمی‌ترین نشست (بر اساس آخرین فعالیت) با دلیل «limit» باطل
  می‌شود تا دستگاه جدید جای آن را بگیرد.
- هر درخواست → validate: نشست باید وجود داشته و باطل نشده باشد؛ «آخرین فعالیت» حداکثر هر ۵ دقیقه یک بار به‌روز می‌شود.
- خروج (logout) فقط همان sid را باطل می‌کند؛ ابطال از راه دور (کاربر از دستگاه دیگر یا ادمین) هم همین کار را می‌کند
  و دستگاه باطل‌شده در درخواست بعدی 401 می‌گیرد و به صفحه‌ی ورود می‌رود.
- تغییر رمز / بازنشانی توسط ادمین / غیرفعال‌سازی → revoke_all (به‌جز نشست جاری در تغییر رمز توسط خودِ کاربر).
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.employee import Employee
from app.models.user import User
from app.models.user_session import UserSession

logger = logging.getLogger(__name__)

TOUCH_INTERVAL = timedelta(minutes=5)  # حداقل فاصله‌ی به‌روزرسانی last_seen_at (کاهش نوشتن در هر درخواست)
MIN_SESSIONS, MAX_SESSIONS, DEFAULT_MAX_SESSIONS = 1, 3, 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


def device_label(user_agent: str | None, client_app: str | None = None) -> str:
    """برچسب کوتاه و فارسی دستگاه از User-Agent (مثل «Chrome روی Windows»، «اپ اندروید»، «Safari روی iPhone»)."""
    ua = user_agent or ""
    low = ua.lower()
    if client_app == "android":
        return "اپ اندروید"
    if "iphone" in low:
        os_name = "iPhone"
    elif "ipad" in low:
        os_name = "iPad"
    elif "android" in low:
        os_name = "Android"
    elif "windows" in low:
        os_name = "Windows"
    elif "mac os" in low or "macintosh" in low:
        os_name = "Mac"
    elif "linux" in low:
        os_name = "Linux"
    else:
        os_name = ""
    if "edg/" in low or "edge/" in low:
        browser = "Edge"
    elif "opr/" in low or "opera" in low:
        browser = "Opera"
    elif "samsungbrowser" in low:
        browser = "Samsung Internet"
    elif "firefox" in low:
        browser = "Firefox"
    elif "chrome" in low or "crios" in low:
        browser = "Chrome"
    elif "safari" in low:
        browser = "Safari"
    elif re.search(r"okhttp|python|curl|dart", low):
        browser = "برنامه"
    else:
        browser = "مرورگر"
    return f"{browser} روی {os_name}" if os_name else browser


async def effective_limit(db: AsyncSession, user: User) -> int:
    """سقف نشست هم‌زمان این کاربر: مقدار اختصاصی یا پیش‌فرض تنظیمات امنیت ورود، محدود به ۱..۳."""
    limit = user.max_sessions
    if limit is None:
        from app.services.login_security_service import get_login_security_settings

        try:
            limit = (await get_login_security_settings(db)).max_sessions
        except Exception:  # noqa: BLE001 - تنظیمات خراب نباید ورود را بشکند
            limit = DEFAULT_MAX_SESSIONS
    return max(MIN_SESSIONS, min(MAX_SESSIONS, int(limit or DEFAULT_MAX_SESSIONS)))


async def active_sessions(db: AsyncSession, user_id: int) -> list[UserSession]:
    rows = (
        await db.execute(
            select(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .order_by(UserSession.last_seen_at.desc())
        )
    ).scalars().all()
    return list(rows)


async def create_session(
    db: AsyncSession,
    user: User,
    *,
    ip: str | None,
    user_agent: str | None,
    client_app: str | None,
    enforce_limit: bool = True,
) -> UserSession:
    """
    نشست تازه برای یک ورود موفق (بدون commit؛ فراخواننده commit می‌کند). اگر به سقف رسیده باشد، قدیمی‌ترین
    نشست‌های فعال با دلیل «limit» باطل می‌شوند. نشست‌های کهنه (بی‌فعالیت بیش از عمر رفرش‌توکن) هم باطل می‌شوند.
    enforce_limit=False برای مهاجرت بی‌صدای توکن‌های قدیمی (بدون sid) در تمدید: هیچ دستگاهی خارج نمی‌شود.
    """
    now = _now()
    stale_before = now - timedelta(days=get_settings().REFRESH_TOKEN_EXPIRE_DAYS)
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None), UserSession.last_seen_at < stale_before)
        .values(revoked_at=now, revoked_reason="expired")
    )
    if enforce_limit:
        limit = await effective_limit(db, user)
        current = await active_sessions(db, user.id)  # مرتب از جدیدترین فعالیت
        if len(current) >= limit:
            for old in current[limit - 1 :]:
                old.revoked_at = now
                old.revoked_reason = "limit"
    session = UserSession(
        user_id=user.id,
        sid=str(uuid.uuid4()),
        device_label=device_label(user_agent, client_app)[:120],
        user_agent=(user_agent or "")[:300] or None,
        client_app=(client_app or None),
        ip=(ip or "")[:64] or None,
        created_at=now,
        last_seen_at=now,
    )
    db.add(session)
    await db.flush()
    return session


async def validate(db: AsyncSession, user_id: int, sid: str | None, *, ip: str | None = None) -> UserSession | None:
    """
    نشست فعال با این sid برای این کاربر؛ None اگر نباشد یا باطل شده باشد. «آخرین فعالیت» و IP را (حداکثر هر
    ۵ دقیقه) به‌روز می‌کند و commit کوچکی می‌زند.
    """
    if not sid:
        return None
    session = (
        await db.execute(select(UserSession).where(UserSession.sid == sid, UserSession.user_id == user_id))
    ).scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        return None
    now = _now()
    last = session.last_seen_at if session.last_seen_at.tzinfo else session.last_seen_at.replace(tzinfo=timezone.utc)
    if now - last >= TOUCH_INTERVAL or (ip and ip != session.ip):
        try:
            # Savepoint تا شکست این به‌روزرسانی آماری فقط همین بخش را برگرداند، نه کل Session (و اشیای بارگذاری‌شده‌ی آن)
            async with db.begin_nested():
                await db.execute(
                    update(UserSession)
                    .where(UserSession.id == session.id)
                    .values(last_seen_at=now, ip=(ip or session.ip or "")[:64] or None)
                )
            await db.commit()
        except Exception:  # noqa: BLE001 - به‌روزرسانی آماری نباید درخواست را خراب کند
            logger.debug("به‌روزرسانی last_seen نشست ناموفق بود", exc_info=True)
    return session


async def revoke(db: AsyncSession, session_id: int, *, user_id: int | None, reason: str) -> bool:
    """یک نشست را باطل می‌کند (اگر user_id داده شود فقط نشست همان کاربر). بدون commit. خروجی: پیدا و باطل شد؟"""
    stmt = update(UserSession).where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
    if user_id is not None:
        stmt = stmt.where(UserSession.user_id == user_id)
    result = await db.execute(stmt.values(revoked_at=_now(), revoked_reason=reason))
    return (result.rowcount or 0) > 0


async def revoke_by_sid(db: AsyncSession, sid: str | None, *, reason: str) -> None:
    if not sid:
        return
    await db.execute(
        update(UserSession)
        .where(UserSession.sid == sid, UserSession.revoked_at.is_(None))
        .values(revoked_at=_now(), revoked_reason=reason)
    )


async def revoke_all(db: AsyncSession, user_id: int, *, reason: str, except_sid: str | None = None) -> int:
    """همه‌ی نشست‌های فعال کاربر (به‌جز except_sid) را باطل می‌کند. بدون commit. خروجی: تعداد."""
    stmt = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if except_sid:
        stmt = stmt.where(UserSession.sid != except_sid)
    result = await db.execute(stmt.values(revoked_at=_now(), revoked_reason=reason))
    return result.rowcount or 0


def to_dict(session: UserSession, *, current_sid: str | None = None) -> dict:
    return {
        "id": session.id,
        "device": session.device_label,
        "client_app": session.client_app,
        "ip": session.ip,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "last_seen_at": session.last_seen_at.isoformat() if session.last_seen_at else None,
        "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
        "revoked_reason": session.revoked_reason,
        "current": bool(current_sid and session.sid == current_sid),
    }


async def list_admin(
    db: AsyncSession, *, search: str | None, only_active: bool, page: int, page_size: int
) -> dict:
    """فهرست نشست‌ها برای پنل «امنیت ورود» با نام کاربر/پرسنل، جست‌وجو (نام کاربری، نام، کد پرسنلی، IP) و صفحه‌بندی."""
    stmt = (
        select(UserSession, User, Employee)
        .join(User, User.id == UserSession.user_id)
        .outerjoin(Employee, Employee.id == User.employee_id)
    )
    if only_active:
        stmt = stmt.where(UserSession.revoked_at.is_(None))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            User.username.ilike(like)
            | Employee.first_name.ilike(like)
            | Employee.last_name.ilike(like)
            | Employee.personnel_code.ilike(like)
            | UserSession.ip.ilike(like)
        )
    total = (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(UserSession.last_seen_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).all()
    items = []
    for session, user, employee in rows:
        item = to_dict(session)
        item.update(
            {
                "user_id": user.id,
                "username": user.username,
                "employee": f"{employee.first_name} {employee.last_name} ({employee.personnel_code})" if employee else None,
                "max_sessions": user.max_sessions,
            }
        )
        items.append(item)
    return {"items": items, "total": total}
