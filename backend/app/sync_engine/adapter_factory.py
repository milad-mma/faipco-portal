"""
Factory ساخت Adapter مناسب بر اساس db_type ذخیره‌شده در SiteConnection.

برای اضافه کردن دیتابیس جدید:
1. یک Adapter جدید در app/sync_engine/adapters/ بسازید (ارث‌بری از BaseSiteAdapter)
2. مقدار جدید را به Enum app.models.site.DbType اضافه کنید (+ Migration)
3. اینجا در دیکشنری _ADAPTERS ثبتش کنید
"""
from app.models.site import DbType
from app.sync_engine.adapters.base import BaseSiteAdapter
from app.sync_engine.adapters.mssql_adapter import MSSQLAdapter
from app.sync_engine.adapters.mysql_adapter import MySQLAdapter
from app.sync_engine.adapters.postgresql_adapter import PostgreSQLAdapter

_ADAPTERS: dict[DbType, type[BaseSiteAdapter]] = {
    DbType.postgresql: PostgreSQLAdapter,
    DbType.mysql: MySQLAdapter,
    DbType.mssql: MSSQLAdapter,
}


def get_adapter(
    db_type: DbType, *, host: str, port: int, database: str, username: str, password: str
) -> BaseSiteAdapter:
    adapter_cls = _ADAPTERS.get(db_type)
    if adapter_cls is None:
        raise ValueError(f"دیتابیس از نوع '{db_type}' پشتیبانی نمی‌شود")
    return adapter_cls(host=host, port=port, database=database, username=username, password=password)
