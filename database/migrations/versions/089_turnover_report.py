"""گزارش جذب و ترک کار: نگاشت ستون‌های ترک کار/تحصیلات، دسته‌بندی علت ترک کار و مجوزها

Revision ID: 089
Revises: 088
Create Date: 2026-09-26

- employee_mappings: ستون تاریخ و علت ترک کار (کاراوب: End_Date / Cut_Reason)، ستون مدرک تحصیلی و
  جدول Lookup آن (کاراوب: Grade_No / Grades.Title) و «ماه شروع آمار» (مثل 1403/06).
  گزارش مستقیم از دیتابیس منبع خوانده می‌شود؛ پرسنل قطع‌همکاری‌شده وارد پرتال نمی‌شوند.
- termination_reason_categories: دسته‌های علت ترک کار با گروه آماری
  (voluntary / involuntary / probation / other / excluded) و مبنای قانونی (قانون کار).
- termination_reason_aliases: متن‌های نرمال‌شده‌ی علت ترک کار (متن آزاد کاراوب) و دسته‌ی هر کدام.
- مجوزها: reports.turnover (مشاهده و خروجی، سایت‌محور) و reports.turnover_categories (ویرایش دسته‌ها، کل سیستم).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "089"
down_revision: Union[str, None] = "088"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MAPPING_COLUMNS = [
    "termination_date_column",
    "termination_reason_column",
    "education_column",
    "education_lookup_table",
    "education_lookup_id_column",
    "education_lookup_name_column",
]

# (کلید، عنوان، گروه، مبنای قانونی، ترتیب)
_CATEGORIES = [
    ("resignation", "استعفا", "voluntary", "قانون کار، ماده ۲۱ بند «و»", 10),
    ("abandonment", "ترک کار", "voluntary", "رویه‌ی مراجع حل اختلاف (در متن قانون تعریف نشده)", 20),
    ("probation", "فسخ در دوره‌ی آزمایشی", "probation", "قانون کار، ماده ۱۱", 30),
    ("contract_end", "انقضای مدت / عدم تمدید قرارداد", "involuntary", "قانون کار، ماده ۲۱ بند «د»", 40),
    ("task_end", "پایان کار معین", "involuntary", "قانون کار، ماده ۲۱ بند «هـ»", 50),
    ("layoff", "تعدیل نیرو", "involuntary", "قانون کار، ماده ۲۱ بند «ز» و ماده ۹ قانون تسهیل نوسازی صنایع", 60),
    ("dismissal", "اخراج انضباطی", "involuntary", "قانون کار، ماده ۲۷", 70),
    ("retirement", "بازنشستگی", "other", "قانون کار، ماده ۲۱ بند «ب»", 80),
    ("disability", "از کارافتادگی کلی", "other", "قانون کار، ماده ۲۱ بند «ج»", 90),
    ("death", "فوت", "other", "قانون کار، ماده ۲۱ بند «الف»", 100),
    ("record_error", "خطای ثبت (خارج از آمار)", "excluded", "اصلاح رکورد؛ خروج واقعی نیست", 110),
]

# متن نرمال‌شده (خروجی normalize_reason در app/services/turnover_report_service.py) -> کلید دسته
_ALIASES = [
    ("استعفا", "resignation"),
    ("استعفا (روزمزد)", "resignation"),
    ("ترک", "abandonment"),
    ("ترک کار", "abandonment"),
    ("عدم تمدید قرارداد", "contract_end"),
    ("تعدیل", "layoff"),
    ("نارضایتی سرپرست", "dismissal"),
    ("از کار افتادگی", "disability"),
    ("کدپرسنلی اشتباه", "record_error"),
    ("شماره پرسنلی اشتباه", "record_error"),
    ("اشتباه کد پرسنلی", "record_error"),
    ("اشتباه شدن کد پرسنلی", "record_error"),
    ("ترک کار-کدپرسنلی صحیح 235209", "record_error"),
]


def upgrade() -> None:
    for name in _MAPPING_COLUMNS:
        op.add_column("employee_mappings", sa.Column(name, sa.String(128), nullable=True))
    op.add_column("employee_mappings", sa.Column("turnover_start_month", sa.String(7), nullable=True))

    categories = op.create_table(
        "termination_reason_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(40), nullable=True, unique=True),  # دسته‌های پیش‌فرض؛ دسته‌ی ساخت کاربر NULL
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("group", sa.String(20), nullable=False),
        sa.Column("legal_basis", sa.String(255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "termination_reason_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("normalized_text", sa.String(400), nullable=False, unique=True),
        sa.Column("sample_text", sa.String(400), nullable=False),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("termination_reason_categories.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.bulk_insert(
        categories,
        [
            {"id": i + 1, "key": key, "title": title, "group": group, "legal_basis": basis, "sort_order": order}
            for i, (key, title, group, basis, order) in enumerate(_CATEGORIES)
        ],
    )
    op.execute("SELECT setval(pg_get_serial_sequence('termination_reason_categories', 'id'), (SELECT MAX(id) FROM termination_reason_categories))")
    ids = {key: i + 1 for i, (key, *_rest) in enumerate(_CATEGORIES)}
    aliases = sa.table(
        "termination_reason_aliases",
        sa.column("normalized_text", sa.String),
        sa.column("sample_text", sa.String),
        sa.column("category_id", sa.Integer),
    )
    op.bulk_insert(aliases, [{"normalized_text": t, "sample_text": t, "category_id": ids[k]} for t, k in _ALIASES])

    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('reports.turnover', 'مشاهده و خروجی گزارش جذب و ترک کار (سایت‌محور)'),
        ('reports.turnover_categories', 'ویرایش دسته‌بندی علت‌های ترک کار (اثر روی گزارش همه‌ی سایت‌ها)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ('reports.turnover','reports.turnover_categories'))"
    )
    op.execute("DELETE FROM permissions WHERE code IN ('reports.turnover','reports.turnover_categories')")
    op.drop_table("termination_reason_aliases")
    op.drop_table("termination_reason_categories")
    op.drop_column("employee_mappings", "turnover_start_month")
    for name in reversed(_MAPPING_COLUMNS):
        op.drop_column("employee_mappings", name)
