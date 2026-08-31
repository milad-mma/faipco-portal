"""add title to feedback_messages + seed prohibited phrases

Revision ID: 041
Revises: 040
Create Date: 2026-08-31

دو تغییر:
    1) ستون title (عنوان پیام) به feedback_messages اضافه می‌شود - طبق
       درخواست صریح، صفحه ارسال باید فیلد عنوان هم داشته باشد.
    2) فهرست پایه کلمات نامناسب فارسی (استخراج‌شده از یک دیتاست عمومی
       و مجاز - amirshnll/Persian-Swear-Words، مجوز Apache-2.0) از فایل
       جداگانه backend/app/data/prohibited_phrases_seed.txt خوانده و در
       جدول prohibited_phrases درج می‌شود - طبق درخواست صریح، این فهرست
       در یک فایل مستقل نگهداری می‌شود، نه هاردکد در خودِ منطق برنامه.
"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SEED_FILE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "backend"
    / "app"
    / "data"
    / "prohibited_phrases_seed.txt"
)


def upgrade() -> None:
    op.add_column("feedback_messages", sa.Column("title", sa.String(length=255), nullable=True))

    if _SEED_FILE_PATH.exists():
        phrases = [line.strip() for line in _SEED_FILE_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
        conn = op.get_bind()
        insert_sql = sa.text(
            "INSERT INTO prohibited_phrases (phrase) VALUES (:phrase) ON CONFLICT (phrase) DO NOTHING"
        )
        for phrase in phrases:
            conn.execute(insert_sql, {"phrase": phrase})


def downgrade() -> None:
    op.drop_column("feedback_messages", "title")
    # عمداً کلمات seed شده در downgrade حذف نمی‌شوند - چون ممکن است Admin
    # واقعی بین این مدت کلمات دستی دیگری هم اضافه کرده باشد و تشخیص
    # «کدام‌ها از seed اولیه بودند» دیگر امکان‌پذیر نیست.
