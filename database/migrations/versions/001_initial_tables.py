"""initial tables

Revision ID: 001
Revises:
Create Date: 2026-07-29

این فایل به‌صورت دستی نوشته شده (نه Autogenerate) تا از باگ شناخته‌شده Alembic
با Enum های PostgreSQL جلوگیری شود: وقتی همان Enum هم به‌صورت صریح ساخته می‌شود
و هم داخل تعریف ستون دوباره تلاش برای ساختش می‌شود، خطای «already exists» می‌دهد.
اینجا هر Enum فقط یک‌بار و به‌صورت صریح ساخته می‌شود (checkfirst=True) و در تمام
ستون‌ها با create_type=False استفاده می‌شود تا دوباره ساخته نشود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------- تعریف Enum های PostgreSQL (فقط یک‌بار ساخته می‌شوند) ----------
db_type_enum = postgresql.ENUM("postgresql", "mysql", "mssql", name="db_type_enum", create_type=False)
sync_status_enum = postgresql.ENUM(
    "never", "success", "failed", "partial", "running", name="sync_status_enum", create_type=False
)
notice_priority_enum = postgresql.ENUM(
    "low", "normal", "high", "urgent", name="notice_priority_enum", create_type=False
)
notice_status_enum = postgresql.ENUM(
    "draft", "published", "expired", name="notice_status_enum", create_type=False
)
notice_target_type_enum = postgresql.ENUM(
    "all", "site", "department", "role", "employee", name="notice_target_type_enum", create_type=False
)
sync_run_status_enum = postgresql.ENUM(
    "running", "success", "failed", "partial", name="sync_run_status_enum", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()

    # ---------- ساخت Enum ها (هرکدام دقیقاً یک‌بار) ----------
    db_type_enum.create(bind, checkfirst=True)
    sync_status_enum.create(bind, checkfirst=True)
    notice_priority_enum.create(bind, checkfirst=True)
    notice_status_enum.create(bind, checkfirst=True)
    notice_target_type_enum.create(bind, checkfirst=True)
    sync_run_status_enum.create(bind, checkfirst=True)

    # ---------- sites ----------
    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_sites_code"),
    )
    op.create_index("ix_sites_code", "sites", ["code"])

    # ---------- departments ----------
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("site_id", "code", name="uq_department_site_code"),
    )

    # ---------- employees ----------
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("personnel_code", sa.String(length=64), nullable=False),
        sa.Column("national_code", sa.String(length=32), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("last_name", sa.String(length=128), nullable=False),
        sa.Column("mobile", sa.String(length=32), nullable=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "department_id",
            sa.Integer(),
            sa.ForeignKey("departments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("site_id", "personnel_code", name="uq_employee_site_personnel_code"),
    )
    op.create_index("ix_employees_personnel_code", "employees", ["personnel_code"])
    op.create_index("ix_employees_national_code", "employees", ["national_code"])

    # ---------- users ----------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    # ---------- roles ----------
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    # ---------- permissions ----------
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"])

    # ---------- role_permissions ----------
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "permission_id",
            sa.Integer(),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    # ---------- user_roles ----------
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=True
        ),
        sa.UniqueConstraint("user_id", "role_id", "site_id", name="uq_user_role_site"),
    )

    # ---------- site_connections ----------
    op.create_table(
        "site_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("db_type", db_type_enum, nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("database_name", sa.String(length=128), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("password_encrypted", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sync_status_enum, nullable=False, server_default="never"),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("site_id", name="uq_site_connections_site_id"),
    )

    # ---------- employee_mappings ----------
    op.create_table(
        "employee_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("table_name", sa.String(length=128), nullable=False),
        sa.Column("personnel_code_column", sa.String(length=128), nullable=False),
        sa.Column("national_code_column", sa.String(length=128), nullable=True),
        sa.Column("first_name_column", sa.String(length=128), nullable=False),
        sa.Column("last_name_column", sa.String(length=128), nullable=False),
        sa.Column("mobile_column", sa.String(length=128), nullable=True),
        sa.Column("is_active_column", sa.String(length=128), nullable=True),
        sa.Column("department_column", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("site_id", name="uq_employee_mappings_site_id"),
    )

    # ---------- notices ----------
    op.create_table(
        "notices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("priority", notice_priority_enum, nullable=False, server_default="normal"),
        sa.Column("status", notice_status_enum, nullable=False, server_default="draft"),
        sa.Column("publish_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ---------- notice_targets ----------
    op.create_table(
        "notice_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "notice_id", sa.Integer(), sa.ForeignKey("notices.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("target_type", notice_target_type_enum, nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=True),
    )

    # ---------- sync_logs ----------
    op.create_table(
        "sync_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sync_run_status_enum, nullable=False, server_default="running"),
        sa.Column("inserted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deactivated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("sync_logs")
    op.drop_table("notice_targets")
    op.drop_table("notices")
    op.drop_table("employee_mappings")
    op.drop_table("site_connections")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
    op.drop_table("employees")
    op.drop_table("departments")
    op.drop_table("sites")

    bind = op.get_bind()
    sync_run_status_enum.drop(bind, checkfirst=True)
    notice_target_type_enum.drop(bind, checkfirst=True)
    notice_status_enum.drop(bind, checkfirst=True)
    notice_priority_enum.drop(bind, checkfirst=True)
    sync_status_enum.drop(bind, checkfirst=True)
    db_type_enum.drop(bind, checkfirst=True)
