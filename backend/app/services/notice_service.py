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

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.employee import Department, Employee
from app.models.notice import Notice, NoticeStatus, NoticeTarget, NoticeTargetType
from app.models.notice_read import NoticeRead
from app.models.user import Role, User, UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.notice import (
    NoticeCreate,
    NoticeDetailOut,
    NoticeOut,
    NoticeReaderOut,
    NoticeTargetDescription,
    NoticeTargetOut,
)
from app.services.push_service import PushService


class NoticePermissionError(Exception):
    """کاربر اجازه هدف قرار دادن یکی از Target های درخواستی را ندارد."""


async def send_publish_notifications(notice_id: int) -> None:
    """
    ارسال Push به مخاطبان یک اطلاعیه — طراحی‌شده برای اجرا در Background
    (بعد از پاسخ HTTP، نه در همان درخواست). چون این تابع مستقل از هر
    Request اجرا می‌شود، Session دیتابیس مخصوص خودش را می‌سازد (Session
    درخواست اصلی تا این لحظه بسته شده است).
    """
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Notice).options(selectinload(Notice.targets)).where(Notice.id == notice_id)
            )
            notice = result.scalar_one_or_none()
            if notice is None:
                return
            service = NoticeService(db)
            audience = await service._resolve_audience_user_ids(notice)
            await PushService(db).notify_users(audience, title=notice.title, body=notice.body, url="/notices")
        except Exception:  # noqa: BLE001 - ارسال Push هرگز نباید کل عملیات را متوقف کند
            pass


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
        """
        فقط انتشار را ثبت می‌کند و بلافاصله برمی‌گردد — سریع و بدون مکث.
        ارسال Push به کاربران هدف در پس‌زمینه و جداگانه انجام می‌شود
        (به send_publish_notifications در endpoint مراجعه کنید) تا کندی
        شبکه هنگام ارسال چندین Push، پاسخ HTTP را معطل نگه ندارد.
        """
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
        notices = list(result.scalars().unique().all())
        if not notices:
            return []

        # اطلاعیه‌هایی که کاربر جاری قبلاً باز/مشاهده کرده — برای رنگ‌بندی متفاوت
        # پیام‌های خوانده‌شده در UI
        notice_ids = [n.id for n in notices]
        read_result = await self.db.execute(
            select(NoticeRead.notice_id).where(
                NoticeRead.notice_id.in_(notice_ids), NoticeRead.user_id == user.id
            )
        )
        read_ids = {row[0] for row in read_result.all()}

        return [
            NoticeOut(
                id=n.id,
                sender_id=n.sender_id,
                title=n.title,
                body=n.body,
                priority=n.priority,
                status=n.status,
                publish_at=n.publish_at,
                expire_at=n.expire_at,
                created_at=n.created_at,
                targets=[
                    NoticeTargetOut(target_type=t.target_type, target_id=t.target_id) for t in n.targets
                ],
                is_read=n.id in read_ids,
            )
            for n in notices
        ]

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

        # can_target_employee: سراسری، یا Site-scoped برای حداقل یک سایت، یا سرپرست حداقل یک واحد
        can_employee = user.is_superuser or await self._has_permission(user, "notices.target.employee")
        if not can_employee:
            for site in all_sites:
                if await self._has_permission(user, "notices.target.employee", site_id=site.id):
                    can_employee = True
                    break
        if not can_employee:
            result = await self.db.execute(
                select(Department.id).where(Department.supervisor_user_id == user.id).limit(1)
            )
            can_employee = result.first() is not None

        # میان‌بر «ارسال به سرپرست واحد(ها)»: سرپرست‌های واقعی همان واحدهایی
        # که این کاربر اجازه هدف‌گیری‌شان را دارد (Employee این افراد را برمی‌گرداند
        # تا بشود مستقیماً به‌عنوان Target از نوع employee استفاده کرد).
        supervisor_employees: list[dict] = []
        supervisor_user_ids = {
            dept.supervisor_user_id
            for dept in all_departments
            if dept.id in allowed_department_ids and dept.supervisor_user_id is not None
        }
        if supervisor_user_ids:
            result = await self.db.execute(
                select(Employee.id, Employee.first_name, Employee.last_name, Employee.personnel_code)
                .join(User, User.employee_id == Employee.id)
                .where(User.id.in_(supervisor_user_ids))
            )
            supervisor_employees = [
                {"id": r[0], "first_name": r[1], "last_name": r[2], "personnel_code": r[3]}
                for r in result.all()
            ]

        return {
            "can_target_all": can_all,
            "can_target_role": can_role,
            "can_target_employee": can_employee,
            "site_ids": sorted(allowed_site_ids),
            "department_ids": sorted(allowed_department_ids),
            "supervisor_employees": supervisor_employees,
        }

    # ---------- ثبت مشاهده ----------

    async def mark_as_read(self, notice_id: int, user_id: int) -> None:
        """اولین بار که کاربر یک اطلاعیه را باز می‌کند، ثبت می‌شود (اجرای دوباره بی‌اثر است)."""
        result = await self.db.execute(
            select(NoticeRead).where(NoticeRead.notice_id == notice_id, NoticeRead.user_id == user_id)
        )
        if result.scalar_one_or_none() is not None:
            return  # قبلاً ثبت شده — زمان اولین مشاهده حفظ می‌شود
        self.db.add(NoticeRead(notice_id=notice_id, user_id=user_id))
        await self.db.commit()

    # ---------- گزارش‌ها ----------

    async def _resolve_sender_names(self, sender_ids: set[int]) -> dict[int, str]:
        if not sender_ids:
            return {}
        result = await self.db.execute(
            select(User.id, User.username, Employee.first_name, Employee.last_name)
            .outerjoin(Employee, Employee.id == User.employee_id)
            .where(User.id.in_(sender_ids))
        )
        names: dict[int, str] = {}
        for user_id, username, first_name, last_name in result.all():
            names[user_id] = f"{first_name} {last_name}" if first_name else username
        return names

    async def _describe_target(self, target: NoticeTarget) -> NoticeTargetDescription:
        from app.models.site import Site  # پرهیز از Circular Import

        if target.target_type == NoticeTargetType.all:
            label = "کل سازمان"
        elif target.target_type == NoticeTargetType.site:
            site = await self.db.get(Site, target.target_id)
            label = site.name if site else f"سایت #{target.target_id}"
        elif target.target_type == NoticeTargetType.department:
            dept = await self.db.get(Department, target.target_id)
            label = dept.name if dept else f"واحد #{target.target_id}"
        elif target.target_type == NoticeTargetType.employee:
            emp = await self.db.get(Employee, target.target_id)
            label = f"{emp.first_name} {emp.last_name} ({emp.personnel_code})" if emp else f"پرسنل #{target.target_id}"
        elif target.target_type == NoticeTargetType.role:
            role = await self.db.get(Role, target.target_id)
            label = role.name if role else f"نقش #{target.target_id}"
        else:
            label = "نامشخص"

        return NoticeTargetDescription(target_type=target.target_type, target_id=target.target_id, label=label)

    async def get_detailed_notices(self, sender_id: int | None = None) -> list[NoticeDetailOut]:
        """
        گزارش کامل اطلاعیه‌ها با نام فرستنده، توصیف مقصدها و آمار بازدید.
        اگر sender_id داده شود فقط اطلاعیه‌های همان فرستنده («ارسالی من»)،
        وگرنه همه اطلاعیه‌های سیستم (گزارش کامل Admin).
        """
        stmt = select(Notice).options(selectinload(Notice.targets)).order_by(Notice.created_at.desc())
        if sender_id is not None:
            stmt = stmt.where(Notice.sender_id == sender_id)
        result = await self.db.execute(stmt)
        notices = list(result.scalars().unique().all())
        if not notices:
            return []

        sender_names = await self._resolve_sender_names({n.sender_id for n in notices})

        # شمارش بازدیدها برای همه این اطلاعیه‌ها در یک Query
        notice_ids = [n.id for n in notices]
        read_result = await self.db.execute(
            select(NoticeRead.notice_id, func.count(NoticeRead.id))
            .where(NoticeRead.notice_id.in_(notice_ids))
            .group_by(NoticeRead.notice_id)
        )
        read_counts = dict(read_result.all())

        detailed: list[NoticeDetailOut] = []
        for notice in notices:
            target_descriptions = [await self._describe_target(t) for t in notice.targets]
            audience_count = len(await self._resolve_audience_user_ids(notice))
            detailed.append(
                NoticeDetailOut(
                    id=notice.id,
                    title=notice.title,
                    body=notice.body,
                    priority=notice.priority,
                    status=notice.status,
                    sender_id=notice.sender_id,
                    sender_name=sender_names.get(notice.sender_id, "—"),
                    created_at=notice.created_at,
                    publish_at=notice.publish_at,
                    targets=target_descriptions,
                    audience_count=audience_count,
                    read_count=read_counts.get(notice.id, 0),
                )
            )
        return detailed

    async def get_notice_readers(self, notice_id: int) -> list[NoticeReaderOut]:
        """فهرست کسانی که یک اطلاعیه مشخص را دیده‌اند، با زمان دقیق — برای Drill-down."""
        result = await self.db.execute(
            select(
                NoticeRead.user_id,
                Employee.id,
                Employee.first_name,
                Employee.last_name,
                Employee.personnel_code,
                NoticeRead.read_at,
            )
            .join(User, User.id == NoticeRead.user_id)
            .outerjoin(Employee, Employee.id == User.employee_id)
            .where(NoticeRead.notice_id == notice_id)
            .order_by(NoticeRead.read_at.asc())
        )
        return [
            NoticeReaderOut(
                user_id=row[0],
                employee_id=row[1],
                first_name=row[2],
                last_name=row[3],
                personnel_code=row[4],
                read_at=row[5],
            )
            for row in result.all()
        ]
