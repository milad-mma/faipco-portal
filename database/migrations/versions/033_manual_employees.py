"""add is_manually_created to employees + employees.create/employees.view permissions

Revision ID: 033
Revises: 032
Create Date: 2026-08-27

قابلیت «افزودن دستی پرسنل» — طبق درخواست صریح کارفرما، مجوز
employees.create باید واقعاً چیزی را باز کند. تا امروز این مجوز فقط
به‌عنوان مثال در یک Docstring وجود داشت، هیچ Endpointی به آن گوش
نمی‌داد.

is_manually_created فقط برای شفافیت/گزارش‌گیری است — پرسنلی که این‌طور
ثبت می‌شوند، اگر بعداً همان personnel_code در منبع Sync واقعی هم ظاهر
شود، طبق منطق موجود Sync Engine (که بر اساس personnel_code+site_id
Upsert می‌کند) به‌طور طبیعی به‌روزرسانی/ادغام می‌شوند — نه خطا/تکراری.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("is_manually_created", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('employees.view', 'مشاهده لیست کامل پرسنل (صفحه «پرسنل»)')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('employees.create', 'افزودن دستی یک پرسنل (خارج از Sync Engine)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE code IN ('employees.view', 'employees.create')")
    op.drop_column("employees", "is_manually_created")
