"""
منبع واحد «چه کسی چه مجوزی در کدام سایت دارد» (Migration 106).

یک مجوز از دو راه به کاربر می‌رسد:
1. **نقش:** users → user_roles(site_id) → roles → role_permissions → permissions
2. **مستقیم:** users → user_permissions(site_id) → permissions

هر دو مسیر یک «اعطا» (grant) با سه ستون user_id / code / site_id می‌دهند (site_id خالی = همه‌ی سایت‌ها).
هر جایی که مجوز بررسی می‌شود (core/deps، core/site_access، repository کاربر، اعلان‌ها) باید از grants_subquery
استفاده کند تا مجوز مستقیم هم حساب شود — نه این‌که خودش به user_roles join بزند.

مثال:
    g = grants_subquery()
    rows = await db.execute(select(g.c.code, g.c.site_id).where(g.c.user_id == user.id))
"""
from __future__ import annotations

from sqlalchemy import select, union_all

from app.models.user import Permission, RolePermission, UserPermission, UserRole


def grants_subquery():
    """زیرکوئری (user_id, code, site_id) از هر دو مسیر نقش و مجوز مستقیم. هر بار یک شیء تازه (برای چند join در یک کوئری)."""
    via_role = (
        select(UserRole.user_id.label("user_id"), Permission.code.label("code"), UserRole.site_id.label("site_id"))
        .join(RolePermission, RolePermission.role_id == UserRole.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
    )
    direct = (
        select(
            UserPermission.user_id.label("user_id"),
            Permission.code.label("code"),
            UserPermission.site_id.label("site_id"),
        )
        .join(Permission, Permission.id == UserPermission.permission_id)
    )
    return union_all(via_role, direct).subquery("permission_grants")
