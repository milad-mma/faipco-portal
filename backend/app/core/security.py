"""
هسته امنیتی برنامه:
- هش و بررسی پسورد کاربران (bcrypt)
- قانون قدرت رمز عبور
- تولید و اعتبارسنجی JWT
- رمزنگاری/رمزگشایی Credential های اتصال به دیتابیس سایت‌ها (Fernet/AES)

هیچ پسورد یا Credential ای هرگز نباید به‌صورت متن ساده در دیتابیس ذخیره شود.
"""
import re
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# جدول تبدیل ارقام فارسی/عربی به لاتین — روی کیبورد فارسی موبایل (که برای
# خیلی از پرسنل ایرانی پیش‌فرض است)، تایپ کردن یک عدد می‌تواند ارقام فارسی
# (۰۱۲۳۴۵۶۷۸۹) یا عربی (٠١٢٣٤٥٦٧٨٩) تولید کند، نه لاتین — که با کد ملی
# لاتین ذخیره‌شده در دیتابیس هرگز برابر نمی‌شود، حتی اگر از نظر چشم انسان
# «همان عدد» به‌نظر برسد.
_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"
)
# کاراکترهای نامرئی (Zero-Width) که در تایپ فارسی (خصوصاً موبایل) رایج‌اند
# ولی str.strip() پیش‌فرض پایتون آن‌ها را حذف نمی‌کند (چون «فاصله» محسوب
# نمی‌شوند) — اگر یکی از این‌ها به هر دلیلی (مثلاً کیبورد/Autocomplete) وارد
# یک فیلد عددی شود، مقایسه رشته‌ای همیشه شکست می‌خورد، بدون هیچ تفاوت
# قابل‌مشاهده برای کاربر.
_ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\ufeff"


def normalize_login_credential(value: str) -> str:
    """
    یک رشته ورودی کاربر (کد پرسنلی یا کد ملی، هنگام ورود) را قبل از مقایسه
    با دیتابیس نرمال‌سازی می‌کند — ارقام فارسی/عربی به لاتین تبدیل می‌شوند،
    کاراکترهای نامرئی حذف می‌شوند، و فاصله ابتدا/انتها پاک می‌شود. بدون این،
    پرسنلی که از کیبورد فارسی موبایل استفاده می‌کند، حتی با تایپ کاملاً
    درست کد ملی‌اش، ممکن است با خطای «اطلاعات ورود اشتباه است» مواجه شود.
    """
    if value is None:
        return ""
    result = value.translate(_DIGIT_TRANSLATION)
    for ch in _ZERO_WIDTH_CHARS:
        result = result.replace(ch, "")
    return result.strip()
_fernet = Fernet(settings.DB_CREDENTIALS_ENCRYPTION_KEY.encode())

MIN_PASSWORD_LENGTH = 10


class WeakPasswordError(Exception):
    """رمز عبور داده‌شده قانون قدرت رمز را رعایت نمی‌کند."""


def check_password_strength(password: str) -> str | None:
    """اگر رمز ضعیف باشد، پیام خطای فارسی مربوطه را برمی‌گرداند؛ وگرنه None
    (یعنی رمز قابل‌قبول است). عمداً یک تابع «بررسی» جدا از یک Exception
    است تا هم بشود در جاهایی که فقط می‌خواهیم بی‌سروصدا تشخیص بدهیم (مثلاً
    create_admin.py، برای تصمیم‌گیری درباره must_change_password) و هم در
    جاهایی که باید Exception پرتاب شود (validate_password_strength) از آن
    استفاده کرد."""
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
    """اگر رمز ضعیف باشد WeakPasswordError پرتاب می‌کند — برای مسیرهایی که
    کاربر واقعاً در حال تعیین/تغییر رمز است (باید حتماً رد شود، نه فقط
    علامت‌گذاری)."""
    error = check_password_strength(password)
    if error:
        raise WeakPasswordError(error)


# ---------- پسورد کاربران ----------

def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------- JWT ----------

def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire, "type": "access"}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ---------- رمزنگاری Credential دیتابیس سایت‌ها ----------

def encrypt_secret(plain_text: str) -> str:
    """برای رمزنگاری پسورد اتصال به دیتابیس هر Site استفاده می‌شود."""
    return _fernet.encrypt(plain_text.encode()).decode()


def decrypt_secret(encrypted_text: str) -> str:
    return _fernet.decrypt(encrypted_text.encode()).decode()
