"""
لایه‌ی Storage فایل‌های اتوماسیون (docs/office-automation-spec.md بخش ۹.۱): فایل بیرون از PostgreSQL، write-once.

رابط ساده تا بعداً پیاده‌سازی S3-سازگار جایگزین شود؛ اکنون فقط پوشه‌ی محلی خصوصی (settings.OA_STORAGE_DIR):
- tmp/<uuid>.part   دریافت جریانی؛ بعد از بررسی به objects/ منتقل یا حذف می‌شود
- objects/YYYY/MM/<uuid>   محتوای ذخیره‌شده (بدون پسوند؛ نوع و نام در دیتابیس) — هرگز بازنویسی نمی‌شود
- quarantine/<uuid>  فایل آلوده (فقط‌خواندنی، بدون مسیر دانلود)
"""
from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone
from pathlib import Path



def _settings():
    from app.core.config import get_settings  # import محلی: ماژول بدون .env هم قابل تست است

    return get_settings()


CHUNK = 1 << 20  # ۱ مگابایت


class StorageError(RuntimeError):
    pass


class SizeLimitExceeded(StorageError):
    pass


class LocalStorage:
    def __init__(self, root: str | None = None):
        self.root = Path(root or _settings().OA_STORAGE_DIR)

    # ---------- مسیرها ----------

    def _safe(self, key: str) -> Path:
        """کلید نسبی → مسیر مطلق داخل root؛ کلید خارج از root (.. / مسیر مطلق) رد می‌شود."""
        path = (self.root / key).resolve()
        root = self.root.resolve()
        if root != path and root not in path.parents:
            raise StorageError("کلید فایل نامعتبر است")
        return path

    def ensure_dirs(self) -> None:
        for sub in ("tmp", "objects", "quarantine"):
            (self.root / sub).mkdir(parents=True, exist_ok=True, mode=0o700)

    def path_of(self, key: str) -> Path:
        return self._safe(key)

    def exists(self, key: str) -> bool:
        return self._safe(key).is_file()

    # ---------- نوشتن ----------

    async def receive(self, chunks: AsyncIterator[bytes], max_bytes: int) -> tuple[str, int, str]:
        """
        دریافت جریانی در tmp با سقف حجم؛ خروجی (کلید موقت، حجم، SHA-256). بیش از سقف → SizeLimitExceeded و حذف.
        """
        self.ensure_dirs()
        key = f"tmp/{uuid.uuid4().hex}.part"
        path = self._safe(key)
        digest, size = hashlib.sha256(), 0
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        raise SizeLimitExceeded()
                    digest.update(chunk)
                    f.write(chunk)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return key, size, digest.hexdigest()

    def commit(self, temp_key: str) -> str:
        """فایل موقت را به objects/ منتقل می‌کند (یک‌بار، بدون بازنویسی)؛ خروجی کلید دائم."""
        now = datetime.now(timezone.utc)
        key = f"objects/{now:%Y}/{now:%m}/{uuid.uuid4().hex}"
        dst = self._safe(key)
        dst.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        src = self._safe(temp_key)
        if dst.exists():
            raise StorageError("فایل مقصد از قبل وجود دارد")
        os.replace(src, dst)
        os.chmod(dst, 0o400)  # write-once
        return key

    def quarantine(self, key: str) -> str:
        new_key = f"quarantine/{uuid.uuid4().hex}"
        dst = self._safe(new_key)
        dst.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.replace(self._safe(key), dst)
        os.chmod(dst, 0o400)
        return new_key

    def delete(self, key: str | None) -> None:
        """فقط برای فایل موقت/ردشده/آلوده‌ی بی‌پیوند (پاک‌سازی)؛ فایل دائم حذف خودکار ندارد."""
        if not key:
            return
        path = self._safe(key)
        if path.is_file():
            os.chmod(path, 0o600)
            path.unlink()

    # ---------- خواندن ----------

    def iter_file(self, key: str, chunk: int = CHUNK) -> Iterator[bytes]:
        with open(self._safe(key), "rb") as f:
            while True:
                block = f.read(chunk)
                if not block:
                    return
                yield block

    def sha256_of(self, key: str) -> str:
        digest = hashlib.sha256()
        for block in self.iter_file(key):
            digest.update(block)
        return digest.hexdigest()

    def usage(self) -> dict:
        """فضای آزاد دیسک پوشه‌ی فایل‌ها (برای پنل)."""
        self.ensure_dirs()
        total, used, free = shutil.disk_usage(self.root)
        return {"total": total, "used": used, "free": free}
