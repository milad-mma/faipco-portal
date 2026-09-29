"""پیش‌فرض نگاشت آدرس و مدرک تحصیلی برای کاراوب (تکمیل 094)

Revision ID: 095
Revises: 094
Create Date: 2026-09-29

094 ستون آدرس را فقط برای table_name دقیقاً «Employee» پر می‌کرد و مدرک تحصیلی به نگاشت اختیاریِ گزارش
ترک کار وابسته بود؛ اگر آن نگاشت خالی بود، مدرک Sync نمی‌شد. اینجا برای هر نگاشتی که جدولش Employee کاراوب است
(با هر شکل نوشتن: dbo.Employee، [dbo].[Employee]، ...) و فیلد مربوط خالی است، مقدار کاراوب گذاشته می‌شود.
فیلدهایی که قبلاً پر شده‌اند دست نمی‌خورند.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "095"
down_revision: Union[str, None] = "094"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_IS_KARA_EMPLOYEE = (
    "lower(replace(replace(regexp_replace(table_name, '^.*\\.', ''), '[', ''), ']', '')) = 'employee'"
)


def upgrade() -> None:
    op.execute(
        f"UPDATE employee_mappings SET address_column = 'Address' "
        f"WHERE coalesce(trim(address_column), '') = '' AND {_IS_KARA_EMPLOYEE}"
    )
    op.execute(
        f"""
        UPDATE employee_mappings SET
            education_column = 'Grade_No',
            education_lookup_table = 'Grades',
            education_lookup_id_column = 'Grade_No',
            education_lookup_name_column = 'Title'
        WHERE coalesce(trim(education_column), '') = '' AND {_IS_KARA_EMPLOYEE}
        """
    )


def downgrade() -> None:
    # مقادیر نگاشت عمداً برگردانده نمی‌شوند (ممکن است بعداً دستی تأیید/ویرایش شده باشند)
    pass
