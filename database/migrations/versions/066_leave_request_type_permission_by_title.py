"""consolidate leave-request type permissions to be shared by title, not per-site

Revision ID: 066
Revises: 065
Create Date: 2026-09-17

طبق تصحیح صریح کاربر: طراحی قبلی (Migration 065) یک Permission جداگانه
به‌ازای هر ردیف LeaveRequestType می‌ساخت - یعنی اگر «مرخصی روزانه
استحقاقی» در دو سایت وجود داشت، دو Permission جدا (leave_requests.view.type.9
و leave_requests.view.type.12) ساخته می‌شد، در حالی که این دو مفهوماً
یک نوع درخواست هستند - باید فقط یک Permission مشترک داشته باشند و
سایت‌بندی مثل بقیه سیستم RBAC از طریق UserRole.site_id (هنگام تخصیص
نقش) انجام شود.

این Migration:
    1. برای هر عنوانِ یکتا در leave_request_types، یک کد مجوز جدید
       بر پایه‌ی خودِ عنوان می‌سازد (leave_requests.view.type.<عنوان‌با‌زیرخط>).
    2. یکی از Permission های قدیمی (طرح شماره‌ای قبلی) با همان عنوان را
       به‌عنوان «بازمانده» انتخاب و به کد جدید تغییر نام می‌دهد - تا
       role_permissions های موجود (مثلاً مجوزی که قبلاً به نقش «حراست»
       داده شده) از بین نروند.
    3. بقیه Permission های تکراری همان عنوان را حذف می‌کند - ولی قبلش
       role_permissions شان را (اگر برای نقشی که «بازمانده» را ندارد) به
       بازمانده منتقل می‌کند تا هیچ مجوز اعطاشده‌ای گم نشود.
"""
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "066"
down_revision: Union[str, None] = "065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slug(title: str) -> str:
    return re.sub(r"\s+", "_", title.strip())


def upgrade() -> None:
    connection = op.get_bind()

    types = connection.execute(sa.text("SELECT id, title FROM leave_request_types")).fetchall()
    types_by_title: dict[str, list[int]] = {}
    for type_id, title in types:
        types_by_title.setdefault(title, []).append(type_id)

    for title, type_ids in types_by_title.items():
        canonical_code = f"leave_requests.view.type.{_slug(title)}"

        old_codes = [f"leave_requests.view.type.{tid}" for tid in type_ids]
        existing_perms = connection.execute(
            sa.text("SELECT id, code FROM permissions WHERE code = ANY(:codes)"), {"codes": old_codes}
        ).fetchall()

        # ممکن است این نوع اصلاً مجوزی نداشته باشد (مثلاً هنوز کسی محدودش نکرده) - رد شو
        if not existing_perms:
            # با این حال مطمئن شو خودِ مجوز مشترک (برای دفعه بعد که لازم شود) وجود دارد
            exists_canonical = connection.execute(
                sa.text("SELECT 1 FROM permissions WHERE code = :code"), {"code": canonical_code}
            ).first()
            if not exists_canonical:
                connection.execute(
                    sa.text("INSERT INTO permissions (code, description) VALUES (:code, :desc)"),
                    {"code": canonical_code, "desc": f"مشاهده درخواست‌های «{title}»"},
                )
            continue

        survivor_id, survivor_code = existing_perms[0]
        if survivor_code != canonical_code:
            connection.execute(
                sa.text("UPDATE permissions SET code = :code, description = :desc WHERE id = :id"),
                {"code": canonical_code, "desc": f"مشاهده درخواست‌های «{title}»", "id": survivor_id},
            )

        for perm_id, _code in existing_perms[1:]:
            # role_permissions این تکراری را به بازمانده منتقل کن (اگر همان نقش قبلاً بازمانده را نداشته باشد)
            connection.execute(
                sa.text(
                    """
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT rp.role_id, :survivor_id
                    FROM role_permissions rp
                    WHERE rp.permission_id = :dup_id
                      AND NOT EXISTS (
                          SELECT 1 FROM role_permissions rp2
                          WHERE rp2.role_id = rp.role_id AND rp2.permission_id = :survivor_id
                      )
                    """
                ),
                {"survivor_id": survivor_id, "dup_id": perm_id},
            )
            connection.execute(sa.text("DELETE FROM permissions WHERE id = :id"), {"id": perm_id})


def downgrade() -> None:
    # ⚠️ برگرداندن دقیق حالت قبلی (یک Permission به‌ازای هر سایت) ممکن
    # نیست چون شناسه‌های قدیمی از بین رفته‌اند - این Migration یک‌طرفه است.
    pass
