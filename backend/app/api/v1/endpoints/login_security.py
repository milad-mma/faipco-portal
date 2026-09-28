"""
Endpointهای «امنیت ورود» (مجوز system.login_security، کل سیستم):
- GET/PUT  /settings        تنظیمات قفل پلکانی، محدودیت IP، IPهای معاف، کپچا، هشدار و نگهداری گزارش
- GET      /locks           قفل‌های فعال (شناسه، IP، بازیابی رمز)
- POST     /unlock          رفع یک قفل (برای IP رویدادهای اخیرش هم از شمارش سقف IP خارج می‌شوند)
- GET      /events          گزارش رویدادها (فیلتر نوع، جست‌وجوی IP/شناسه، بازه‌ی ساعت)
- GET      /summary         خلاصه‌ی بازه: شمارش هر نوع، پرتکرارترین IPها و شناسه‌ها
رفع قفل ورود یک پرسنل از صفحه‌ی پرسنل: POST /employees/{id}/unlock-login (users.manage برای سایت او).
"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.login_security import LockOut, LoginSecurityEventOut, LoginSecuritySettings, UnlockRequest
from app.services import login_security_service as svc

router = APIRouter()
PERM = svc.PERMISSION_CODE


@router.get("/settings", response_model=LoginSecuritySettings)
async def get_settings_endpoint(db: AsyncSession = Depends(get_db), _u: User = Depends(require_permission(PERM))):
    """تنظیمات فعلی امنیت ورود (پیش‌فرض‌ها اگر ذخیره نشده باشد)."""
    return await svc.get_login_security_settings(db)


@router.put("/settings", response_model=LoginSecuritySettings)
async def put_settings_endpoint(
    payload: LoginSecuritySettings, db: AsyncSession = Depends(get_db), _u: User = Depends(require_permission(PERM))
):
    """ذخیره‌ی تنظیمات؛ از درخواست ورود بعدی اعمال می‌شود (قفل‌های فعلی با مدت قبلی تمام می‌شوند)."""
    return await svc.save_login_security_settings(db, payload)


@router.get("/locks", response_model=list[LockOut])
async def list_locks_endpoint(db: AsyncSession = Depends(get_db), _u: User = Depends(require_permission(PERM))):
    """قفل‌های فعال در همین لحظه."""
    return await svc.list_active_locks(db)


@router.post("/unlock", status_code=status.HTTP_204_NO_CONTENT)
async def unlock_endpoint(
    payload: UnlockRequest, db: AsyncSession = Depends(get_db), _u: User = Depends(require_permission(PERM))
):
    """رفع یک قفل با کلید برگشتی از /locks."""
    await svc.unlock_key(db, payload.key)


@router.get("/events")
async def list_events_endpoint(
    kind: str | None = Query(default=None, max_length=30),
    search: str | None = Query(default=None, max_length=100),
    hours: int = Query(default=24, ge=1, le=24 * 730),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _u: User = Depends(require_permission(PERM)),
):
    """گزارش رویدادها، جدیدترین اول. خروجی: {items, total, labels}."""
    items, total = await svc.list_events(db, kind, search, hours, limit, offset)
    return {
        "items": [LoginSecurityEventOut.model_validate(e) for e in items],
        "total": total,
        "labels": svc.EVENT_LABELS,
    }


@router.get("/summary")
async def summary_endpoint(
    hours: int = Query(default=24, ge=1, le=24 * 730),
    db: AsyncSession = Depends(get_db),
    _u: User = Depends(require_permission(PERM)),
):
    """خلاصه‌ی بازه به‌همراه تعداد قفل‌های فعال."""
    data = await svc.summary(db, hours)
    locks = await svc.list_active_locks(db)
    data["active_locks"] = {
        "identifier": sum(1 for x in locks if x["kind"] == "identifier"),
        "ip": sum(1 for x in locks if x["kind"] == "ip"),
        "reset": sum(1 for x in locks if x["kind"] == "reset"),
    }
    return data
