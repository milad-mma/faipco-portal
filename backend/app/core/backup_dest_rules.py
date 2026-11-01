"""
قواعد خالص مقصدهای بکاپ (docs/backup.md بخش «مقصدها»): امضای AWS SigV4 برای S3، اعتبارسنجی پوشه‌ی محلی، و منطق صف
تلاش دوباره (زمان تلاش بعدی، کنار گذاشتن بعد از سقف). بدون وابستگی به شبکه/دیتابیس تا با تست واحد بررسی شود.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

# ---------- ترتیب و برچسب مقصدها ----------

KINDS = ("local", "smb", "ftp", "sftp", "s3", "email")
LABELS = {
    "local": "پوشه/دیسک محلی",
    "smb": "SMB",
    "ftp": "FTP",
    "sftp": "SFTP",
    "s3": "فضای ابری S3",
    "email": "ایمیل",
}

# ---------- صف تلاش دوباره ----------

# فاصله‌ی تلاش‌های بعدی پس از هر شکست (دقیقه): ۱۵ دقیقه، ۳۰ دقیقه، ۱، ۲، ۴ و ۸ ساعت → حدود ۱۶ ساعت
RETRY_DELAYS_MIN = (15, 30, 60, 120, 240, 480)
MAX_ATTEMPTS = len(RETRY_DELAYS_MIN)  # بعد از این تعداد تلاش ناموفق، آن مقصد برای این فایل کنار گذاشته می‌شود
MAX_QUEUED_ARCHIVES = 3  # حداکثر فایل بکاپ منتظر روی دیسک سرور (قدیمی‌ترین کنار می‌رود)


_ARCHIVE_NAME_RE = re.compile(r"faipco-backup-\d{8}-\d{6}\.zip")


def parse_filename_ok(name: str) -> bool:
    """آیا name نام معتبر یک فایل بکاپ است (برای جلوگیری از مسیر دلخواه در صف/حذف)."""
    return bool(_ARCHIVE_NAME_RE.fullmatch(name or ""))


def next_retry_at(attempts: int, now: datetime | None = None) -> datetime | None:
    """
    زمان تلاش بعدی پس از attempts شکست (۱ = اولین شکست، یعنی ارسال اصلی). None یعنی سقف تلاش پر شده و دیگر تلاش نشود.
    """
    if attempts < 1 or attempts > MAX_ATTEMPTS:
        return None
    now = now or datetime.now(timezone.utc)
    return now + timedelta(minutes=RETRY_DELAYS_MIN[attempts - 1])


def entries_to_drop(entries: list[dict], keep: int = MAX_QUEUED_ARCHIVES) -> list[str]:
    """از فهرست ورودی‌های صف ({"filename", "created_at" ISO})، نام فایل‌هایی که باید کنار بروند (قدیمی‌ترها فراتر از keep)."""
    ordered = sorted(entries, key=lambda e: e.get("created_at") or "", reverse=True)
    return [e["filename"] for e in ordered[keep:]]


def superseded_kinds(entry_created: str, newer_success: dict[str, str]) -> set[str]:
    """
    مقصدهایی از یک ورودی قدیمی که دیگر تلاش برایشان لازم نیست چون بکاپ جدیدتری به همان مقصد رسیده است.
    newer_success: {kind: created_at ISO آخرین بکاپی که به آن مقصد رسید}.
    """
    return {k for k, ts in newer_success.items() if ts and ts > entry_created}


# ---------- پوشه‌ی محلی / دیسک متصل ----------

# مسیرهایی که بکاپ نباید داخلشان نوشته شود (سیستم، خود پرتال، پوشه‌ی موقت بکاپ)
_FORBIDDEN_LOCAL_PREFIXES = (
    "/bin", "/boot", "/dev", "/etc", "/lib", "/lib64", "/proc", "/run", "/sbin", "/sys", "/usr",
    "/var/www", "/var/lib/faipco", "/var/lib/postgresql", "/var/log", "/root",
)


def check_local_path(raw: str | None) -> str:
    """
    مسیر پوشه‌ی بکاپ محلی را بررسی و نرمال می‌کند: باید مطلق باشد، «..» نداشته باشد و داخل مسیرهای سیستمی یا خود پرتال
    نباشد. خروجی: مسیر نرمال. خطا: ValueError با پیام فارسی.
    """
    path = (raw or "").strip()
    if not path:
        raise ValueError("مسیر پوشه‌ی بکاپ را وارد کنید (مثلاً /mnt/backup/faipco)")
    if not path.startswith("/"):
        raise ValueError("مسیر پوشه باید کامل باشد و با / شروع شود (مثلاً /mnt/backup/faipco)")
    if "\x00" in path or ".." in path.split("/"):
        raise ValueError("مسیر پوشه نامعتبر است")
    norm = os.path.normpath(path)
    if norm == "/":
        raise ValueError("ریشه‌ی دیسک (/) را نمی‌شود انتخاب کرد؛ یک پوشه بسازید (مثلاً /mnt/backup/faipco)")
    for prefix in _FORBIDDEN_LOCAL_PREFIXES:
        if norm == prefix or norm.startswith(prefix + "/"):
            raise ValueError(f"پوشه‌ی بکاپ نمی‌تواند داخل {prefix} باشد؛ یک دیسک یا پوشه‌ی جدا انتخاب کنید (مثلاً /mnt/backup)")
    return norm


# ---------- S3: امضای AWS Signature Version 4 ----------

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
S3_SINGLE_PUT_MAX = 5 * 1024**3  # سقف آپلود یک‌تکه‌ی S3 (۵ گیگابایت)


def _uri_encode(value: str, *, keep_slash: bool = False) -> str:
    return quote(value, safe="-_.~/" if keep_slash else "-_.~")


def s3_object_url(endpoint: str, bucket: str, key: str, *, path_style: bool) -> tuple[str, str, str]:
    """
    آدرس شیء S3. خروجی: (url کامل، host، canonical_uri). endpoint مثل https://s3.example.com (بدون نام bucket).
    path_style=True → https://host/bucket/key ؛ False → https://bucket.host/key
    """
    ep = (endpoint or "").strip().rstrip("/")
    if not ep.startswith(("https://", "http://")):
        ep = "https://" + ep
    scheme, rest = ep.split("://", 1)
    host = rest.split("/", 1)[0]
    key = key.lstrip("/")
    if path_style:
        canonical = "/" + _uri_encode(bucket) + ("/" + _uri_encode(key, keep_slash=True) if key else "")
    else:
        host = f"{bucket}.{host}"
        canonical = "/" + _uri_encode(key, keep_slash=True)
    return f"{scheme}://{host}{canonical}", host, canonical


def _canonical_query(params: dict[str, str] | None) -> str:
    if not params:
        return ""
    return "&".join(f"{_uri_encode(k)}={_uri_encode(str(v))}" for k, v in sorted(params.items()))


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def sigv4_headers(
    *,
    method: str,
    host: str,
    canonical_uri: str,
    query: dict[str, str] | None,
    headers: dict[str, str] | None,
    payload_sha256: str,
    access_key: str,
    secret_key: str,
    region: str,
    now: datetime | None = None,
    service: str = "s3",
) -> dict[str, str]:
    """
    هدرهای امضاشده‌ی SigV4 (Authorization، x-amz-date، x-amz-content-sha256 و هدرهای ورودی) را برمی‌گرداند.
    payload_sha256 هش واقعی بدنه است؛ سرور S3 با آن سالم رسیدن کل فایل را بررسی می‌کند (عدم تطابق = رد آپلود).
    """
    now = now or datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = now.strftime("%Y%m%d")
    all_headers = {k.lower(): str(v).strip() for k, v in (headers or {}).items()}
    all_headers["host"] = host
    all_headers["x-amz-content-sha256"] = payload_sha256
    all_headers["x-amz-date"] = amz_date
    signed = ";".join(sorted(all_headers))
    canonical_headers = "".join(f"{k}:{all_headers[k]}\n" for k in sorted(all_headers))
    canonical_request = "\n".join(
        [method.upper(), canonical_uri, _canonical_query(query), canonical_headers, signed, payload_sha256]
    )
    scope = f"{date}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()]
    )
    k = _hmac(("AWS4" + secret_key).encode("utf-8"), date)
    k = _hmac(k, region)
    k = _hmac(k, service)
    k = _hmac(k, "aws4_request")
    signature = hmac.new(k, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    out = {key: val for key, val in all_headers.items() if key != "host"}
    out["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={signed}, Signature={signature}"
    )
    return out


def s3_key(prefix: str | None, filename: str) -> str:
    """کلید شیء: پیشوند (پوشه) اختیاری + نام فایل."""
    p = (prefix or "").strip().strip("/")
    return f"{p}/{filename}" if p else filename


def sha256_file(path, chunk: int = 1 << 20) -> str:
    """SHA-256 یک فایل (جریانی)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()
