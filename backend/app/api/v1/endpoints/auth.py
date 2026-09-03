"""Endpoint های Authentication: یک فرم ورود یکپارچه برای مدیریت و پرسنل، refresh، دریافت اطلاعات کاربر جاری."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.ip_allowlist import get_client_ip
from app.core.rate_limit import check_login_lockout, record_failed_login, reset_login_attempts
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ContactInfoUpdateRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.user import UserOut
from app.services.auth_service import AuthError, AuthIpBlockedError, AuthLockedError, AuthService
from app.services.email_service import EmailError, EmailNotConfiguredError
from app.services.employee_contact_service import ContactInfoUpdateError, update_my_contact_info
from app.services.password_reset_service import PasswordResetError, request_reset, reset_password
from app.services.sms_service import SmsError, SmsNotConfiguredError

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


@router.put("/me/contact-info")
async def update_my_contact_info_endpoint(
    payload: ContactInfoUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    اگر برای سایت این پرسنل، ستون ایمیل/موبایل در نگاشت ستون‌ها تنظیم شده
    باشد، مقدار جدید در دیتابیس اصلی همان سایت هم به‌روزرسانی می‌شود
    (Write-back)؛ وگرنه فقط در دیتابیس داخلی پرتال ذخیره می‌شود.
    """
    if payload.email is None and payload.mobile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="حداقل یکی از ایمیل یا موبایل باید وارد شود")
    try:
        result = await update_my_contact_info(db, current_user, email=payload.email, mobile=payload.mobile)
    except ContactInfoUpdateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return result


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    """
    ⚠️ امنیتی: طبق درخواست صریح، همیشه یک نسخه ناقص از مخاطب
    (masked_contact) و زمان انقضا (expires_in_seconds) برگردانده
    می‌شود - چه شناسه معتبر باشد چه نه (برای شناسه نامعتبر، یک ماسک
    قلابی ولی باورپذیر تولید می‌شود) - نگاه کنید به توضیح کامل در
    docstring بالای app/services/password_reset_service.py. فقط اگر
    خودِ سرویس ایمیل/پیامک قطع/تنظیم‌نشده باشد، خطای واقعی نشان داده
    می‌شود.
    """
    settings = get_settings()
    reset_link_base = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password"
    try:
        result = await request_reset(db, payload.identifier, payload.channel, reset_link_base)
    except (EmailNotConfiguredError, EmailError, SmsNotConfiguredError, SmsError) as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

    if payload.channel == "sms":
        message = f"کد تأیید بازنشانی رمز عبور به شماره {result.masked_contact} پیامک شد."
    else:
        message = (
            f"لینک بازنشانی رمز عبور به آدرس {result.masked_contact} ارسال شد. لطفاً صندوق ایمیل خود را بررسی کنید."
        )

    return {
        "message": message,
        "masked_contact": result.masked_contact,
        "expires_in_seconds": result.expires_in_seconds,
    }


@router.post("/reset-password")
async def reset_password_endpoint(
    payload: ResetPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    """
    ⚠️ محافظت در برابر Brute-force: مهم‌ترین کاربرد این محافظت، کد ۶ رقمی
    پیامکی است (فقط یک‌میلیون حالت ممکن، برخلاف توکن ایمیل که یک رشته
    تصادفی طولانی و عملاً غیرقابل‌حدس است) - از همان زیرساخت قفل موقت
    ورود (app/core/rate_limit.py، امن در برابر چند Worker) استفاده
    می‌شود، این‌بار کلید‌شده بر اساس IP کلاینت به‌جای نام‌کاربری.
    """
    client_ip = get_client_ip(request)
    lockout_key = f"reset-password:{client_ip}"
    locked_remaining = await check_login_lockout(db, lockout_key)
    if locked_remaining is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"تعداد تلاش‌های ناموفق زیاد بوده — لطفاً {int(locked_remaining) + 1} ثانیه دیگر دوباره تلاش کنید.",
        )

    try:
        await reset_password(db, payload.token, payload.new_password)
    except PasswordResetError as e:
        await record_failed_login(db, lockout_key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await reset_login_attempts(db, lockout_key)
    return {"message": "رمز عبور با موفقیت تغییر کرد. اکنون می‌توانید وارد شوید."}
