"""
محاسبه فاصله جغرافیایی بین دو نقطه (فرمول Haversine) — برای تشخیص این‌که
آیا یک مختصات GPS داخل شعاع مجاز یک سایت هست یا نه.
"""
from __future__ import annotations

import math


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """ورودی: عرض و طول جغرافیایی دو نقطه (درجه). خروجی: فاصله روی سطح زمین به متر."""
    earth_radius_meters = 6_371_000  # شعاع میانگین زمین
    # تبدیل درجه به رادیان و محاسبه اختلاف‌ها
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # فرمول Haversine: a نصف وتر مربع، c زاویه مرکزی به رادیان
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_meters * c
