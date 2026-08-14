"""
منطق واقعی «محدودکردن ورود به رنج‌های IP مجاز» — استفاده در auth_service.py.

نکته مهم درباره تشخیص IP واقعی کاربر: این سرور پشت Nginx است (که خودش هم
ممکن است پشت یک Reverse Proxy خارجی برای SSL باشد — یعنی دو لایه Proxy).
چون uvicorn با فلگ --proxy-headers اجرا نمی‌شود، Request.client.host همیشه
127.0.0.1 (اتصال محلی از Nginx) خواهد بود، نه IP واقعی کاربر. Nginx با
`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` این هدر را
به هر Proxy جدید در زنجیره اضافه (نه جایگزین) می‌کند — پس با فرض این‌که
Reverse Proxy خارجی هم همین رفتار استاندارد را دارد، **اولین مقدار** در
X-Forwarded-For همیشه IP اصلی کاربر است، صرف‌نظر از تعداد Proxy های بین راه.
اگر این هدر اصلاً نبود (مثلاً تست مستقیم به بک‌اند)، از Request.client.host
استفاده می‌شود.
"""
from __future__ import annotations

import ipaddress

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ip_allowlist_entry import IpAllowlistEntry


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip
    return request.client.host if request.client else "unknown"


def _normalize_ip(ip: str) -> str:
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
    """اگر حداقل یک رنج ثبت شده باشد، محدودیت فعال است."""
    result = await db.execute(select(IpAllowlistEntry.id).limit(1))
    return result.first() is not None


async def is_ip_allowed(db: AsyncSession, client_ip: str) -> bool:
    """
    True اگر:
    - هیچ رنجی اصلاً ثبت نشده (محدودیت غیرفعال است)، یا
    - client_ip داخل حداقل یکی از رنج‌های ثبت‌شده باشد
    """
    result = await db.execute(select(IpAllowlistEntry.cidr))
    cidrs = [row[0] for row in result.all()]
    if not cidrs:
        return True

    try:
        normalized = ipaddress.ip_address(_normalize_ip(client_ip))
    except ValueError:
        return False  # IP نامعتبر/ناشناس — با محدودیت فعال، اجازه داده نمی‌شود

    for cidr in cidrs:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            continue  # یک رکورد خراب نباید کل بررسی را متوقف کند
        if normalized in network:
            return True

    return False
