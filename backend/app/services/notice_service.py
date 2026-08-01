"""
منطق تجاری سیستم اطلاعیه‌ها + سلسله‌مراتب مجوز ارسال.

منطق تصمیم‌گیری «آیا این کاربر اجازه دارد این Target را هدف بگیرد؟»:

- all (همه سازمان):
    فقط کسی که مجوز سراسری notices.target.all دارد (مثلاً نقش «مدیرعامل»).

- site (یک سایت کامل):
    کسی که مجوز notices.target.site دارد — یا سراسری (HR/مدیرعامل) یا
    Site-scoped دقیقاً برای همان Site (مدیر همان سایت).

- department (یک واحد سازمانی):
    سرپرست مستقیم همان واحد (Department.supervisor_user_id) — بدون نیاز به
    هیچ Role ای؛ یا هرکسی که مجوز notices.target.department برای همان Site
    (سراسری یا Site-scoped) داشته باشد.

- employee (یک پرسنل خاص):
    سرپرست واحدی که آن پرسنل در آن است؛ یا هرکسی که مجوز
    notices.target.employee برای همان Site را داشته باشد.

- role (یک نقش خاص، مثل «همه سرپرستان»):
    فقط با مجوز سراسری notices.target.role (معمولاً HR/مدیرعامل).

superuser همیشه به همه چیز دسترسی دارد.
"""
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.employee import Department, Employee
from app.models.notice import Notice, NoticeStatus, NoticeTarget, NoticeTargetType
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.notice import NoticeCreate
from app.services.push_service import PushService


class NoticePermissionError(Exception):
    """کاربر اجازه هدف قرار دادن یکی از Target های درخواستی را ندارد."""


class NoticeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    # ---------- بررسی مجوز هر Target ----------

    async def _has_permission(self, user: User, code: str, site_id: int | None = None) -> bool:
        if user.is_superuser:
            return True
        codes = await self.user_repo.get_permission_codes(user.id, site_id=site_id)
        return code in codes

    async def _can_target(self, user: User, target_type: NoticeTargetType, target_id: int | None) -> bool:
        if user.is_superuser:
            return True

        if target_type == NoticeTargetType.all:
            return await self._has_permission(user, "notices.target.all")

        if target_type == NoticeTargetType.site:
            return await self._has_permission(user, "notices.target.site", site_id=target_id)

        if target_type == NoticeTargetType.department:
            department = await self.db.get(Department, target_id)
            if department is None:
                return False
            if department.supervisor_user_id == user.id:
                return True
            return await self._has_permission(user, "notices.target.department", site_id=department.site_id)

        if target_type == NoticeTargetType.employee:
            employee = await self.db.get(Employee, target_id)
            if employee is None:
                return False
            if employee.department_id is not None:
                department = await self.db.get(Department, employee.department_id)
                if department is not None and department.supervisor_user_id == user.id:
                    return True
            return await self._has_permission(user, "notices.target.employee", site_id=employee.site_id)

        if target_type == NoticeTargetType.role:
            return await self._has_permission(user, "notices.target.role")

        return False

    # ---------- عملیات اصلی ----------

    async def create_notice(self, sender: User, payload: NoticeCreate) -> Notice:
        for target in payload.targets:
            if not await self._can_target(sender, target.target_type, target.target_id):
                raise NoticePermissionError(
                    f"شما اجازه ارسال اطلاعیه به این مقصد را ندارید: {target.target_type.value}"
                )

        notice = Notice(
            sender_id=sender.id,
            title=payload.title,
            body=payload.body,
            priority=payload.priority,
            status=NoticeStatus.draft,
            publish_at=payload.publish_at,
            expire_at=payload.expire_at,
        )
        for target in payload.targets:
            notice.targets.append(
                NoticeTarget(target_type=target.target_type, target_id=target.target_id)
            )
        self.db.add(notice)
        await self.db.commit()
        # چون expire_on_commit=False است، لیست targets که پیش از commit پر شده
        # همچنان معتبر است — نیازی به refresh رابطه نیست (خطر MissingGreenlet).
        return notice

    async def publish_notice(self, notice_id: int) -> Notice | None:
        result = await self.db.execute(
            select(Notice).options(selectinload(Notice.targets)).where(Notice.id == notice_id)
        )
        notice = result.scalar_one_or_none()
        if notice is None:
            return None
        notice.status = NoticeStatus.published
        if notice.publish_at is None:
            notice.publish_at = datetime.now(timezone.utc)
        await self.db.commit()

        # ارسال Push به کاربران هدف — Best effort: اگر VAPID پیکربندی نشده یا
        # خطایی رخ دهد، هرگز باعث شکست انتشار اطلاعیه نمی‌شود.
        try:
            audience = await self._resolve_audience_user_ids(notice)
            await PushService(self.db).notify_users(
                audience, title=notice.title, body=notice.body, url="/notices"
            )
        except Exception:  # noqa: BLE001
            pass

        return notice

    async def _resolve_audience_user_ids(self, notice: Notice) -> set[int]:
        """برای هر Target اطلاعیه، شناسه کاربرانی که باید Push دریافت کنند را برمی‌گرداند."""
        user_ids: set[int] = set()

        for target in notice.targets:
            if target.target_type == NoticeTargetType.all:
                result = await self.db.execute(select(User.id).where(User.is_active.is_(True)))
                user_ids.update(row[0] for row in result.all())

            elif target.target_type == NoticeTargetType.site:
                result = await self.db.execute(
                    select(User.id)
                    .join(Employee, Employee.id == User.employee_id)
                    .where(Employee.site_id == target.target_id, Employee.is_active.is_(True))
                )
                user_ids.update(row[0] for row in result.all())

            elif target.target_type == NoticeTargetType.department:
                result = await self.db.execute(
                    select(User.id)
                    .join(Employee, Employee.id == User.employee_id)
                    .where(Employee.department_id == target.target_id, Employee.is_active.is_(True))
                )
                user_ids.update(row[0] for row in result.all())

            elif target.target_type == NoticeTargetType.employee:
                result = await self.db.execute(select(User.id).where(User.employee_id == target.target_id))
                user_ids.update(row[0] for row in result.all())

            elif target.target_type == NoticeTargetType.role:
                result = await self.db.execute(select(UserRole.user_id).where(UserRole.role_id == target.target_id))
                user_ids.update(row[0] for row in result.all())

        return user_ids

    async def list_all(self) -> list[Notice]:
        result = await self.db.execute(
            select(Notice).options(selectinload(Notice.targets)).order_by(Notice.created_at.desc())
        )
        return list(result.scalars().unique().all())

    async def list_for_user(self, user: User) -> list[Notice]:
        now = datetime.now(timezone.utc)

        result = await self.db.execute(select(UserRole.role_id).where(UserRole.user_id == user.id))
        role_ids = {row[0] for row in result.all()}

        target_conditions = [NoticeTarget.target_type == NoticeTargetType.all]

        if user.employee_id is not None:
            employee = await self.db.get(Employee, user.employee_id)
            if employee is not None:
                target_conditions.append(
                    and_(
                        NoticeTarget.target_type == NoticeTargetType.site,
                        NoticeTarget.target_id == employee.site_id,
                    )
                )
                if employee.department_id is not None:
                    target_conditions.append(
                        and_(
                            NoticeTarget.target_type == NoticeTargetType.department,
                            NoticeTarget.target_id == employee.department_id,
                        )
                    )
            target_conditions.append(
                and_(
                    NoticeTarget.target_type == NoticeTargetType.employee,
                    NoticeTarget.target_id == user.employee_id,
                )
            )

        if role_ids:
            target_conditions.append(
                and_(
                    NoticeTarget.target_type == NoticeTargetType.role,
                    NoticeTarget.target_id.in_(role_ids),
                )
            )

        stmt = (
            select(Notice)
            .options(selectinload(Notice.targets))
            .join(NoticeTarget, NoticeTarget.notice_id == Notice.id)
            .where(
                Notice.status == NoticeStatus.published,
                or_(Notice.publish_at.is_(None), Notice.publish_at <= now),
                or_(Notice.expire_at.is_(None), Notice.expire_at >= now),
                or_(*target_conditions),
            )
            .order_by(Notice.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all())

    # ---------- کمکی برای UI: کدام Target ها برای کاربر جاری مجازند؟ ----------

    async def get_available_targets(self, user: User) -> dict:
        """
        برای پر کردن هوشمند فرم «اطلاعیه جدید» در پنل — فقط سایت‌ها/واحدهایی
        که کاربر واقعاً اجازه دارد به آن‌ها پیام بدهد را برمی‌گرداند.
        """
        can_all = await self._has_permission(user, "notices.target.all")
        can_role = await self._has_permission(user, "notices.target.role")

        from app.models.site import Site  # import محلی برای پرهیز از Circular Import

        sites_result = await self.db.execute(select(Site).where(Site.is_active.is_(True)))
        all_sites = list(sites_result.scalars().all())

        allowed_site_ids = set()
        for site in all_sites:
            if await self._has_permission(user, "notices.target.site", site_id=site.id):
                allowed_site_ids.add(site.id)

        dept_result = await self.db.execute(select(Department))
        all_departments = list(dept_result.scalars().all())

        allowed_department_ids = set()
        for dept in all_departments:
            if dept.supervisor_user_id == user.id or await self._has_permission(
                user, "notices.target.department", site_id=dept.site_id
            ):
                allowed_department_ids.add(dept.id)

        return {
            "can_target_all": can_all,
            "can_target_role": can_role,
            "site_ids": sorted(allowed_site_ids),
            "department_ids": sorted(allowed_department_ids),
        }
