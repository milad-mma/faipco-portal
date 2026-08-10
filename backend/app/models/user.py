"""
مدل‌های سیستم Authentication و RBAC.

طراحی:
- User: حساب ورود به Portal. می‌تواند (اختیاری) به یک رکورد Employee سینک‌شده وصل باشد.
- Role: نقش (مثلاً "مدیر منابع انسانی سایت ۲")
- Permission: مجوز اتمی (مثلاً "employees.view")
- UserRole: نقش هر کاربر - با site_id اختیاری تا بشود یک نقش را فقط برای یک Site
  به کاربر داد (مثلاً "HR Manager فقط در سایت A"). اگر site_id خالی باشد یعنی نقش سراسری است.
- RolePermission: مجوزهای هر نقش
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # اتصال اختیاری به رکورد پرسنلی سینک‌شده (کاربر می‌تواند بدون Employee هم وجود داشته باشد؛ مثلاً Admin سیستم)
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # اگر True باشد یعنی این کاربر (یا Admin به‌جایش) یک رمز عبور واقعی تعیین
    # کرده — از این پس ورود پرسنل با «کد پرسنلی + کد ملی» دیگر کار نمی‌کند و
    # فقط «کد پرسنلی + همین رمز عبور» معتبر است. تا وقتی False است، password_hash
    # یک مقدار تصادفی غیرقابل‌حدس است (نه چیزی که کسی واقعاً بداند) و ورود
    # همچنان از مسیر کد ملی انجام می‌شود.
    has_custom_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # نقش‌های سیستمی (مثل superadmin) توسط کاربر عادی قابل حذف نیستند
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    # مثال: employees.view / employees.create / notices.create / sites.manage
    code: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class RolePermission(Base):
    """جدول واسط نقش <-> مجوز"""
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped["Role"] = relationship(back_populates="permissions")
    permission: Mapped["Permission"] = relationship()


class UserRole(Base):
    """
    جدول واسط کاربر <-> نقش.
    site_id اختیاری: اگر مقدار داشته باشد، این نقش فقط برای همان Site معتبر است.
    """
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "site_id", name="uq_user_role_site"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    site_id: Mapped[int | None] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="roles")
    role: Mapped["Role"] = relationship()
