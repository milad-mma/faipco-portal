"""Endpoint های Authentication: یک فرم ورود یکپارچه برای مدیریت و پرسنل، refresh، دریافت اطلاعات کاربر جاری."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.ip_allowlist import get_client_ip
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.user import UserOut
from app.services.auth_service import AuthError, AuthIpBlockedError, AuthLockedError, AuthService
from app.services.email_service import EmailError, EmailNotConfiguredError
from app.services.password_reset_service import PasswordResetError, request_reset, reset_password

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    فرم ورود یکپارچه: همان دو فیلد (username/password) هم برای مدیریت
    (یوزرنیم + رمز عبور) و هم برای پرسنل (کد پرسنلی + کد ملی) کار می‌کند —
    منطق تشخیص در AuthService.login() انجام می‌شود.
    """
    service = AuthService(db)
    try:
        access_token, refresh_token = await service.login(
            payload.username, payload.password, client_ip=get_client_ip(request)
        )
    except AuthIpBlockedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except AuthLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": str(e.retry_after_seconds)},
        )
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    try:
        access_token, new_refresh_token = await service.refresh(payload.refresh_token)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.get("/me", response_model=UserOut)
async def read_current_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await AuthService(db).get_me(current_user)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    try:
        await service.change_password(current_user, payload.current_password, payload.new_password)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    ⚠️ امنیتی: همیشه یک پیام یکسان برمی‌گرداند - چه شناسه واردشده وجود
    داشته باشد چه نه، و چه ایمیلی برایش ثبت شده باشد چه نه - تا این
    Endpoint نتواند برای حدس‌زدن نام‌کاربری/کدپرسنلی معتبر استفاده شود.
    فقط اگر خودِ سرویس ایمیل قطع/تنظیم‌نشده باشد، خطای واقعی نشان داده
    می‌شود (چون آن یک مشکل پیکربندی سیستم است، نه اطلاعاتی درباره این کاربر).
    """
    settings = get_settings()
    reset_link_base = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password"
    try:
        await request_reset(db, payload.identifier, reset_link_base)
    except (EmailNotConfiguredError, EmailError) as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return {
        "message": "اگر این شناسه در سامانه ثبت شده و ایمیلی برایش موجود باشد، لینک بازنشانی رمز عبور ارسال شد."
    }


@router.post("/reset-password")
async def reset_password_endpoint(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    try:
        await reset_password(db, payload.token, payload.new_password)
    except PasswordResetError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "رمز عبور با موفقیت تغییر کرد. اکنون می‌توانید وارد شوید."}
