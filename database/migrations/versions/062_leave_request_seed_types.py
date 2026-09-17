"""seed the 3 initial leave request types from real WF_Requests samples

Revision ID: 062
Revises: 061
Create Date: 2026-09-16

طبق درخواست صریح کاربر: فعلاً فقط همین سه نوع درخواست در نظر گرفته
می‌شوند - مقادیر (Card_No/ActionId/OperationsID) مستقیماً از سه رکورد
واقعی نمونه‌ی ثبت‌شده در WF_Requests (RequestId=22/27/29) خوانده شده‌اند
(با بررسی مستقیم دیتابیس Kara):

    - مرخصی روزانه استحقاقی (RequestId=22): OperationsID=5، ActionId=1،
      Card_No=57، is_mission=False، is_hourly=False
    - مرخصی ساعتی استحقاقی (RequestId=27): OperationsID=5، ActionId=3،
      Card_No=17، is_mission=False، is_hourly=True
    - ماموریت ساعتی (RequestId=29): OperationsID=3، ActionId=9،
      Card_No=9، is_mission=True، is_hourly=True

⚠️ چون طبق درخواست صریح کاربر، صفحه تنظیمات (که امکان افزودن دستی نوع
از پنل ادمین را می‌داد) فعلاً حذف شده، تنها راه فعلی برای وارد کردن این
سه نوع، همین Migration است. برای هر سایتی که از قبل Mapping درخواست
مرخصی/ماموریت تنظیم کرده (یعنی این قابلیت برایش فعال است)، این سه نوع
اضافه می‌شود - در صورت اجرای دوباره، تکراری اضافه نمی‌شود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "062"
down_revision: Union[str, None] = "061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_TYPES = [
    # title, is_mission, is_hourly, action_id, operation_id, card_no
    ("مرخصی روزانه استحقاقی", False, False, 1, 5, 57),
    ("مرخصی ساعتی استحقاقی", False, True, 3, 5, 17),
    ("ماموریت ساعتی", True, True, 9, 3, 9),
]


def upgrade() -> None:
    connection = op.get_bind()
    site_ids = connection.execute(sa.text("SELECT site_id FROM leave_request_mappings")).scalars().all()

    for site_id in site_ids:
        for title, is_mission, is_hourly, action_id, operation_id, card_no in SEED_TYPES:
            exists = connection.execute(
                sa.text("SELECT 1 FROM leave_request_types WHERE site_id = :site_id AND title = :title"),
                {"site_id": site_id, "title": title},
            ).first()
            if exists:
                continue
            connection.execute(
                sa.text(
                    """
                    INSERT INTO leave_request_types
                        (site_id, title, is_mission, is_hourly, is_active, action_id, operation_id, card_no)
                    VALUES
                        (:site_id, :title, :is_mission, :is_hourly, true, :action_id, :operation_id, :card_no)
                    """
                ),
                {
                    "site_id": site_id,
                    "title": title,
                    "is_mission": is_mission,
                    "is_hourly": is_hourly,
                    "action_id": action_id,
                    "operation_id": operation_id,
                    "card_no": card_no,
                },
            )


def downgrade() -> None:
    connection = op.get_bind()
    titles = [t[0] for t in SEED_TYPES]
    connection.execute(
        sa.text("DELETE FROM leave_request_types WHERE title = ANY(:titles)"),
        {"titles": titles},
    )
