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
from app.models.notice import Notice, NoticeStatus, NoticeTarget, NoticeTargetType, NoticeType
from app.models.notice_read import NoticeRead
from app.models.payroll_receipt import PayrollReceipt
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
    """کاربر اجازه هدف قرار دادن یکی از Target های درخواستی را ندارد (یا اجازه حذف این اطلاعیه را ندارد)."""


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
                    .where(
                        Employee.site_id == target.target_id,
                        Employee.is_active.is_(True),
                        Employee.is_enabled.is_(True),
                    )
                )
                user_ids.update(row[0] for row in result.all())

            elif target.target_type == NoticeTargetType.department:
                result = await self.db.execute(
                    select(User.id)
                    .join(Employee, Employee.id == User.employee_id)
                    .where(
                        Employee.department_id == target.target_id,
                        Employee.is_active.is_(True),
                        Employee.is_enabled.is_(True),
                    )
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
                Notice.is_deleted.is_(False),
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

        # برای اطلاعیه‌های نوع payroll، آیا فیش خودِ همین کاربر واقعاً موجود
        # است؟ (ممکن است این کاربر Target شده باشد ولی به هر دلیلی رکورد
        # PayrollReceipt نداشته باشد — نباید فرض کنیم هر Target از نوع
        # payroll لزوماً فیش هم دارد)
        payroll_receipt_notice_ids: set[int] = set()
        if user.employee_id is not None:
            payroll_notice_ids = [n.id for n in notices if n.notice_type == NoticeType.payroll]
            if payroll_notice_ids:
                receipt_result = await self.db.execute(
                    select(PayrollReceipt.notice_id).where(
                        PayrollReceipt.notice_id.in_(payroll_notice_ids),
                        PayrollReceipt.employee_id == user.employee_id,
                    )
                )
                payroll_receipt_notice_ids = {row[0] for row in receipt_result.all()}

        return [
            NoticeOut(
                id=n.id,
                sender_id=n.sender_id,
                title=n.title,
                body=n.body,
                priority=n.priority,
                status=n.status,
                notice_type=n.notice_type,
                publish_at=n.publish_at,
                expire_at=n.expire_at,
                created_at=n.created_at,
                targets=[
                    NoticeTargetOut(target_type=t.target_type, target_id=t.target_id) for t in n.targets
                ],
                is_read=n.id in read_ids,
                has_my_payroll_receipt=n.id in payroll_receipt_notice_ids,
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
        can_upload_payroll = await self._has_permission(user, "notices.payroll")

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

        # ---------- دامنه هدف‌گیری «پرسنل خاص» ----------
        # اگر کاربر مجوز سراسری/Site-scoped notices.target.employee داشته باشد،
        # می‌تواند در بین همه پرسنل (سایت‌های مجاز) جستجو کند. اگر این مجوز را
        # نداشته باشد ولی سرپرست حداقل یک واحد باشد، هنوز اجازه هدف‌گیری پرسنل
        # را دارد ولی *فقط* محدود به پرسنل همان واحد(های) خودش — نه کل سازمان
        # (طبق سیاست: سرپرست واحد فقط به واحد خودش دسترسی دارد).
        has_broad_employee_permission = user.is_superuser or await self._has_permission(
            user, "notices.target.employee"
        )
        if not has_broad_employee_permission:
            for site in all_sites:
                if await self._has_permission(user, "notices.target.employee", site_id=site.id):
                    has_broad_employee_permission = True
                    break

        supervised_department_ids = sorted(
            {dept.id for dept in all_departments if dept.supervisor_user_id == user.id}
        )

        if has_broad_employee_permission:
            can_employee = True
            employee_target_department_ids: list[int] | None = None  # None یعنی بدون محدودیت
        elif supervised_department_ids:
            can_employee = True
            employee_target_department_ids = supervised_department_ids
        else:
            can_employee = False
            employee_target_department_ids = None

        # میان‌بر «ارسال به سرپرست واحد(ها)» — فقط برای کاربرانی که مجوز
        # گسترده‌تری از «فقط سرپرست بودن واحد خودشان» دارند (مثل HR/مدیر سایت/
        # مدیر میانی) نمایش داده می‌شود. برای سرپرستی که *فقط* سرپرست واحد
        # خودش است، این میان‌بر بی‌فایده و گمراه‌کننده است (چون تنها می‌تواند
        # همان واحد خودش را هدف بگیرد که با فیلدهای عادی هم در دسترس است)، پس
        # برای او خالی برمی‌گردد و در UI اصلاً نمایش داده نمی‌شود.
        supervisor_employees: list[dict] = []
        if has_broad_employee_permission:
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
            "employee_target_department_ids": employee_target_department_ids,
            "can_upload_payroll": can_upload_payroll,
            "site_ids": sorted(allowed_site_ids),
            "department_ids": sorted(allowed_department_ids),
            "supervisor_employees": supervisor_employees,
        }

    # ---------- حذف اطلاعیه ----------

    async def delete_notice(self, notice_id: int, current_user: User) -> Notice:
        """
        حذف Soft-Delete: فقط خودِ فرستنده یا superuser اجازه دارد. رکورد فیزیکی
        پاک نمی‌شود (تا آمار بازدید و گزارش دست‌نخورده بماند) — فقط is_deleted
        ثبت می‌شود که بلافاصله آن را از لیست دریافتی مخاطبان (list_for_user)
        کنار می‌گذارد، ولی در گزارش فرستنده/Admin با برچسب «حذف شده» باقی می‌ماند.
        """
        notice = await self.db.get(Notice, notice_id)
        if notice is None:
            raise ValueError("اطلاعیه یافت نشد")
        if notice.sender_id != current_user.id and not current_user.is_superuser:
            raise NoticePermissionError("شما اجازه حذف این اطلاعیه را ندارید")
        if notice.is_deleted:
            return notice  # قبلاً حذف شده — اجرای دوباره بی‌اثر است
        notice.is_deleted = True
        notice.deleted_at = datetime.now(timezone.utc)
        await self.db.commit()
        return notice

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

    async def _describe_targets_batch(
        self, targets: list[NoticeTarget]
    ) -> dict[tuple[NoticeTargetType, int | None], NoticeTargetDescription]:
        """
        توصیف («کارخانه ۱» به‌جای site_id=۱) همه Target های داده‌شده را در چند
        Query دسته‌ای (نه یک Query جداگانه به‌ازای هر Target) برمی‌گرداند —
        جایگزین حلقه‌ی قبلی که به‌ازای هر Target یک رفت‌وبرگشت جدا به دیتابیس
        می‌زد و روی گزارش‌های پرتعداد به‌شدت کند بود.
        """
        from app.models.site import Site  # پرهیز از Circular Import

        site_ids = {t.target_id for t in targets if t.target_type == NoticeTargetType.site}
        dept_ids = {t.target_id for t in targets if t.target_type == NoticeTargetType.department}
        emp_ids = {t.target_id for t in targets if t.target_type == NoticeTargetType.employee}
        role_ids = {t.target_id for t in targets if t.target_type == NoticeTargetType.role}

        site_names: dict[int, str] = {}
        if site_ids:
            result = await self.db.execute(select(Site.id, Site.name).where(Site.id.in_(site_ids)))
            site_names = dict(result.all())

        dept_names: dict[int, str] = {}
        if dept_ids:
            result = await self.db.execute(select(Department.id, Department.name).where(Department.id.in_(dept_ids)))
            dept_names = dict(result.all())

        emp_labels: dict[int, str] = {}
        if emp_ids:
            result = await self.db.execute(
                select(Employee.id, Employee.first_name, Employee.last_name, Employee.personnel_code).where(
                    Employee.id.in_(emp_ids)
                )
            )
            emp_labels = {r[0]: f"{r[1]} {r[2]} ({r[3]})" for r in result.all()}

        role_names: dict[int, str] = {}
        if role_ids:
            result = await self.db.execute(select(Role.id, Role.name).where(Role.id.in_(role_ids)))
            role_names = dict(result.all())

        descriptions: dict[tuple[NoticeTargetType, int | None], NoticeTargetDescription] = {}
        for t in targets:
            key = (t.target_type, t.target_id)
            if key in descriptions:
                continue
            if t.target_type == NoticeTargetType.all:
                label = "کل سازمان"
            elif t.target_type == NoticeTargetType.site:
                label = site_names.get(t.target_id, f"سایت #{t.target_id}")
            elif t.target_type == NoticeTargetType.department:
                label = dept_names.get(t.target_id, f"واحد #{t.target_id}")
            elif t.target_type == NoticeTargetType.employee:
                label = emp_labels.get(t.target_id, f"پرسنل #{t.target_id}")
            elif t.target_type == NoticeTargetType.role:
                label = role_names.get(t.target_id, f"نقش #{t.target_id}")
            else:
                label = "نامشخص"
            descriptions[key] = NoticeTargetDescription(target_type=t.target_type, target_id=t.target_id, label=label)
        return descriptions

    async def _resolve_audience_counts_batch(self, notices: list[Notice]) -> dict[int, int]:
        """
        تعداد مخاطبان هر اطلاعیه را برمی‌گرداند — با یک Query دسته‌ای به‌ازای هر
        نوع Target (نه به‌ازای هر Target/هر اطلاعیه جداگانه). مجموعه کاربران هر
        Target یکتا (مثلاً همان site_id) فقط یک‌بار محاسبه و در بین اطلاعیه‌هایی
        که آن Target را مشترک دارند بازاستفاده می‌شود.
        """
        unique_keys = {(t.target_type, t.target_id) for n in notices for t in n.targets}
        user_ids_by_key: dict[tuple[NoticeTargetType, int | None], set[int]] = {}

        if (NoticeTargetType.all, None) in unique_keys:
            result = await self.db.execute(select(User.id).where(User.is_active.is_(True)))
            user_ids_by_key[(NoticeTargetType.all, None)] = {row[0] for row in result.all()}

        site_ids = {tid for (ttype, tid) in unique_keys if ttype == NoticeTargetType.site}
        if site_ids:
            result = await self.db.execute(
                select(Employee.site_id, User.id)
                .join(Employee, Employee.id == User.employee_id)
                .where(
                    Employee.site_id.in_(site_ids),
                    Employee.is_active.is_(True),
                    Employee.is_enabled.is_(True),
                )
            )
            grouped: dict[int, set[int]] = {}
            for site_id, user_id in result.all():
                grouped.setdefault(site_id, set()).add(user_id)
            for site_id in site_ids:
                user_ids_by_key[(NoticeTargetType.site, site_id)] = grouped.get(site_id, set())

        dept_ids = {tid for (ttype, tid) in unique_keys if ttype == NoticeTargetType.department}
        if dept_ids:
            result = await self.db.execute(
                select(Employee.department_id, User.id)
                .join(Employee, Employee.id == User.employee_id)
                .where(
                    Employee.department_id.in_(dept_ids),
                    Employee.is_active.is_(True),
                    Employee.is_enabled.is_(True),
                )
            )
            grouped = {}
            for dept_id, user_id in result.all():
                grouped.setdefault(dept_id, set()).add(user_id)
            for dept_id in dept_ids:
                user_ids_by_key[(NoticeTargetType.department, dept_id)] = grouped.get(dept_id, set())

        emp_ids = {tid for (ttype, tid) in unique_keys if ttype == NoticeTargetType.employee}
        if emp_ids:
            result = await self.db.execute(
                select(Employee.id, User.id).join(User, User.employee_id == Employee.id).where(Employee.id.in_(emp_ids))
            )
            for emp_id, user_id in result.all():
                user_ids_by_key[(NoticeTargetType.employee, emp_id)] = {user_id}
            for emp_id in emp_ids:
                user_ids_by_key.setdefault((NoticeTargetType.employee, emp_id), set())

        role_ids = {tid for (ttype, tid) in unique_keys if ttype == NoticeTargetType.role}
        if role_ids:
            result = await self.db.execute(
                select(UserRole.role_id, UserRole.user_id).where(UserRole.role_id.in_(role_ids))
            )
            grouped = {}
            for role_id, user_id in result.all():
                grouped.setdefault(role_id, set()).add(user_id)
            for role_id in role_ids:
                user_ids_by_key[(NoticeTargetType.role, role_id)] = grouped.get(role_id, set())

        counts: dict[int, int] = {}
        for notice in notices:
            union_ids: set[int] = set()
            for t in notice.targets:
                union_ids |= user_ids_by_key.get((t.target_type, t.target_id), set())
            counts[notice.id] = len(union_ids)
        return counts

    async def count_published_this_week(self) -> int:
        """
        تعداد اطلاعیه‌های منتشرشده کل سیستم در ۷ روز اخیر (نه فقط اطلاعیه‌های
        کاربر جاری) — برای کارت آمار داشبورد Admin.
        """
        from datetime import timedelta

        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        stmt = select(func.count()).select_from(Notice).where(
            Notice.status == NoticeStatus.published,
            Notice.is_deleted.is_(False),
            Notice.publish_at >= week_ago,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_detailed_notices(
        self, sender_id: int | None = None, limit: int = 10, offset: int = 0
    ) -> tuple[list[NoticeDetailOut], int]:
        """
        یک صفحه از گزارش اطلاعیه‌ها (نام فرستنده، توصیف مقصدها، آمار بازدید).
        اگر sender_id داده شود فقط اطلاعیه‌های همان فرستنده («ارسالی من»)،
        وگرنه همه اطلاعیه‌های سیستم (گزارش کامل Admin). به‌جای واکشی و پردازش
        همه اطلاعیه‌های سیستم در یک درخواست (که با رشد تعداد اطلاعیه‌ها به‌شدت
        کند می‌شد)، Pagination در سطح SQL انجام می‌شود — فقط همین صفحه پردازش
        می‌شود، و آن پردازش هم با Query های دسته‌ای انجام می‌شود، نه N+1.
        خروجی: (لیست اطلاعیه‌های همین صفحه, تعداد کل اطلاعیه‌ها).
        """
        base_stmt = select(Notice)
        if sender_id is not None:
            base_stmt = base_stmt.where(Notice.sender_id == sender_id)

        total = (
            await self.db.execute(select(func.count()).select_from(base_stmt.subquery()))
        ).scalar_one()

        stmt = (
            base_stmt.options(selectinload(Notice.targets))
            .order_by(Notice.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        notices = list(result.scalars().unique().all())
        if not notices:
            return [], total

        sender_names = await self._resolve_sender_names({n.sender_id for n in notices})

        # شمارش بازدیدها برای همین صفحه در یک Query
        notice_ids = [n.id for n in notices]
        read_result = await self.db.execute(
            select(NoticeRead.notice_id, func.count(NoticeRead.id))
            .where(NoticeRead.notice_id.in_(notice_ids))
            .group_by(NoticeRead.notice_id)
        )
        read_counts = dict(read_result.all())

        all_targets = [t for n in notices for t in n.targets]
        target_descriptions_by_key = await self._describe_targets_batch(all_targets)
        audience_counts = await self._resolve_audience_counts_batch(notices)

        detailed: list[NoticeDetailOut] = []
        for notice in notices:
            target_descriptions = [
                target_descriptions_by_key[(t.target_type, t.target_id)] for t in notice.targets
            ]
            detailed.append(
                NoticeDetailOut(
                    id=notice.id,
                    title=notice.title,
                    body=notice.body,
                    priority=notice.priority,
                    status=notice.status,
                    notice_type=notice.notice_type,
                    sender_id=notice.sender_id,
                    sender_name=sender_names.get(notice.sender_id, "—"),
                    created_at=notice.created_at,
                    publish_at=notice.publish_at,
                    targets=target_descriptions,
                    audience_count=audience_counts.get(notice.id, 0),
                    read_count=read_counts.get(notice.id, 0),
                    is_deleted=notice.is_deleted,
                    deleted_at=notice.deleted_at,
                )
            )
        return detailed, total

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
