"""
منطق تجاری سیستم اطلاعیه‌ها.

نکته مهم درباره «قابل‌مشاهده بودن»:
یک اطلاعیه برای کاربر X قابل‌مشاهده است اگر حداقل یکی از Target هایش یکی از این‌ها باشد:
  - all
  - site == سایت پرسنل متصل به حساب کاربر
  - department == واحد سازمانی پرسنل متصل به حساب کاربر
  - role == یکی از نقش‌های کاربر
  - employee == خود پرسنل متصل به حساب کاربر
و علاوه بر آن، وضعیت اطلاعیه باید published باشد و در بازه publish_at/expire_at قرار داشته باشد.
"""
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.models.notice import Notice, NoticeStatus, NoticeTarget, NoticeTargetType
from app.models.user import User, UserRole
from app.schemas.notice import NoticeCreate


class NoticeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_notice(self, sender_id: int, payload: NoticeCreate) -> Notice:
        notice = Notice(
            sender_id=sender_id,
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
        await self.db.refresh(notice, attribute_names=["targets"])
        return notice

    async def publish_notice(self, notice_id: int) -> Notice | None:
        notice = await self.db.get(Notice, notice_id)
        if notice is None:
            return None
        notice.status = NoticeStatus.published
        if notice.publish_at is None:
            notice.publish_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(notice, attribute_names=["targets"])
        return notice

    async def list_all(self) -> list[Notice]:
        result = await self.db.execute(select(Notice).order_by(Notice.created_at.desc()))
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
