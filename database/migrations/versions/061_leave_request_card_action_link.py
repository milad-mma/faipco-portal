"""add card_lookup_action_id_column - Card_No drives ActionId, not independent

Revision ID: 061
Revises: 060
Create Date: 2026-09-13

کشف حیاتی از بررسی مستقیم دیتابیس Kara (سازوکار «درخواست مرخصی/ماموریت»
خطا می‌داد - ریشه‌یابی شد): ستون WF_Requests.ActionId هیچ‌وقت مستقل
انتخاب نمی‌شود - همیشه دقیقاً برابر Cards.WF_ActionID همان کارتی است که
Card_No به آن اشاره می‌کند (تأییدشده با تطبیق کامل هر ۷ رکورد واقعی
WF_Requests با جدول Cards). همچنین WF_Requests.Card_No یک محدودیت
Foreign Key واقعی به Cards.Card_No دارد (FK_WF_Requests_Cards) - یعنی
هر مقدار دلخواه/پیش‌فرض (مثلاً ۰) که در آن جدول وجود نداشته باشد، باعث
شکست INSERT می‌شود؛ این دقیقاً همان علت خطای گزارش‌شده کاربر برای
«ماموریت ساعتی» بود (Card_No آن نوع تنظیم نشده بود، پیش‌فرض ۰ نوشته
می‌شد که در Cards وجود ندارد).

این Migration ستون card_lookup_action_id_column را اضافه می‌کند - تا
هنگام انتخاب یک کارت در پنل ادمین (از فهرست واقعی Cards)، ActionId
مرتبط با همان کارت هم خودکار و درست خوانده/پر شود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "061"
down_revision: Union[str, None] = "060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_request_mappings",
        sa.Column("card_lookup_action_id_column", sa.String(length=128), nullable=True, server_default="WF_ActionID"),
    )


def downgrade() -> None:
    op.drop_column("leave_request_mappings", "card_lookup_action_id_column")
