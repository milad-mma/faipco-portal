"""initial tables

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ENUM types ────────────────────────────────────────────
    db_type_enum = postgresql.ENUM('postgresql', 'mysql', 'mssql', name='dbtype', create_type=False)
    notice_priority_enum = postgresql.ENUM('low', 'normal', 'high', 'urgent', name='noticepriority', create_type=False)
    notice_status_enum = postgresql.ENUM('draft', 'published', 'archived', name='noticestatus', create_type=False)
    notice_target_type_enum = postgresql.ENUM('all', 'site', 'department', 'role', 'employee', name='noticetargettype', create_type=False)
    sync_status_enum = postgresql.ENUM('running', 'success', 'failed', name='syncstatus', create_type=False)

    op.execute("CREATE TYPE dbtype AS ENUM ('postgresql', 'mysql', 'mssql')")
    op.execute("CREATE TYPE noticepriority AS ENUM ('low', 'normal', 'high', 'urgent')")
    op.execute("CREATE TYPE noticestatus AS ENUM ('draft', 'published', 'archived')")
    op.execute("CREATE TYPE noticetargettype AS ENUM ('all', 'site', 'department', 'role', 'employee')")
    op.execute("CREATE TYPE syncstatus AS ENUM ('running', 'success', 'failed')")

    # ── sites ─────────────────────────────────────────────────
    op.create_table(
        'sites',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('code', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )

    # ── site_connections ──────────────────────────────────────
    op.create_table(
        'site_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), unique=True),
        sa.Column('db_type', sa.Enum('postgresql', 'mysql', 'mssql', name='dbtype'), nullable=False),
        sa.Column('host', sa.String(255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('database_name', sa.String(255), nullable=False),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('password_encrypted', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('last_sync', sa.DateTime(timezone=True)),
    )

    # ── employee_mappings ─────────────────────────────────────
    op.create_table(
        'employee_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), unique=True),
        sa.Column('table_name', sa.String(255), nullable=False),
        sa.Column('personnel_code_column', sa.String(100), nullable=False),
        sa.Column('national_code_column', sa.String(100), nullable=False),
        sa.Column('first_name_column', sa.String(100), nullable=False),
        sa.Column('last_name_column', sa.String(100), nullable=False),
        sa.Column('mobile_column', sa.String(100)),
        sa.Column('department_column', sa.String(100)),
    )

    # ── departments ───────────────────────────────────────────
    op.create_table(
        'departments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE')),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text()),
    )

    # ── employees ─────────────────────────────────────────────
    op.create_table(
        'employees',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('personnel_code', sa.String(50), nullable=False),
        sa.Column('national_code', sa.String(20)),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('mobile', sa.String(20)),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id')),
        sa.Column('department_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('departments.id')),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('synced_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('personnel_code', 'site_id', name='uq_employee_site'),
    )

    # ── users ─────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('username', sa.String(100), unique=True, nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(200)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_superuser', sa.Boolean(), default=False),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('employees.id')),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('last_login', sa.DateTime(timezone=True)),
    )

    # ── roles ─────────────────────────────────────────────────
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )

    # ── permissions ───────────────────────────────────────────
    op.create_table(
        'permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('description', sa.Text()),
    )

    # ── role_permissions ──────────────────────────────────────
    op.create_table(
        'role_permissions',
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True),
    )

    # ── user_roles ────────────────────────────────────────────
    op.create_table(
        'user_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('roles.id', ondelete='CASCADE')),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id')),
    )

    # ── refresh_tokens ────────────────────────────────────────
    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE')),
        sa.Column('token_hash', sa.String(255), unique=True, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('is_revoked', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )

    # ── notices ───────────────────────────────────────────────
    op.create_table(
        'notices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('priority', sa.Enum('low', 'normal', 'high', 'urgent', name='noticepriority'), default='normal'),
        sa.Column('status', sa.Enum('draft', 'published', 'archived', name='noticestatus'), default='draft'),
        sa.Column('publish_at', sa.DateTime(timezone=True)),
        sa.Column('expire_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True)),
    )

    # ── notice_targets ────────────────────────────────────────
    op.create_table(
        'notice_targets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('notice_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('notices.id', ondelete='CASCADE')),
        sa.Column('target_type', sa.Enum('all', 'site', 'department', 'role', 'employee', name='noticetargettype'), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True)),
    )

    # ── sync_logs ─────────────────────────────────────────────
    op.create_table(
        'sync_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id')),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.Enum('running', 'success', 'failed', name='syncstatus'), default='running'),
        sa.Column('records_synced', sa.Integer(), default=0),
        sa.Column('error_message', sa.Text()),
    )

    # ── indexes ───────────────────────────────────────────────
    op.create_index('ix_employees_site_id', 'employees', ['site_id'])
    op.create_index('ix_employees_national_code', 'employees', ['national_code'])
    op.create_index('ix_sync_logs_site_id', 'sync_logs', ['site_id'])
    op.create_index('ix_notice_targets_notice_id', 'notice_targets', ['notice_id'])


def downgrade() -> None:
    op.drop_table('sync_logs')
    op.drop_table('notice_targets')
    op.drop_table('notices')
    op.drop_table('refresh_tokens')
    op.drop_table('user_roles')
    op.drop_table('role_permissions')
    op.drop_table('permissions')
    op.drop_table('roles')
    op.drop_table('users')
    op.drop_table('employees')
    op.drop_table('departments')
    op.drop_table('employee_mappings')
    op.drop_table('site_connections')
    op.drop_table('sites')

    op.execute("DROP TYPE IF EXISTS syncstatus")
    op.execute("DROP TYPE IF EXISTS noticetargettype")
    op.execute("DROP TYPE IF EXISTS noticestatus")
    op.execute("DROP TYPE IF EXISTS noticepriority")
    op.execute("DROP TYPE IF EXISTS dbtype")
