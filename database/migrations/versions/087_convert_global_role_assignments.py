"""user_roles: تبدیل انتصاب‌های سراسری (بدون سایت) به انتصاب برای تک‌تک سایت‌های موجود

Revision ID: 087
Revises: 086
Create Date: 2026-09-24

از این نسخه «سراسری» به‌عنوان نوع جداگانه‌ی انتصاب کنار گذاشته می‌شود: کسی که باید همه‌جا را
ببیند، نقش را برای همه‌ی سایت‌ها می‌گیرد و کد، داشتن یک نقش/مجوز در همه‌ی سایت‌های موجود را معادل
سراسری حساب می‌کند (core/site_access.py). این Migration هر انتصاب بدون سایت را به یک انتصاب برای
هر سایت موجود تبدیل و ردیف بدون سایت را حذف می‌کند؛ پس دسترسی امروز هیچ‌کس تغییر نمی‌کند، ولی
سایت‌هایی که بعداً ساخته شوند خودکار به کسی داده نمی‌شوند.

مستثنا: نقش superadmin (مدیر کل) و attendance-pilot (قابلیت آزمایشی ثبت تردد با GPS).
downgrade امکان بازسازی ردیف‌های سراسری را ندارد (معلوم نیست کدام ردیف‌ها قبلاً سراسری بوده‌اند) و کاری نمی‌کند.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "087"
down_revision: Union[str, None] = "086"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# نقش‌هایی که انتصاب سراسری‌شان دست نمی‌خورد
_EXCLUDED_ROLES = "('superadmin', 'attendance-pilot')"


def upgrade() -> None:
    # یک انتصاب برای هر سایت موجود (انتصاب‌هایی که از قبل وجود دارند تکرار نمی‌شوند)
    op.execute(
        f"""
        INSERT INTO user_roles (user_id, role_id, site_id)
        SELECT ur.user_id, ur.role_id, s.id
        FROM user_roles ur
        JOIN roles r ON r.id = ur.role_id
        CROSS JOIN sites s
        WHERE ur.site_id IS NULL
          AND r.name NOT IN {_EXCLUDED_ROLES}
          AND NOT EXISTS (
              SELECT 1 FROM user_roles x
              WHERE x.user_id = ur.user_id AND x.role_id = ur.role_id AND x.site_id = s.id
          )
        """
    )
    # حذف ردیف‌های سراسری تبدیل‌شده (فقط اگر حداقل یک سایت وجود دارد، تا کسی دسترسی‌اش را از دست ندهد)
    op.execute(
        f"""
        DELETE FROM user_roles ur
        USING roles r
        WHERE r.id = ur.role_id
          AND ur.site_id IS NULL
          AND r.name NOT IN {_EXCLUDED_ROLES}
          AND EXISTS (SELECT 1 FROM sites)
        """
    )


def downgrade() -> None:
    # بازسازی انتصاب‌های سراسری ممکن نیست؛ دسترسی‌ها در قالب انتصاب‌های سایتی باقی می‌مانند
    pass
