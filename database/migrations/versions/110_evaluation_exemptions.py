"""ارزیابی عملکرد: فهرست «معاف از ارزیابی»

Revision ID: 110
Revises: 109
Create Date: 2026-10-12

پرسنلی که در این فهرست‌اند در «تولید انتساب» ارزیابی نمی‌شوند (با تولید دوباره هم برنمی‌گردند). نوع معافیت:
- target_only («فقط ارزیابی نشود»، پیش‌فرض): ارزیابی نمی‌شود ولی ارزیابی می‌کند؛
- full («کامل»): نه ارزیابی می‌شود و نه ارزیاب است.
مدیریت از صفحه‌ی «ساختار ارزیابی» هر سایت، مجوز performance.structure.manage. هر پرسنل حداکثر یک ردیف.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "110"
down_revision: Union[str, None] = "109"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_exemptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True
        ),
        sa.Column("reason", sa.String(300), nullable=True),
        sa.Column("scope", sa.String(20), nullable=False, server_default="target_only"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("evaluation_exemptions")
