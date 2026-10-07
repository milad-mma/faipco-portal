"""
گزارش خطاها (docs/error-logs.md). مجوز system.logs (کل سیستم) برای همه به‌جز POST /client.

- GET    /error-logs                    فهرست گروه‌های خطا (فیلتر نوع، بخش، وضعیت، جست‌وجو، کد پیگیری) + خلاصه
- GET    /error-logs/{id}               جزئیات یک گروه + آخرین رخدادها
- POST   /error-logs/{id}/resolve       «حل شد» (با رخداد دوباره، خودکار باز می‌شود)
- POST   /error-logs/{id}/reopen
- POST   /error-logs/resolve-all        همه‌ی موارد باز (با همان فیلترها) حل‌شده
- GET/PUT /error-logs/settings          ایمیل هشدار (روشن/خاموش، گیرندگان) + آماده بودن SMTP
- POST   /error-logs/settings/test      ایمیل آزمایشی
- POST   /error-logs/client             گزارش خطای مرورگر (بدون نیاز به ورود؛ سقف تعداد به‌ازای هر IP)
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.core.ip_allowlist import get_client_ip
from app.core.security import decode_token
from app.db.session import get_db
from app.models.error_log import ErrorLog, ErrorLogOccurrence
from app.models.user import User
from app.services import error_log_service as svc

router = APIRouter()
PERMISSION = "system.logs"


def _item(row: ErrorLog, with_detail: bool = False) -> dict:
    data = {
        "id": row.id,
        "kind": row.kind,
        "kind_label": svc.KIND_LABELS.get(row.kind, row.kind),
        "category": row.category,
        "category_label": svc.CATEGORY_LABELS.get(row.category, row.category),
        "source": row.source,
        "message": row.message,
        "hint": svc.hint_for(row.kind, row.category, row.message),
        "count": row.count,
        "first_seen": row.first_seen,
        "last_seen": row.last_seen,
        "last_request": row.last_request,
        "last_user_label": row.last_user_label,
        "last_ip": row.last_ip,
        "last_context": row.last_context,
        "resolved": row.resolved_at is not None,
        "resolved_at": row.resolved_at,
    }
    if with_detail:
        data["detail"] = row.detail
    return data


def _filters(kind: str | None, category: str | None, state: str, q: str | None, since_hours: int | None) -> list:
    conds = []
    if kind:
        conds.append(ErrorLog.kind == kind)
    if category:
        conds.append(ErrorLog.category == category)
    if state == "open":
        conds.append(ErrorLog.resolved_at.is_(None))
    elif state == "resolved":
        conds.append(ErrorLog.resolved_at.is_not(None))
    if since_hours:
        conds.append(ErrorLog.last_seen >= datetime.now(timezone.utc) - timedelta(hours=since_hours))
    if q:
        text = q.strip()
        like = f"%{text}%"
        # کد پیگیری (۶ حرف هگز) هم جست‌وجو می‌شود
        by_request = select(ErrorLogOccurrence.error_id).where(ErrorLogOccurrence.request_id == text.upper())
        conds.append(
            or_(
                ErrorLog.message.ilike(like),
                ErrorLog.source.ilike(like),
                ErrorLog.last_request.ilike(like),
                ErrorLog.last_user_label.ilike(like),
                ErrorLog.id.in_(by_request),
            )
        )
    return conds


@router.get("")
async def list_errors(
    kind: str | None = Query(default=None, pattern="^(error|slow|client|android)$"),
    category: str | None = Query(default=None, max_length=32),
    state: str = Query(default="open", pattern="^(open|resolved|all)$"),
    q: str | None = Query(default=None, max_length=200),
    since_hours: int | None = Query(default=None, ge=1, le=24 * 31),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(PERMISSION)),
):
    conds = _filters(kind, category, state, q, since_hours)
    total = (await db.execute(select(func.count()).select_from(ErrorLog).where(*conds))).scalar_one()
    rows = (
        await db.execute(
            select(ErrorLog).where(*conds).order_by(ErrorLog.last_seen.desc()).limit(page_size).offset((page - 1) * page_size)
        )
    ).scalars().all()
    # خلاصه: موارد باز ۲۴ ساعت اخیر به‌تفکیک نوع
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    summary_rows = (
        await db.execute(
            select(ErrorLog.kind, func.count(), func.coalesce(func.sum(ErrorLog.count), 0))
            .where(ErrorLog.resolved_at.is_(None), ErrorLog.last_seen >= day_ago)
            .group_by(ErrorLog.kind)
        )
    ).all()
    summary = {k: {"groups": int(g), "occurrences": int(c)} for k, g, c in summary_rows}
    categories = [{"key": k, "label": v} for k, v in svc.CATEGORY_LABELS.items()]
    return {
        "items": [_item(r) for r in rows],
        "total": int(total),
        "summary": summary,
        "categories": categories,
        "kinds": [{"key": k, "label": v} for k, v in svc.KIND_LABELS.items()],
        "retention_days": svc.RETENTION_DAYS,
    }


class AlertSettingsIn(BaseModel):
    enabled: bool = True
    recipients: list[str] = Field(default_factory=list, max_length=10)


@router.get("/settings")
async def get_settings_endpoint(
    db: AsyncSession = Depends(get_db), _user: User = Depends(require_permission(PERMISSION))
):
    cfg = await svc.get_alert_settings(db)
    return {**cfg, "smtp_ready": await svc.smtp_ready(db), "slow_request_seconds": svc.SLOW_REQUEST_SECONDS}


@router.put("/settings")
async def put_settings_endpoint(
    payload: AlertSettingsIn,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(PERMISSION)),
):
    try:
        cfg = await svc.save_alert_settings(db, payload.enabled, payload.recipients)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {**cfg, "smtp_ready": await svc.smtp_ready(db), "slow_request_seconds": svc.SLOW_REQUEST_SECONDS}


@router.post("/settings/test")
async def test_alert_email(db: AsyncSession = Depends(get_db), _user: User = Depends(require_permission(PERMISSION))):
    from app.services.email_service import EmailError, send_email

    cfg = await svc.get_alert_settings(db)
    if not cfg["recipients"]:
        raise HTTPException(status_code=400, detail="هیچ گیرنده‌ای تعریف نشده است.")
    if not await svc.smtp_ready(db):
        raise HTTPException(status_code=400, detail="ایمیل (SMTP) در تنظیمات سامانه فعال یا کامل نیست.")
    try:
        for address in cfg["recipients"]:
            await send_email(
                db,
                to_address=address,
                subject="ایمیل آزمایشی هشدار خطاهای پرتال",
                body_text="این یک ایمیل آزمایشی است. از این پس خطاهای جدید پرتال به همین آدرس فرستاده می‌شوند.",
            )
    except EmailError as e:
        raise HTTPException(status_code=400, detail=f"ارسال ناموفق بود: {e}")
    return {"sent": len(cfg["recipients"])}


@router.post("/resolve-all")
async def resolve_all(
    kind: str | None = Query(default=None, pattern="^(error|slow|client|android)$"),
    category: str | None = Query(default=None, max_length=32),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission(PERMISSION)),
):
    conds = _filters(kind, category, "open", None, None)
    result = await db.execute(
        update(ErrorLog).where(*conds).values(resolved_at=datetime.now(timezone.utc), resolved_by_user_id=user.id)
    )
    await db.commit()
    return {"resolved": result.rowcount or 0}


# ---------------------------------------------------------------- گزارش خطای مرورگر (بدون ورود)

_client_hits: dict[str, deque] = defaultdict(deque)
_CLIENT_LIMIT_PER_MINUTE = 30


class ClientErrorIn(BaseModel):
    type: str = Field(default="error", pattern="^(error|crash|network)$")
    message: str = Field(max_length=2000)
    stack: str | None = Field(default=None, max_length=12000)
    page: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default=None, max_length=200)
    api: str | None = Field(default=None, max_length=300)
    request_id: str | None = Field(default=None, max_length=16)
    app_version: str | None = Field(default=None, max_length=40)
    in_android_app: bool = False


@router.post("/client", status_code=status.HTTP_204_NO_CONTENT)
async def report_client_error(payload: ClientErrorIn, request: Request, db: AsyncSession = Depends(get_db)):
    """خطای مرورگر کاربر؛ کاربر (اگر واردشده باشد) از توکن خوانده می‌شود. بیش از سقف در دقیقه نادیده گرفته می‌شود."""
    ip = get_client_ip(request)
    now = time.monotonic()
    hits = _client_hits[ip]
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= _CLIENT_LIMIT_PER_MINUTE:
        return None
    hits.append(now)
    if len(_client_hits) > 5000:  # جلوگیری از رشد بی‌پایان حافظه
        _client_hits.clear()

    user_ref = None
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        data = decode_token(auth[7:].strip())
        if data and data.get("type") == "access" and str(data.get("sub", "")).isdigit():
            user = await db.get(User, int(data["sub"]))
            if user is not None:
                user_ref = (user.id, user.username)
    svc.record_client_error(payload.model_dump(), user_ref, ip, request.headers.get("user-agent"))
    return None


# ---------------------------------------------------------------- جزئیات (مسیرهای با شناسه در آخر)


@router.get("/{error_id}")
async def get_error(
    error_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require_permission(PERMISSION))
):
    row = await db.get(ErrorLog, error_id)
    if row is None:
        raise HTTPException(status_code=404, detail="یافت نشد")
    occurrences = (
        await db.execute(
            select(ErrorLogOccurrence)
            .where(ErrorLogOccurrence.error_id == error_id)
            .order_by(ErrorLogOccurrence.occurred_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return {
        **_item(row, with_detail=True),
        "occurrences": [
            {
                "occurred_at": o.occurred_at,
                "request_id": o.request_id,
                "request": o.request,
                "user_label": o.user_label,
                "ip": o.ip,
                "context": o.context,
            }
            for o in occurrences
        ],
    }


@router.post("/{error_id}/resolve")
async def resolve_error(
    error_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_permission(PERMISSION))
):
    row = await db.get(ErrorLog, error_id)
    if row is None:
        raise HTTPException(status_code=404, detail="یافت نشد")
    row.resolved_at = datetime.now(timezone.utc)
    row.resolved_by_user_id = user.id
    await db.commit()
    return _item(row)


@router.post("/{error_id}/reopen")
async def reopen_error(
    error_id: int, db: AsyncSession = Depends(get_db), _user: User = Depends(require_permission(PERMISSION))
):
    row = await db.get(ErrorLog, error_id)
    if row is None:
        raise HTTPException(status_code=404, detail="یافت نشد")
    row.resolved_at = None
    row.resolved_by_user_id = None
    await db.commit()
    return _item(row)
