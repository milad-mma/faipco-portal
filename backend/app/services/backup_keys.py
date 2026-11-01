"""
کلیدهای رمزنگاری بکاپ با age (docs/office-automation-spec.md بخش ۱۰.۴؛ docs/backup.md).

- حالت اول «external»: فقط کلید عمومی در دیتابیس؛ کلید خصوصی یک بار به ادمین نمایش/دانلود داده می‌شود و هنگام بازیابی
  باید ارائه شود. مدیر فنی بدون کلید نمی‌تواند محتوای بکاپ را بخواند.
- حالت دوم «server_protected»: کلید خصوصی رمزنگاری‌شده با secret سرور (encrypt_secret) ذخیره می‌شود؛ بازیابی از پنل بدون
  ورود کلید. جداسازی اختیار فراهم نیست (هر کس به سرور و secret دسترسی دارد می‌تواند بکاپ را بخواند).
- چرخش: کلید جدید فعال می‌شود و کلید قبلی retired می‌ماند (حذف نمی‌شود) تا بکاپ‌های قدیمی قابل بازیابی بمانند.
- بسته‌ی امن کلید (حالت دوم، برای خرابی کامل سرور): کلید خصوصی رمزنگاری‌شده با عبارت عبور (scrypt + AES-GCM).
- کلید خام هرگز در لاگ، manifest یا پاسخ‌های بعدی نمی‌آید.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # import محلی در توابع دیتابیس: ابزارهای age بدون SQLAlchemy هم قابل تست‌اند
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.backup_v4 import BackupKey

MODES = {"external": "کلید بیرون از سرور", "server_protected": "کلید محافظت‌شده روی سرور"}
KEY_PACKAGE_FORMAT = "faipco-backup-key-v1"


class BackupKeyError(RuntimeError):
    pass


def age_binary(name: str = "age") -> str:
    found = shutil.which(name) or (f"/usr/bin/{name}" if os.path.exists(f"/usr/bin/{name}") else None)
    if not found:
        raise BackupKeyError(f"ابزار {name} روی سرور نصب نیست (بسته‌ی age). یک بار آپدیت پرتال آن را نصب می‌کند.")
    return found


def age_available() -> bool:
    try:
        age_binary("age")
        age_binary("age-keygen")
        return True
    except BackupKeyError:
        return False


def generate_identity() -> tuple[str, str]:
    """(کلید خصوصی AGE-SECRET-KEY-1...، کلید عمومی age1...) با age-keygen، بدون نوشتن روی دیسک."""
    out = subprocess.run([age_binary("age-keygen")], capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise BackupKeyError(f"ساخت کلید ناموفق بود: {out.stderr[:300]}")
    identity = next((ln.strip() for ln in out.stdout.splitlines() if ln.startswith("AGE-SECRET-KEY-")), None)
    if identity is None:
        raise BackupKeyError("خروجی age-keygen نامعتبر بود")
    return identity, public_key_of(identity)


def public_key_of(identity: str) -> str:
    """کلید عمومی متناظر یک کلید خصوصی (age-keygen -y)."""
    identity = (identity or "").strip()
    if not identity.startswith("AGE-SECRET-KEY-1"):
        raise BackupKeyError("کلید خصوصی نامعتبر است (باید با AGE-SECRET-KEY-1 شروع شود)")
    out = subprocess.run([age_binary("age-keygen"), "-y"], input=identity + "\n", capture_output=True, text=True,
                         timeout=30)
    if out.returncode != 0 or not out.stdout.strip().startswith("age1"):
        raise BackupKeyError("کلید خصوصی نامعتبر است")
    return out.stdout.strip()


def key_id_of(public_key: str) -> str:
    return hashlib.sha256(public_key.encode()).hexdigest()[:16]


@contextmanager
def identity_file(identity: str):
    """کلید خصوصی در یک فایل موقت 0600 (برای age -d -i)؛ بعد از استفاده حذف می‌شود."""
    fd, path = tempfile.mkstemp(prefix="faipco-age-", suffix=".key")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(identity.strip() + "\n")
        os.chmod(path, 0o600)
        yield path
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------- بسته‌ی امن کلید با عبارت عبور ----------


def export_package(identity: str, passphrase: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    if len(passphrase or "") < 12:
        raise BackupKeyError("عبارت عبور باید حداقل ۱۲ نویسه باشد")
    salt, nonce = os.urandom(16), os.urandom(12)
    key = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(passphrase.encode())
    ct = AESGCM(key).encrypt(nonce, identity.strip().encode(), KEY_PACKAGE_FORMAT.encode())
    return json.dumps(
        {
            "format": KEY_PACKAGE_FORMAT,
            "public_key": public_key_of(identity),
            "kdf": {"name": "scrypt", "n": 2**15, "r": 8, "p": 1, "salt": base64.b64encode(salt).decode()},
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ct).decode(),
        },
        ensure_ascii=False,
        indent=2,
    ).encode()


def import_package(raw: bytes, passphrase: str) -> str:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    try:
        data = json.loads(raw.decode("utf-8"))
        assert data["format"] == KEY_PACKAGE_FORMAT
        kdf = data["kdf"]
        key = Scrypt(salt=base64.b64decode(kdf["salt"]), length=32, n=int(kdf["n"]), r=int(kdf["r"]),
                     p=int(kdf["p"])).derive((passphrase or "").encode())
        identity = AESGCM(key).decrypt(base64.b64decode(data["nonce"]), base64.b64decode(data["ciphertext"]),
                                       KEY_PACKAGE_FORMAT.encode()).decode()
    except InvalidTag:
        raise BackupKeyError("عبارت عبور اشتباه است") from None
    except Exception:  # noqa: BLE001
        raise BackupKeyError("فایل بسته‌ی کلید نامعتبر است") from None
    return identity


# ---------- دیتابیس ----------


async def active_key(db: AsyncSession) -> BackupKey | None:
    from sqlalchemy import select

    from app.models.backup_v4 import BackupKey  # noqa: F811

    return (
        await db.execute(
            select(BackupKey).where(BackupKey.retired_at.is_(None)).order_by(BackupKey.id.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def list_keys(db: AsyncSession) -> list[BackupKey]:
    from sqlalchemy import select

    from app.models.backup_v4 import BackupKey  # noqa: F811

    return list((await db.execute(select(BackupKey).order_by(BackupKey.id.desc()))).scalars().all())


async def key_by_id(db: AsyncSession, key_id: str) -> BackupKey | None:
    from sqlalchemy import select

    from app.models.backup_v4 import BackupKey  # noqa: F811

    return (await db.execute(select(BackupKey).where(BackupKey.key_id == key_id))).scalar_one_or_none()


async def create_key(db: AsyncSession, mode: str, user_id: int | None, identity: str | None = None) -> tuple[BackupKey, str]:
    """
    کلید تازه (یا وارد کردن کلید خصوصی موجود) و فعال کردن آن؛ کلید قبلی retired می‌شود. خروجی: (ردیف، کلید خصوصی) —
    کلید خصوصی فقط همین یک بار برگردانده می‌شود (برای نمایش در حالت external). commit با فراخواننده.
    """
    from app.core.security import encrypt_secret
    from app.models.backup_v4 import BackupKey  # noqa: F811

    if mode not in MODES:
        raise BackupKeyError("حالت کلید نامعتبر است")
    if identity:
        public = public_key_of(identity)
    else:
        identity, public = generate_identity()
    kid = key_id_of(public)
    existing = await key_by_id(db, kid)
    now = datetime.now(timezone.utc)
    current = await active_key(db)
    if current is not None and current.key_id != kid:
        current.retired_at = now
    if existing is not None:
        existing.retired_at = None
        existing.mode = mode
        existing.encrypted_private_key = encrypt_secret(identity) if mode == "server_protected" else None
        return existing, identity
    row = BackupKey(
        key_id=kid, mode=mode, public_key=public, created_by=user_id,
        encrypted_private_key=encrypt_secret(identity) if mode == "server_protected" else None,
    )
    db.add(row)
    return row, identity


def stored_identity(row: BackupKey) -> str | None:
    """کلید خصوصی ذخیره‌شده (فقط حالت server_protected)."""
    if not row.encrypted_private_key:
        return None
    from app.core.security import decrypt_secret

    return decrypt_secret(row.encrypted_private_key)


def key_out(row: BackupKey, active_id: int | None) -> dict:
    return {
        "key_id": row.key_id,
        "mode": row.mode,
        "mode_label": MODES.get(row.mode, row.mode),
        "public_key": row.public_key,
        "has_server_copy": bool(row.encrypted_private_key),
        "created_at": row.created_at,
        "retired_at": row.retired_at,
        "active": row.id == active_id,
    }
