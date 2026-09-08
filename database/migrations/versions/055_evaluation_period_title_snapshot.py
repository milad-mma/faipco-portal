"""add period_title_snapshot to evaluations

Revision ID: 055
Revises: 054
Create Date: 2026-09-08

رفع یک گپ واقعی: هنگام طراحی اولیه Historical Snapshot برای Evaluation
(ارزیاب/ارزیابی‌شونده/سایت/واحد/فرم)، عنوان دوره ارزیابی فراموش شده
بود - یعنی «نتایج ارزیابی من» به‌جای عنوان دوره، فقط عنوان فرم را نشان
می‌داد. حالا که عنوان دوره هم قابل‌ویرایش شده (طبق قابلیت قبلی)، نگه‌داشتن
Snapshot اهمیت بیشتری هم پیدا کرده - نتایج قدیمی نباید با تغییر بعدی
عنوان دوره عوض شوند.

⚠️ برای ارزیابی‌های از قبل موجود (اگر باشند)، مقدار این ستون از روی
EvaluationAssignment -> EvaluationPeriod فعلی پر می‌شود - بهترین تخمین
ممکن، چون در لحظه واقعی ثبت، این عنوان ذخیره نشده بود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "055"
down_revision: Union[str, None] = "054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("evaluations", sa.Column("period_title_snapshot", sa.String(length=255), nullable=True))
    op.execute(
        """
        UPDATE evaluations e
        SET period_title_snapshot = ep.title
        FROM evaluation_assignments ea
        JOIN evaluation_periods ep ON ep.id = ea.period_id
        WHERE e.assignment_id = ea.id
        """
    )
    op.alter_column("evaluations", "period_title_snapshot", nullable=False)


def downgrade() -> None:
    op.drop_column("evaluations", "period_title_snapshot")
