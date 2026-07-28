"""
هسته امنیتی برنامه:
- هش و بررسی پسورد کاربران (bcrypt)
- تولید و اعتبارسنجی JWT
- رمزنگاری/رمزگشایی Credential های اتصال به دیتابیس سایت‌ها (Fernet/AES)

هیچ پسورد یا Credential ای هرگز نباید به‌صورت متن ساده در دیتابیس ذخیره شود.
"""
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_fernet = Fernet(settings.DB_CREDENTIALS_ENCRYPTION_KEY.encode())


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
