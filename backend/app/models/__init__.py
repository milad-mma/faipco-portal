"""
تمام مدل‌ها اینجا import می‌شوند تا:
1. Alembic برای autogenerate migrations آن‌ها را در metadata ببیند
2. رفرنس‌های رشته‌ای بین مدل‌ها (مثل Mapped["Site"]) در زمان اجرا درست resolve شوند
"""
from app.models.user import User, Role, Permission, RolePermission, UserRole  # noqa: F401
from app.models.site import Site, SiteConnection, DbType, SyncStatus  # noqa: F401
from app.models.employee import Department, Employee, EmployeeMapping  # noqa: F401
from app.models.notice import (  # noqa: F401
    Notice,
    NoticeTarget,
    NoticePriority,
    NoticeStatus,
    NoticeTargetType,
    NoticeType,
)
from app.models.sync_log import SyncLog, SyncRunStatus  # noqa: F401
from app.models.push_subscription import PushSubscription  # noqa: F401
from app.models.notice_read import NoticeRead  # noqa: F401
from app.models.system_setting import SystemSetting  # noqa: F401
from app.models.payroll_receipt import PayrollReceipt  # noqa: F401
from app.models.attendance_card_receipt import AttendanceCardReceipt  # noqa: F401
