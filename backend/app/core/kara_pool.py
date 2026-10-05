"""
استخر (Pool) کوچک اتصال‌های همگام به دیتابیس منبع (کاراوب: SQL Server / MySQL / PostgreSQL).

قبلاً هر تابع کمکیِ همگام (`_xxx_sync`) یک اتصال تازه باز می‌کرد و می‌بست؛ یک ثبت مرخصی یا تصمیم تأییدکننده
۴ تا ۱۰ بار Login به SQL Server می‌زد (هر بار ۵۰ تا ۳۰۰ میلی‌ثانیه). این ماژول اتصال‌های باز را برای استفاده‌ی بعدی
نگه می‌دارد، بدون تغییر در کد فراخوان: `conn = pooled_connect(...)` ... `conn.close()` — close() اتصال را به استخر
برمی‌گرداند (پس از rollback تا تراکنش ناتمام و قفلی باقی نماند).

قواعد:
- کلید استخر: نوع دیتابیس + میزبان + پورت + نام دیتابیس + کاربر.
- حداکثر MAX_IDLE_PER_KEY اتصال بی‌کار به‌ازای هر کلید؛ اتصال بی‌کارِ بیش از IDLE_TTL_SECONDS بسته می‌شود.
- پیش از تحویل، اتصال با یک `SELECT 1` سبک آزمایش می‌شود؛ اتصال خراب دور انداخته و اتصال تازه ساخته می‌شود.
- اتصال‌ها thread-safe نیستند ولی هر اتصال در هر لحظه فقط دست یک فراخوان است (get/put با Lock).
- خطا در rollback/هر مشکلی هنگام بازگرداندن → اتصال واقعاً بسته می‌شود، نه به استخر.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Callable

logger = logging.getLogger(__name__)

MAX_IDLE_PER_KEY = 4
IDLE_TTL_SECONDS = 300

_lock = threading.Lock()
_idle: dict[tuple, deque] = {}  # کلید → deque[(اتصال خام, زمان بازگشت به استخر)]


class PooledConnection:
    """پوشش نازک روی اتصال درایور؛ همه‌ی متدها به اتصال خام می‌رسند و فقط close() رفتار استخر دارد."""

    __slots__ = ("_raw", "_key", "_returned")

    def __init__(self, raw, key: tuple):
        self._raw = raw
        self._key = key
        self._returned = False

    def cursor(self, *args, **kwargs):
        return self._raw.cursor(*args, **kwargs)

    def commit(self):
        return self._raw.commit()

    def rollback(self):
        return self._raw.rollback()

    def close(self) -> None:
        """اتصال را (پس از rollback) به استخر برمی‌گرداند؛ در صورت خطا واقعاً می‌بندد."""
        if self._returned:
            return
        self._returned = True
        _release(self._key, self._raw)

    def __getattr__(self, name):
        return getattr(self._raw, name)

    # اگر کسی به‌جای try/finally از with استفاده کند
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def _is_alive(raw) -> bool:
    try:
        cur = raw.cursor()
        try:
            cur.execute("SELECT 1")
            cur.fetchall()
        finally:
            cur.close()
        return True
    except Exception:  # noqa: BLE001 - هر خطایی یعنی اتصال قابل‌استفاده نیست
        return False


def _discard(raw) -> None:
    try:
        raw.close()
    except Exception:  # noqa: BLE001
        pass


def _release(key: tuple, raw) -> None:
    try:
        raw.rollback()  # تراکنش ضمنی خواندن/نوشتن ناتمام را می‌بندد (قفل‌ها آزاد می‌شوند)
    except Exception:  # noqa: BLE001 - اتصال مشکوک به استخر برنمی‌گردد
        _discard(raw)
        return
    with _lock:
        bucket = _idle.setdefault(key, deque())
        if len(bucket) >= MAX_IDLE_PER_KEY:
            _discard(raw)
            return
        bucket.append((raw, time.monotonic()))


def pooled_connect(key: tuple, factory: Callable[[], object]) -> PooledConnection:
    """
    ورودی: کلید یکتای مقصد و تابعی که اتصال خام تازه می‌سازد.
    یک اتصال سالم از استخر (یا تازه) برمی‌گرداند. اتصال‌های بی‌کار منقضی همان لحظه بسته می‌شوند.
    """
    now = time.monotonic()
    while True:
        with _lock:
            bucket = _idle.get(key)
            item = bucket.popleft() if bucket else None
        if item is None:
            break
        raw, since = item
        if now - since > IDLE_TTL_SECONDS or not _is_alive(raw):
            _discard(raw)
            continue
        return PooledConnection(raw, key)
    return PooledConnection(factory(), key)


def connection_key(conn) -> tuple:
    """کلید استخر از رکورد SiteConnection (رمز در کلید نیست؛ تغییر رمز با Login بعدی خودش را نشان می‌دهد)."""
    return (str(conn.db_type), (conn.host or "").lower(), conn.port, (conn.database_name or "").lower(), conn.username)


def close_all() -> None:
    """بستن همه‌ی اتصال‌های بی‌کار (برای خاموش شدن سرویس)."""
    with _lock:
        items = [raw for bucket in _idle.values() for raw, _ in bucket]
        _idle.clear()
    for raw in items:
        _discard(raw)
