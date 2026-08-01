"""
env.py — پیکربندی اجرای Alembic Migrations.

نکته مهم: چون Engine اصلی برنامه Async است ولی Alembic به‌صورت پیش‌فرض Sync کار می‌کند،
اینجا URL دیتابیس را به درایور Sync (psycopg2) تبدیل می‌کنیم — فقط برای اجرای Migration.
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# اضافه کردن مسیر backend به sys.path تا بتوانیم app.* را import کنیم
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.db.session import Base  # noqa: E402
import app.models  # noqa: E402,F401  -- ضروری تا همه مدل‌ها در Base.metadata ثبت شوند

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
# تبدیل postgresql+asyncpg://... به postgresql://... (درایور psycopg2 برای Alembic)
sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
config.set_main_option("sqlalchemy.url", sync_db_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
