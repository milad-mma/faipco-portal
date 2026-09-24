"""insurance_members.document_rejected_at: ثبت رد مدرک کفالت توسط مدیر

Revision ID: 088
Revises: 087
Create Date: 2026-09-24

وقتی مدیر بیمه تکمیلی مدرک کفالت/حضانت یک عضو را در پنل رد می‌کند، فایل حذف و زمان رد در این
ستون ثبت می‌شود تا هم در فهرست مدیریت (فیلتر «مدرک ردشده») و هم در صفحه‌ی پرسنل (هشدار «مدرک این
عضو تأیید نشد») دیده شود. با ویرایش و ثبت دوباره‌ی فرم، اعضا از نو ساخته می‌شوند و این مقدار پاک می‌شود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "088"
down_revision: Union[str, None] = "087"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("insurance_members", sa.Column("document_rejected_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("insurance_members", "document_rejected_at")
