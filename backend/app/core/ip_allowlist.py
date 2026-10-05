"""
منطق «محدودکردن ورود به رنج‌های IP مجاز» که در auth_service.py استفاده می‌شود:
تشخیص IP واقعی کاربر، نرمال‌سازی IP، بررسی فعال بودن محدودیت و تطبیق IP با رنج‌های CIDR.

نکته درباره تشخیص IP واقعی کاربر: این سرور پشت Nginx است و چون uvicorn با فلگ
--proxy-headers اجرا نمی‌شود، Request.client.host همیشه 127.0.0.1 (اتصال محلی از
Nginx) خواهد بود، نه IP واقعی کاربر. Nginx نصب‌شده با install.sh دو هدر می‌فرستد:
- `proxy_set_header X-Real-IP $remote_addr;` → IP طرفِ اتصالِ TCP به Nginx. چون
  proxy_set_header مقدار ارسالی کلاینت را **جایگزین** می‌کند (نه الحاق)، این هدر
  هیچ‌وقت قابل جعل از سمت کاربر نیست و منبع اصلی تشخیص IP است.
- `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` → مقدار قبلی
  هدر + IP اتصال. یعنی اگر مهاجم خودش هدر X-Forwarded-For جعلی بفرستد، مقدار
  جعلی در **ابتدای** لیست می‌ماند و IP واقعی به **انتهای** آن اضافه می‌شود.
  پس «اولین مقدار» (رفتار قبلی) کاملاً قابل جعل بود و همین اجازه‌ی دورزدن
  «رنج‌های IP مجاز» و محدودیت‌های IP را می‌داد؛ فقط **آخرین مقدار** (آن‌چه
  نزدیک‌ترین Proxy خودش اضافه کرده) قابل اعتماد است.
ترتیب: X-Real-IP، سپس آخرین مقدار X-Forwarded-For، سپس Request.client.host
(مثلاً تست مستقیم به بک‌اند بدون Nginx).

پراکسی خارجی (مثلاً SSL جلوی Nginx): IP آن با REVERSE_PROXY_IP در .env (گزینه‌ی --reverse-proxy-ip در install.sh)
«معتبر» اعلام می‌شود و get_client_ip از آن عبور می‌کند تا به IP واقعی کاربر در X-Forwarded-For برسد.
"""
from __future__ import annotations

import ipaddress

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ip_allowlist_entry import IpAllowlistEntry


def _trusted_proxies() -> set[str]:
    """IPهای پراکسی‌های معتبر: پراکسی خارجی تنظیم‌شده (REVERSE_PROXY_IP در .env؛ با کاما چندتایی) + loopback."""
    from app.core.config import get_settings  # import محلی: این ماژول در زمان import تنظیمات را لازم ندارد

    trusted = {"127.0.0.1", "::1"}
    raw = getattr(get_settings(), "REVERSE_PROXY_IP", "") or ""
    for part in str(raw).replace(";", ",").split(","):
        part = part.strip()
        if part:
            trusted.add(_normalize_ip(part))
    return trusted


def get_client_ip(request: Request) -> str:
    """
    ورودی: Request. خروجی: IP کاربر نهایی از دید نزدیک‌ترین Proxy معتبر، در غیر این صورت "unknown".
    قاعده: زنجیره‌ی X-Forwarded-For از راست به چپ پیمایش می‌شود و اولین IPای که «پراکسی معتبر» نیست کلاینت است.
    - X-Real-IP را Nginx محلی با IP اتصال ($remote_addr) جایگزین می‌کند؛ اگر این IP پراکسی معتبر نباشد، همان کلاینت است.
    - اگر X-Real-IP خودِ پراکسی خارجی باشد (SSL جلوی Nginx، گزینه‌ی --reverse-proxy-ip)، مقدار قبل از آن در
      X-Forwarded-For (که آن پراکسی افزوده) کلاینت است. مقادیر جلوتر را کلاینت می‌تواند جعل کند و نادیده می‌مانند.
    """
    trusted = _trusted_proxies()
    chain = [p.strip() for p in (request.headers.get("x-forwarded-for") or "").split(",") if p.strip()]
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        # X-Real-IP اتصال واقعی به Nginx است؛ به انتهای زنجیره اضافه می‌شود (معادل $proxy_add_x_forwarded_for)
        if not chain or _normalize_ip(chain[-1]) != _normalize_ip(real_ip):
            chain.append(real_ip)
    elif not chain and request.client:
        return request.client.host
    for hop in reversed(chain):
        if _normalize_ip(hop) not in trusted:
            return hop
    # همه‌ی زنجیره پراکسی معتبر بود (مثلاً فقط loopback): نزدیک‌ترین اتصال
    if chain:
        return chain[-1]
    return request.client.host if request.client else "unknown"


def _normalize_ip(ip: str) -> str:
    """ورودی: رشته IP. خروجی: فرم استاندارد IP؛ رشته نامعتبر بدون تغییر برمی‌گردد."""
    # اگر IP به‌صورت IPv4-mapped IPv6 باشد (مثل ::ffff:192.168.1.10)، برای
    # مقایسه درست با رنج‌های IPv4 ثبت‌شده، به فرم ساده IPv4 تبدیل می‌شود
    try:
        addr = ipaddress.ip_address(ip)
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
            return str(addr.ipv4_mapped)
        return str(addr)
    except ValueError:
        return ip


async def is_ip_allowlist_enforced(db: AsyncSession) -> bool:
    """
    خروجی: True اگر محدودیت IP باید اعمال شود.
    محدودیت فعال است فقط اگر هر دو شرط برقرار باشند:
    ۱) کلید فعال/غیرفعال (که از پنل، مستقل از تعداد رنج‌ها، کنترل می‌شود) روشن باشد
    ۲) حداقل یک رنج هم واقعاً ثبت شده باشد

    اگر کلید روشن باشد ولی هیچ رنجی ثبت نشده، عمداً محدودیت اعمال نمی‌شود —
    وگرنه یک اشتباه ساده (روشن‌کردن کلید قبل از ثبت رنج‌ها) همه را قفل می‌کرد.
    """
    from app.services.system_settings_service import SystemSettingsService

    enabled = await SystemSettingsService(db).get_ip_allowlist_enabled()  # کلید فعال/غیرفعال از تنظیمات سیستم
    if not enabled:
        return False

    # وجود حداقل یک رنج ثبت‌شده
    result = await db.execute(select(IpAllowlistEntry.id).limit(1))
    return result.first() is not None


async def is_ip_allowed(db: AsyncSession, client_ip: str) -> bool:
    """
    ورودی: session دیتابیس و IP کاربر. خروجی: True اگر:
    - هیچ رنجی اصلاً ثبت نشده (محدودیت غیرفعال است)، یا
    - client_ip داخل حداقل یکی از رنج‌های ثبت‌شده باشد
    """
    # خواندن همه رنج‌های CIDR ثبت‌شده
    result = await db.execute(select(IpAllowlistEntry.cidr))
    cidrs = [row[0] for row in result.all()]
    if not cidrs:
        return True

    try:
        normalized = ipaddress.ip_address(_normalize_ip(client_ip))
    except ValueError:
        return False  # IP نامعتبر/ناشناس — با محدودیت فعال، اجازه داده نمی‌شود

    # تطبیق IP با هر رنج؛ اولین تطابق کافی است
    for cidr in cidrs:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue  # یک رکورد خراب نباید کل بررسی را متوقف کند
        if normalized in network:
            return True

    return False
