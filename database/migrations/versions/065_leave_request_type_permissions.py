"""replace leave_request_type_viewers with a dedicated Permission per type

Revision ID: 065
Revises: 064
Create Date: 2026-09-17

طبق درخواست صریح کاربر: به‌جای یک جدول اختصاصی جدا برای مجوز مشاهده به
تفکیک نوع، از همان سیستم نقش/مجوز (RBAC) موجود پروژه استفاده می‌شود -
دقیقاً مثل leave_requests.view/leave_requests.manage. از این پس، هر
LeaveRequestType یک Permission اختصاصی خودش دارد با کد
`leave_requests.view.type.<id>` - تا از همان صفحه «مدیریت نقش/مجوز»
بشود یک نقش (مثلاً «حراست») ساخت که فقط همین یک مجوز را دارد، و آن نقش
را (با site_id مشخص در UserRole) به کاربر داد.

این Migration:
    1. جدول قبلی leave_request_type_viewers را حذف می‌کند (دیگر لازم نیست).
    2. برای هر LeaveRequestType موجود، یک Permission متناظر می‌سازد
       (Backfill - تا نوع‌های از قبل ساخته‌شده هم مجوز خودشان را داشته باشند).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "065"
down_revision: Union[str, None] = "064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("leave_request_type_viewers")

    connection = op.get_bind()
    types = connection.execute(sa.text("SELECT id, title FROM leave_request_types")).fetchall()
    for type_id, title in types:
        code = f"leave_requests.view.type.{type_id}"
        exists = connection.execute(
            sa.text("SELECT 1 FROM permissions WHERE code = :code"), {"code": code}
        ).first()
        if exists:
            continue
        connection.execute(
            sa.text("INSERT INTO permissions (code, description) VALUES (:code, :description)"),
            {"code": code, "description": f"مشاهده درخواست‌های «{title}»"},
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("DELETE FROM permissions WHERE code LIKE 'leave_requests.view.type.%'"))

    op.create_table(
        "leave_request_type_viewers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "leave_type_id",
            sa.Integer(),
            sa.ForeignKey("leave_request_types.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
