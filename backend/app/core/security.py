"""
هسته امنیتی برنامه:
- هش و بررسی پسورد کاربران (bcrypt)
- قانون قدرت رمز عبور
- تولید و اعتبارسنجی JWT
- رمزنگاری/رمزگشایی Credential های اتصال به دیتابیس سایت‌ها (Fernet/AES)
- نرمال‌سازی شناسه ورود (ارقام فارسی/عربی و کاراکترهای نامرئی)

هیچ پسورد یا Credential ای هرگز نباید به‌صورت متن ساده در دیتابیس ذخیره شود.
"""
import re
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # هش پسورد با bcrypt

# جدول تبدیل ارقام فارسی (۰۱۲۳۴۵۶۷۸۹) و عربی (٠١٢٣٤٥٦٧٨٩) به لاتین؛ کیبورد فارسی
# موبایل این ارقام را تولید می‌کند ولی کد ملی/پرسنلی در دیتابیس با ارقام لاتین ذخیره است.
_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"
)
# کاراکترهای نامرئی (Zero-Width) رایج در تایپ فارسی که str.strip() حذفشان نمی‌کند
# و در صورت ورود به فیلد عددی، مقایسه رشته‌ای را خراب می‌کنند.
_ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\ufeff"


def normalize_login_credential(value: str) -> str:
    """
    ورودی: شناسه ورود کاربر (کد پرسنلی یا کد ملی). قبل از مقایسه با دیتابیس، ارقام فارسی/عربی
    را به لاتین تبدیل، کاراکترهای نامرئی را حذف و فاصله ابتدا/انتها را پاک می‌کند.
    خروجی: رشته نرمال‌شده (برای None رشته خالی).
    """
    if value is None:
        return ""
    result = value.translate(_DIGIT_TRANSLATION)
    for ch in _ZERO_WIDTH_CHARS:
        result = result.replace(ch, "")
    return result.strip()
# شیء Fernet برای رمزنگاری Credentialها با کلید مجزای DB_CREDENTIALS_ENCRYPTION_KEY
_fernet = Fernet(settings.DB_CREDENTIALS_ENCRYPTION_KEY.encode())

MIN_PASSWORD_LENGTH = 10  # حداقل طول رمز عبور


class WeakPasswordError(Exception):
    """رمز عبور داده‌شده قانون قدرت رمز را رعایت نمی‌کند."""


def check_password_strength(password: str) -> str | None:
    """ورودی: رمز عبور. خروجی: پیام خطای فارسی اگر رمز ضعیف باشد (طول، حرف کوچک، حرف بزرگ، عدد)؛ وگرنه None.
    بدون Exception است تا هم برای تشخیص بی‌صدا (مثل create_admin.py برای must_change_password)
    و هم در validate_password_strength استفاده شود."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"رمز عبور باید حداقل {MIN_PASSWORD_LENGTH} کاراکتر باشد."
    if not re.search(r"[a-z]", password):
        return "رمز عبور باید حداقل یک حرف کوچک انگلیسی داشته باشد."
    if not re.search(r"[A-Z]", password):
        return "رمز عبور باید حداقل یک حرف بزرگ انگلیسی داشته باشد."
    if not re.search(r"[0-9]", password):
        return "رمز عبور باید حداقل یک عدد داشته باشد."
    return None


def validate_password_strength(password: str) -> None:
    """ورودی: رمز عبور. اگر ضعیف باشد WeakPasswordError پرتاب می‌کند؛ برای مسیرهای تعیین/تغییر رمز."""
    error = check_password_strength(password)
    if error:
        raise WeakPasswordError(error)


# ---------- پسورد کاربران ----------

def hash_password(plain_password: str) -> str:
    """ورودی: رمز متن ساده. خروجی: هش bcrypt آن."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """ورودی: رمز متن ساده و هش ذخیره‌شده. خروجی: True اگر مطابقت داشته باشند."""
    return pwd_context.verify(plain_password, hashed_password)


# ---------- JWT ----------

def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    """ورودی: شناسه کاربر (sub) و claimهای اضافی. خروجی: Access Token امضاشده با نوع "access" و انقضای کوتاه."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire, "type": "access"}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """ورودی: شناسه کاربر (sub). خروجی: Refresh Token امضاشده با نوع "refresh" و انقضای چندروزه."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict | None:
    """ورودی: توکن JWT. خروجی: payload در صورت معتبر بودن امضا و انقضا؛ وگرنه None."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ---------- رمزنگاری Credential دیتابیس سایت‌ها ----------

def encrypt_secret(plain_text: str) -> str:
    """ورودی: متن ساده (پسورد اتصال به دیتابیس Site). خروجی: متن رمزشده با Fernet."""
    return _fernet.encrypt(plain_text.encode()).decode()


def decrypt_secret(encrypted_text: str) -> str:
    """ورودی: متن رمزشده با Fernet. خروجی: متن ساده اصلی."""
    return _fernet.decrypt(encrypted_text.encode()).decode()
