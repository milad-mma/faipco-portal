"""
Endpointهای احراز هویت (Authentication).
- login: فرم ورود یکپارچه برای کاربران مدیریت و پرسنل؛ refresh: تمدید توکن.
- me / me/password / me/contact-info: اطلاعات، رمز عبور و اطلاعات تماس کاربر جاری.
- forgot-password / verify-reset-code / reset-password: جریان بازنشانی رمز عبور با ایمیل یا پیامک.
"""
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
    VerifyResetCodeRequest,
)
from app.schemas.user import UserOut
from app.services.auth_service import AuthError, AuthIpBlockedError, AuthLockedError, AuthService
from app.services.email_service import EmailError, EmailNotConfiguredError
from app.services.employee_contact_service import ContactInfoUpdateError, update_my_contact_info
from app.services.password_reset_service import (
    PasswordResetError,
    request_reset,
    reset_password,
    verify_reset_token,
)
from app.services.sms_service import SmsError, SmsNotConfiguredError

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    ورود یکپارچه: username/password برای مدیریت (یوزرنیم + رمز) و پرسنل (کد پرسنلی + کد ملی)؛ تشخیص در AuthService.login().
    دسترسی: عمومی. خروجی: access و refresh token.
    خطاها: 403 (IP مجاز نیست)، 429 (قفل موقت، با هدر Retry-After)، 401 (اطلاعات نادرست).
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
    """
    با refresh token معتبر، جفت توکن جدید (access + refresh) صادر می‌کند.
    دسترسی: عمومی (نیازمند refresh token). خطا: 401 اگر توکن نامعتبر یا منقضی باشد.
    """
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
    """اطلاعات کامل کاربر جاری (UserOut) را برمی‌گرداند. دسترسی: هر کاربر واردشده."""
    return await AuthService(db).get_me(current_user)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    رمز عبور کاربر جاری را پس از بررسی رمز فعلی تغییر می‌دهد (پاسخ 204).
    دسترسی: هر کاربر واردشده. خطا: 400 اگر رمز فعلی نادرست یا رمز جدید نامعتبر باشد.
    """
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
    ایمیل/موبایل کاربر جاری را به‌روزرسانی می‌کند؛ اگر ستون متناظر در نگاشت ستون‌های سایت پرسنل
    تنظیم شده باشد، در دیتابیس اصلی سایت هم نوشته می‌شود (write-back)، وگرنه فقط در دیتابیس پرتال.
    دسترسی: هر کاربر واردشده. خطا: 400 برای مقدار نامعتبر یا خطای ذخیره.
    """
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
    درخواست بازنشانی رمز: لینک (ایمیل) یا کد ۶ رقمی (پیامک) می‌فرستد. دسترسی: عمومی.
    همیشه masked_contact و expires_in_seconds برمی‌گرداند، حتی برای شناسه‌ی نامعتبر (ماسک ساختگی)،
    تا وجود حساب قابل تشخیص نباشد. خطا: 503 فقط اگر سرویس ایمیل/پیامک تنظیم‌نشده یا قطع باشد.
    """
    settings = get_settings()
    reset_link_base = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password"  # آدرس صفحه‌ی بازنشانی در فرانت‌اند
    try:
        result = await request_reset(db, payload.identifier, payload.channel, reset_link_base)
    except (EmailNotConfiguredError, EmailError, SmsNotConfiguredError, SmsError) as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

    # masked_contact جدا از متن پیام برگردانده می‌شود تا فرانت‌اند آن را با جهت LTR نمایش دهد
    # (درج اعداد/ایمیل لاتین وسط جمله‌ی فارسی RTL باعث به‌هم‌ریختگی نمایش دوجهته می‌شود)
    if payload.channel == "sms":
        message = "کد تأیید بازنشانی رمز عبور به شماره زیر پیامک شد."
    else:
        message = "لینک بازنشانی رمز عبور به آدرس زیر ارسال شد. لطفاً صندوق ایمیل خود را بررسی کنید."

    return {
        "message": message,
        "masked_contact": result.masked_contact,
        "expires_in_seconds": result.expires_in_seconds,
    }


@router.post("/verify-reset-code")
async def verify_reset_code_endpoint(
    payload: VerifyResetCodeRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    """
    اعتبار کد/توکن بازنشانی را بدون مصرف آن بررسی می‌کند (در جریان پیامکی، پیش از نمایش فرم رمز جدید).
    دسترسی: عمومی، با قفل موقت بر اساس IP در برابر Brute-force.
    خطاها: 429 (قفل موقت)، 400 (کد نامعتبر یا منقضی).
    """
    client_ip = get_client_ip(request)
    lockout_key = f"reset-password:{client_ip}"  # کلید قفل مشترک با reset-password
    # اگر این IP در حال حاضر قفل باشد، درخواست رد می‌شود
    locked_remaining = await check_login_lockout(db, lockout_key)
    if locked_remaining is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"تعداد تلاش‌های ناموفق زیاد بوده است. لطفاً {int(locked_remaining) + 1} ثانیه دیگر تلاش کنید.",
        )

    # بررسی کد؛ در صورت شکست، یک تلاش ناموفق برای این IP ثبت می‌شود
    try:
        await verify_reset_token(db, payload.token)
    except PasswordResetError as e:
        await record_failed_login(db, lockout_key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await reset_login_attempts(db, lockout_key)  # موفقیت: شمارنده‌ی تلاش‌ها صفر می‌شود
    return {"message": "کد تأیید معتبر است."}


@router.post("/reset-password")
async def reset_password_endpoint(
    payload: ResetPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    """
    با کد/توکن معتبر، رمز عبور جدید را ثبت می‌کند و توکن را مصرف می‌کند. دسترسی: عمومی.
    قفل موقت بر اساس IP (زیرساخت app/core/rate_limit.py، امن برای چند worker) از حدس کد ۶ رقمی پیامکی جلوگیری می‌کند.
    خطاها: 429 (قفل موقت)، 400 (توکن نامعتبر/منقضی یا رمز نامعتبر).
    """
    client_ip = get_client_ip(request)
    lockout_key = f"reset-password:{client_ip}"
    # اگر این IP در حال حاضر قفل باشد، درخواست رد می‌شود
    locked_remaining = await check_login_lockout(db, lockout_key)
    if locked_remaining is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"تعداد تلاش‌های ناموفق زیاد بوده است. لطفاً {int(locked_remaining) + 1} ثانیه دیگر تلاش کنید.",
        )

    # تغییر رمز؛ در صورت شکست، یک تلاش ناموفق برای این IP ثبت می‌شود
    try:
        await reset_password(db, payload.token, payload.new_password)
    except PasswordResetError as e:
        await record_failed_login(db, lockout_key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await reset_login_attempts(db, lockout_key)
    return {"message": "رمز عبور با موفقیت تغییر کرد. اکنون می‌توانید وارد شوید."}
