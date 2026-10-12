"""
Endpointهای احراز هویت (Authentication).
- login: فرم ورود یکپارچه برای کاربران مدیریت و پرسنل؛ refresh: تمدید توکن.
- me / me/password / me/contact-info: اطلاعات، رمز عبور و اطلاعات تماس کاربر جاری.
- me/password/otp-options، me/password/otp، me/mobile/otp: کد تأیید یک‌بارمصرف برای تغییر رمز و موبایل.
- forgot-password / verify-reset-code / reset-password: جریان بازنشانی رمز عبور با ایمیل یا پیامک.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.ip_allowlist import get_client_ip
from app.core.rate_limit import check_login_lockout, record_failed_login, reset_login_attempts
from app.services import login_security_service as login_security
from app.db.session import get_db
from app.models.employee import Employee
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ContactInfoUpdateRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MobileOtpRequest,
    PasswordOtpRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyResetCodeRequest,
)
from app.schemas.user import UserOut
from app.services.auth_service import AuthError, AuthIpBlockedError, AuthLockedError, AuthService
from app.services.employee_contact_service import ContactInfoUpdateError, normalize_mobile, update_my_contact_info
from app.core.security import check_password_strength
from app.services import otp_service
from app.services.password_reset_service import (
    PasswordResetError,
    is_short_code,
    request_reset,
    reset_password,
    verify_reset_token,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """
    ورود یکپارچه: username/password برای مدیریت (یوزرنیم + رمز) و پرسنل (کد پرسنلی + کد ملی)؛ تشخیص در AuthService.login().
    دسترسی: عمومی. خروجی: access و refresh token.
    خطاها: 403 (IP مجاز نیست)، 429 (قفل موقت شناسه یا مسدودیت IP، با هدر Retry-After)، 401 (اطلاعات نادرست
    یا کپچای لازم/اشتباه). بدنه‌ی 401 فیلد captcha_required دارد: True یعنی تلاش بعدی باید با captcha_id و
    captcha_answer (از GET /auth/captcha) فرستاده شود.
    """
    service = AuthService(db)
    try:
        access_token, refresh_token = await service.login(
            payload.username,
            payload.password,
            client_ip=get_client_ip(request),
            captcha_id=payload.captcha_id,
            captcha_answer=payload.captcha_answer,
            user_agent=request.headers.get("user-agent"),
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
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(e), "captcha_required": bool(getattr(e, "captcha_required", False))},
        )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/captcha-status")
async def captcha_status(
    request: Request,
    identifier: str | None = Query(default=None, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    """
    آیا ورود بعدی کپچا لازم دارد؟ (بر اساس IP درخواست و، اگر داده شود، شناسه). دسترسی: عمومی.
    فرانت هنگام باز شدن صفحه‌ی ورود و بعد از وارد کردن شناسه صدا می‌زند تا بعد از رفرش هم کپچا از
    همان ابتدا نمایش داده شود. خروجی: {required}. چیزی درباره‌ی وجود حساب برنمی‌گرداند.
    """
    cfg = await login_security.get_login_security_settings(db)
    required = await login_security.captcha_required_for_login(db, cfg, (identifier or "").strip(), get_client_ip(request))
    return {"required": required}


@router.get("/captcha")
async def get_captcha(purpose: str = Query(default="login", pattern="^(login|forgot)$"), db: AsyncSession = Depends(get_db)):
    """
    کپچای تصویری داخلی. دسترسی: عمومی. خروجی: {required, captcha_id, image (data URL PNG), expires_in}.
    purpose=forgot: اگر کپچای فراموشی رمز خاموش باشد فقط {required: false} برمی‌گردد.
    purpose=login: همیشه چالش می‌سازد (فرانت فقط بعد از پاسخ captcha_required آن را صدا می‌زند).
    """
    cfg = await login_security.get_login_security_settings(db)
    if purpose == "forgot" and not (cfg.captcha_enabled and cfg.captcha_on_forgot_password):
        return {"required": False}
    return {"required": True, **(await login_security.create_captcha(db))}


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


def _otp_http_error(e: otp_service.OtpError) -> HTTPException:
    """OtpError → 429 (ارسال زودهنگام، با Retry-After) یا 400. هرگز 401 تا interceptor فرانت نشست را نبندد."""
    if e.retry_after:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": str(e.retry_after)},
        )
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/me/password/otp-options")
async def password_otp_options(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    روش تأیید هویت برای تغییر رمز کاربر جاری. دسترسی: هر کاربر واردشده.
    خروجی: {otp_required, channels: {"sms"?: موبایل ماسک‌شده, "email"?: ایمیل ماسک‌شده}, sms_enabled,
    code_ttl_seconds, resend_cooldown_seconds}. otp_required=false یعنی کانالی نیست و «رمز عبور فعلی» لازم است.
    sms_enabled برای دیالوگ مشخصات: روشن = تغییر موبایل با کد پیامکی، خاموش = با رمز فعلی.
    """
    options = await otp_service.password_options(db, current_user)
    return {
        "otp_required": options.otp_required,
        "sms_enabled": await otp_service.sms_available(db),
        "channels": options.channels,
        "code_ttl_seconds": otp_service.CODE_TTL_SECONDS,
        "resend_cooldown_seconds": otp_service.RESEND_COOLDOWN_SECONDS,
    }


@router.post("/me/password/otp")
async def send_password_otp(
    payload: PasswordOtpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    کد تأیید تغییر رمز را با پیامک (به موبایل کاربر) یا ایمیل (به ایمیل کاربر) می‌فرستد. دسترسی: هر کاربر واردشده.
    خروجی: {masked_contact, expires_in_seconds, resend_cooldown_seconds}.
    خطا: 400 (کانال در دسترس نیست / ارسال ناموفق)، 429 (ارسال دوباره زودتر از ۶۰ ثانیه).
    """
    options = await otp_service.password_options(db, current_user)
    if payload.channel not in options.channels:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="این روش ارسال کد برای شما در دسترس نیست.")
    if payload.channel == "sms":
        destination = await otp_service.user_mobile(db, current_user)
    else:
        destination = await otp_service.user_email(db, current_user)
    try:
        ttl = await otp_service.request_code(
            db, current_user, purpose=otp_service.PURPOSE_PASSWORD, channel=payload.channel, destination=destination
        )
    except otp_service.OtpError as e:
        raise _otp_http_error(e)
    return {
        "masked_contact": options.channels[payload.channel],
        "expires_in_seconds": ttl,
        "resend_cooldown_seconds": otp_service.RESEND_COOLDOWN_SECONDS,
    }


@router.put("/me/password", response_model=TokenResponse)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    رمز عبور کاربر جاری را تغییر می‌دهد. تأیید هویت: اگر کاربر موبایل/ایمیل قابل‌استفاده دارد، otp_code (از
    POST /auth/me/password/otp)، وگرنه current_password. چون تغییر رمز همه‌ی توکن‌های قبلی را باطل می‌کند،
    جفت توکن تازه برمی‌گرداند تا نشست جاری بدون ورود مجدد ادامه یابد (کلاینت در client.js ذخیره می‌کند).
    دسترسی: هر کاربر واردشده. خطا: 400 اگر کد/رمز فعلی نادرست یا رمز جدید نامعتبر باشد.
    """
    service = AuthService(db)
    options = await otp_service.password_options(db, current_user)
    try:
        if options.otp_required:
            # قدرت رمز پیش از مصرف کد بررسی می‌شود تا با رمز ضعیف، کد هدر نرود
            weak = check_password_strength(payload.new_password)
            if weak:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=weak)
            try:
                await otp_service.verify_and_consume(
                    db, current_user, purpose=otp_service.PURPOSE_PASSWORD, code=payload.otp_code
                )
            except otp_service.OtpError as e:
                raise _otp_http_error(e)
            access_token, refresh_token = await service.change_password(
                current_user, None, payload.new_password, verified=True
            )
        else:
            if not payload.current_password:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="رمز عبور فعلی را وارد کنید.")
            access_token, refresh_token = await service.change_password(
                current_user, payload.current_password, payload.new_password
            )
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/me/mobile/otp")
async def send_mobile_otp(
    payload: MobileOtpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    کد تأیید تغییر موبایل را با پیامک به «شماره‌ی جدید» می‌فرستد. دسترسی: هر کاربر واردشده.
    خروجی: {masked_contact, expires_in_seconds, resend_cooldown_seconds}.
    خطا: 400 (شماره نامعتبر/تکراری، سرویس پیامک خاموش، ارسال ناموفق)، 429 (ارسال دوباره زودتر از ۶۰ ثانیه).
    """
    if current_user.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این حساب به هیچ پرسنلی متصل نیست، پس موبایل قابل‌ذخیره نیست",
        )
    try:
        new_mobile = normalize_mobile(payload.mobile)
    except ContactInfoUpdateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if new_mobile == (await otp_service.user_mobile(db, current_user) or ""):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="این شماره همان شماره‌ی فعلی شماست.")
    if not await otp_service.sms_available(db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="سرویس پیامک فعال نیست.")
    try:
        ttl = await otp_service.request_code(
            db, current_user, purpose=otp_service.PURPOSE_MOBILE, channel="sms", destination=new_mobile
        )
    except otp_service.OtpError as e:
        raise _otp_http_error(e)
    return {
        "masked_contact": otp_service.mask_mobile(new_mobile),
        "expires_in_seconds": ttl,
        "resend_cooldown_seconds": otp_service.RESEND_COOLDOWN_SECONDS,
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    خروج: همه‌ی توکن‌های صادرشده‌ی کاربر (در همه‌ی دستگاه‌ها) را با به‌روزکردن password_changed_at باطل می‌کند.
    دسترسی: هر کاربر واردشده (پاسخ 204). کلاینت پس از آن توکن‌های محلی را پاک می‌کند.
    """
    await AuthService(db).logout(current_user)


@router.put("/me/contact-info")
async def update_my_contact_info_endpoint(
    payload: ContactInfoUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    ایمیل/موبایل کاربر جاری را به‌روزرسانی می‌کند؛ اگر ستون متناظر در نگاشت ستون‌های سایت پرسنل
    تنظیم شده باشد، در دیتابیس اصلی سایت هم نوشته می‌شود (write-back)، وگرنه فقط در دیتابیس پرتال.
    دسترسی: هر کاربر واردشده. تغییر ایمیل تأیید نمی‌خواهد. اگر موبایل واقعاً تغییر کند، mobile_otp_code (کد
    پیامک‌شده به شماره‌ی جدید با POST /auth/me/mobile/otp) لازم است؛ فقط وقتی سرویس پیامک خاموش است، رمز فعلی
    (برای پرسنل بدون رمز اختصاصی: کد ملی) جای آن را می‌گیرد.
    خطا: 400 برای مقدار نامعتبر، خطای ذخیره یا کد/رمز نادرست.
    """
    # موبایل فعلی ذخیره‌شده (همان منبع /auth/me: Employee)
    stored_mobile = None
    if current_user.employee_id is not None:
        employee = await db.get(Employee, current_user.employee_id)
        if employee is not None:
            stored_mobile = employee.mobile

    try:
        new_mobile = normalize_mobile(payload.mobile)
    except ContactInfoUpdateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    mobile_changed = new_mobile != (stored_mobile or "")

    if mobile_changed:
        # 400 (نه 401) تا interceptor فرانت آن را «توکن منقضی» تلقی و رفرش/خروج نکند
        if await otp_service.sms_available(db):
            # کد پیامک‌شده به همان شماره‌ی جدید (ثابت می‌کند شماره در دست کاربر است)
            try:
                await otp_service.verify_and_consume(
                    db, current_user, purpose=otp_service.PURPOSE_MOBILE,
                    code=payload.mobile_otp_code, destination=new_mobile,
                )
            except otp_service.OtpError as e:
                raise _otp_http_error(e)
        else:
            # سرویس پیامک خاموش است: مثل قبل با رمز فعلی
            if not payload.current_password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="برای تغییر موبایل، رمز عبور فعلی خود را وارد کنید.",
                )
            try:
                await AuthService(db).verify_current_credential(current_user, payload.current_password)
            except AuthError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

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
    همیشه masked_contact و expires_in_seconds (عمر کامل کانال) برمی‌گرداند، حتی برای شناسه‌ی نامعتبر
    (ماسک ساختگی)، تا وجود حساب قابل تشخیص نباشد. ارسال واقعی در پس‌زمینه است؛ خطای درگاه فقط لاگ می‌شود.
    خطا: 429 اگر IP مسدود باشد یا سقف درخواست‌های فراموشی رمز از این IP در بازه پر شده باشد.
    """
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    cfg = await login_security.get_login_security_settings(db)
    # مسدودیت IP همین‌جا هم اعمال می‌شود (جلوی ارسال انبوه پیامک/ایمیل از یک IP)
    ip_remaining = await login_security.ip_block_remaining(db, cfg, client_ip)
    if ip_remaining is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"به‌خاطر تلاش‌های ناموفق زیاد از این شبکه، درخواست موقتاً مسدود شده — {int(ip_remaining) // 60 + 1} دقیقه دیگر امتحان کنید.",
        )
    # سقف جدای درخواست‌های فراموشی رمز از یک IP (ضد بررسی انبوه شناسه‌ها و پیامک انبوه)
    if await login_security.forgot_password_ip_exceeded(db, cfg, client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"تعداد درخواست‌های بازیابی رمز از این شبکه زیاد است — {cfg.ip_window_minutes} دقیقه دیگر امتحان کنید.",
        )
    if cfg.captcha_enabled and cfg.captcha_on_forgot_password:
        if not payload.captcha_id or not payload.captcha_answer:
            return JSONResponse(status_code=400, content={"detail": "لطفاً کد امنیتی تصویر را وارد کنید.", "captcha_required": True})
        if not await login_security.verify_captcha(db, payload.captcha_id, payload.captcha_answer):
            await login_security.record_other_failure(db, cfg, "captcha_failed", client_ip, payload.identifier, user_agent)
            return JSONResponse(
                status_code=400,
                content={"detail": "کد امنیتی اشتباه یا منقضی است؛ کد جدید را وارد کنید.", "captcha_required": True},
            )
    await login_security.log_event(db, "forgot_password", client_ip, payload.identifier, user_agent)

    settings = get_settings()
    reset_link_base = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password"  # آدرس صفحه‌ی بازنشانی در فرانت‌اند
    # ارسال در پس‌زمینه انجام می‌شود؛ خطای درگاه پیامک/ایمیل به کاربر برنمی‌گردد (نشت وجود حساب و زمان پاسخ)
    result = await request_reset(db, payload.identifier, payload.channel, reset_link_base)

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


def _require_identifier_for_short_code(token: str, identifier: str | None) -> None:
    """کد ۶ رقمی پیامکی بدون شناسه‌ی حساب پذیرفته نمی‌شود (400)؛ توکن طولانی لینک ایمیل به شناسه نیاز ندارد."""
    if is_short_code(token) and not (identifier or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای تأیید کد پیامکی، شناسه‌ی ورود (کد پرسنلی/نام کاربری) هم لازم است؛ درخواست را از ابتدا تکرار کنید.",
        )


@router.post("/verify-reset-code")
async def verify_reset_code_endpoint(
    payload: VerifyResetCodeRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    """
    اعتبار کد/توکن بازنشانی را بدون مصرف آن بررسی می‌کند (در جریان پیامکی، پیش از نمایش فرم رمز جدید).
    برای کد ۶ رقمی پیامکی، identifier (همان شناسه‌ی مرحله‌ی اول) الزامی است و کد به حساب او مقید می‌شود؛
    هر کد اشتباه شمارنده‌ی آن توکن را بالا می‌برد و بعد از چند تلاش توکن باطل می‌شود.
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
    _require_identifier_for_short_code(payload.token, payload.identifier)

    # بررسی کد؛ در صورت شکست، یک تلاش ناموفق برای این IP ثبت می‌شود
    try:
        await verify_reset_token(db, payload.token, payload.identifier)
    except PasswordResetError as e:
        cfg = await login_security.get_login_security_settings(db)
        await record_failed_login(db, lockout_key, cfg.attempts_per_tier, login_security.lock_seconds(cfg))
        await login_security.record_other_failure(
            db, cfg, "reset_code_failed", client_ip, payload.identifier, request.headers.get("user-agent")
        )
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

    _require_identifier_for_short_code(payload.token, payload.identifier)

    # تغییر رمز؛ در صورت شکست، یک تلاش ناموفق برای این IP ثبت می‌شود
    try:
        await reset_password(db, payload.token, payload.new_password, payload.identifier)
    except PasswordResetError as e:
        cfg = await login_security.get_login_security_settings(db)
        await record_failed_login(db, lockout_key, cfg.attempts_per_tier, login_security.lock_seconds(cfg))
        await login_security.record_other_failure(
            db, cfg, "reset_code_failed", client_ip, payload.identifier, request.headers.get("user-agent")
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await reset_login_attempts(db, lockout_key)
    return {"message": "رمز عبور با موفقیت تغییر کرد. اکنون می‌توانید وارد شوید."}
