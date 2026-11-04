"""
عکس پرسنلی: درخواست بارگذاری/حذف توسط خود پرسنل و تأیید منابع انسانی (مجوز photo.approve، سایت‌محور).

با تأیید، عکس دقیقاً مثل کاراوب در جدول عکس سایت (نگاشت پرسنل: photo_table / photo_emp_no_column /
photo_thumbnail_column = عکس اصلی / photo_small_column = عکس کوچک) نوشته می‌شود:
- ردیف پرسنل هست (حتی با ستون‌های خالی) → UPDATE همان دو ستون
- ردیف نیست → INSERT فقط با کد پرسنلی و دو عکس
- حذف → دو ستون NULL و ردیف می‌ماند (مثل خود کاراوب)
ستون امضا (WF_SignatureImg) و هر ستون دیگری هرگز دست نمی‌خورد. docs: claude/profile-photo-upload.md
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import psycopg2
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, undefer

from app.core.profile_photo_rules import PhotoRulesError, prepare_upload
from app.models.employee import Employee, EmployeeMapping
from app.models.profile_photo import ProfilePhotoRequest
from app.models.site import DbType, SiteConnection
from app.models.user import User
from app.services import notification_templates
from app.services.leave_request_service import _connect, _quote

logger = logging.getLogger(__name__)

ACTION_LABELS = {"upload": "بارگذاری عکس", "delete": "حذف عکس"}
PHOTO_APPROVE = "photo.approve"


async def send_photo_push(request_id: int) -> None:
    """
    اعلان (Push) عکس پرسنلی، بعد از commit در پس‌زمینه؛ خطا فقط لاگ می‌شود:
    - درخواست در انتظار → همه‌ی کاربران دارای photo.approve برای سایت آن پرسنل (سراسری یا همان سایت)، به‌جز خودش
    - تأیید/رد → خودِ پرسنل
    """
    from app.core.permission_grants import grants_subquery
    from app.db.session import AsyncSessionLocal
    from app.services.push_service import PushService

    try:
        async with AsyncSessionLocal() as db:
            req = await db.get(ProfilePhotoRequest, request_id)
            if req is None:
                return
            emp = await db.get(Employee, req.employee_id)
            name = f"{emp.first_name} {emp.last_name}".strip() if emp else ""
            action = ACTION_LABELS.get(req.action, "")
            if req.status == "pending":
                g = grants_subquery()
                ids = set((await db.execute(
                    select(User.id).join(g, g.c.user_id == User.id).where(
                        g.c.code == PHOTO_APPROVE, (g.c.site_id.is_(None)) | (g.c.site_id == req.site_id),
                        User.is_active.is_(True),
                    )
                )).scalars().all())
                ids -= set((await db.execute(select(User.id).where(User.employee_id == req.employee_id))).scalars().all())
                body = await notification_templates.render(db, None, "photo.hr_new", name=name, action=action)
                url = "/photo-requests/admin"
            elif req.status in ("approved", "rejected"):
                ids = set((await db.execute(select(User.id).where(User.employee_id == req.employee_id))).scalars().all())
                key = "photo.approved" if req.status == "approved" else "photo.rejected"
                body = await notification_templates.render(db, None, key, action=action, reason=req.reject_reason or "")
                url = "/profile"
            else:
                return
            if ids:
                await asyncio.wait_for(PushService(db).notify_users(ids, url=url, priority="normal", body=body), timeout=60)
    except Exception:  # noqa: BLE001 - اعلان نباید خطای کاربر شود
        logger.exception("ارسال اعلان عکس پرسنلی ناموفق بود (درخواست %s)", request_id)


class ProfilePhotoError(Exception):
    """خطای قابل نمایش به کاربر."""


def _write_photo_sync(conn: SiteConnection, mapping: EmployeeMapping, emp_no: int, image: bytes | None, thumb: bytes | None) -> str:
    """
    عکس را در جدول عکس منبع می‌نویسد (یا با None پاک می‌کند). خروجی: updated / inserted / nothing.
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    table, emp_col = q(mapping.photo_table), q(mapping.photo_emp_no_column)
    img_col, thumb_col = q(mapping.photo_thumbnail_column), q(mapping.photo_small_column)

    def b(value: bytes | None):
        if value is None:
            return None
        return psycopg2.Binary(value) if conn.db_type == DbType.postgresql else value

    params = {"emp": emp_no, "img": b(image), "thumb": b(thumb)}
    connection = _connect(conn)
    try:
        with connection.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {emp_col} = %(emp)s", {"emp": emp_no})  # noqa: S608
            exists = (cur.fetchone()[0] or 0) > 0
            if exists:
                cur.execute(
                    f"UPDATE {table} SET {img_col} = %(img)s, {thumb_col} = %(thumb)s WHERE {emp_col} = %(emp)s",  # noqa: S608
                    params,
                )
                outcome = "updated"
            elif image is not None:
                cur.execute(
                    f"INSERT INTO {table} ({emp_col}, {img_col}, {thumb_col}) VALUES (%(emp)s, %(img)s, %(thumb)s)",  # noqa: S608
                    params,
                )
                outcome = "inserted"
            else:
                outcome = "nothing"  # حذف عکسی که در منبع ردیفی ندارد
        connection.commit()
        return outcome
    except Exception:
        try:
            connection.rollback()
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        connection.close()


class ProfilePhotoService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _actor_name(self, user: User) -> str:
        if user.employee_id:
            emp = await self.db.get(Employee, user.employee_id)
            if emp:
                return f"{emp.first_name} {emp.last_name}"
        return user.username or ""

    # ---------- خود پرسنل ----------

    async def _pending(self, employee_id: int) -> ProfilePhotoRequest | None:
        return (
            await self.db.execute(
                select(ProfilePhotoRequest).where(
                    ProfilePhotoRequest.employee_id == employee_id, ProfilePhotoRequest.status == "pending"
                )
            )
        ).scalar_one_or_none()

    async def _has_photo(self, employee_id: int) -> bool:
        value = (
            await self.db.execute(
                select(func.coalesce(func.length(Employee.photo_thumbnail), 0)).where(Employee.id == employee_id)
            )
        ).scalar()
        return bool(value)

    async def _upload_ready(self, site_id: int | None) -> bool:
        if site_id is None:
            return False
        mapping = (
            await self.db.execute(select(EmployeeMapping).where(EmployeeMapping.site_id == site_id))
        ).scalar_one_or_none()
        return bool(
            mapping
            and mapping.photo_table
            and mapping.photo_emp_no_column
            and mapping.photo_thumbnail_column
            and mapping.photo_small_column
            and mapping.photo_small_column.lower() != mapping.photo_thumbnail_column.lower()
        )

    async def my_status(self, employee: Employee) -> dict:
        pending = await self._pending(employee.id)
        last = (
            await self.db.execute(
                select(ProfilePhotoRequest)
                .where(ProfilePhotoRequest.employee_id == employee.id, ProfilePhotoRequest.status.in_(("approved", "rejected")))
                .order_by(ProfilePhotoRequest.decided_at.desc().nullslast(), ProfilePhotoRequest.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return {
            "has_photo": await self._has_photo(employee.id),
            "enabled": await self._upload_ready(employee.site_id),
            "pending": None
            if pending is None
            else {"id": pending.id, "action": pending.action, "created_at": pending.created_at},
            "last_decision": None
            if last is None
            else {
                "action": last.action,
                "status": last.status,
                "reason": last.reject_reason,
                "decided_at": last.decided_at,
            },
        }

    async def _new_request(self, employee: Employee, action: str, image=None, thumb=None) -> ProfilePhotoRequest:
        if not await self._upload_ready(employee.site_id):
            raise ProfilePhotoError("تغییر عکس برای سایت شما هنوز فعال نشده است (نگاشت عکس در تنظیمات سایت کامل نیست)")
        if await self._pending(employee.id) is not None:
            raise ProfilePhotoError("یک درخواست عکس در انتظار تأیید منابع انسانی دارید؛ اول آن را لغو کنید")
        req = ProfilePhotoRequest(
            employee_id=employee.id,
            site_id=employee.site_id,
            action=action,
            status="pending",
            image=image,
            thumbnail=thumb,
            image_size=len(image) if image else None,
        )
        self.db.add(req)
        await self.db.commit()
        return req

    async def request_upload(self, employee: Employee, raw: bytes) -> ProfilePhotoRequest:
        try:
            image, thumb = await asyncio.to_thread(prepare_upload, raw)
        except PhotoRulesError as e:
            raise ProfilePhotoError(str(e)) from e
        return await self._new_request(employee, "upload", image, thumb)

    async def request_delete(self, employee: Employee) -> ProfilePhotoRequest:
        if not await self._has_photo(employee.id):
            raise ProfilePhotoError("عکسی برای حذف ندارید")
        return await self._new_request(employee, "delete")

    async def cancel_pending(self, employee: Employee) -> None:
        pending = await self._pending(employee.id)
        if pending is None:
            raise ProfilePhotoError("درخواستی در انتظار ندارید")
        pending.status = "cancelled"
        pending.decided_at = datetime.now(timezone.utc)
        pending.image = None
        pending.thumbnail = None
        await self.db.commit()

    async def pending_image(self, employee: Employee) -> bytes | None:
        row = (
            await self.db.execute(
                select(ProfilePhotoRequest.image).where(
                    ProfilePhotoRequest.employee_id == employee.id,
                    ProfilePhotoRequest.status == "pending",
                    ProfilePhotoRequest.action == "upload",
                )
            )
        ).scalar_one_or_none()
        return row

    # ---------- منابع انسانی ----------

    @staticmethod
    def _site_filter(stmt, sites: set[int] | None):
        return stmt if sites is None else stmt.where(ProfilePhotoRequest.site_id.in_(sites or {-1}))

    async def pending_count(self, sites: set[int] | None) -> int:
        stmt = select(func.count(ProfilePhotoRequest.id)).where(ProfilePhotoRequest.status == "pending")
        return int((await self.db.execute(self._site_filter(stmt, sites))).scalar() or 0)

    async def list_requests(self, sites: set[int] | None, box: str, page: int = 1, page_size: int = 30) -> dict:
        statuses = ("pending",) if box == "pending" else ("approved", "rejected")
        base = self._site_filter(select(ProfilePhotoRequest).where(ProfilePhotoRequest.status.in_(statuses)), sites)
        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
        order = ProfilePhotoRequest.created_at.asc() if box == "pending" else ProfilePhotoRequest.decided_at.desc()
        rows = (
            await self.db.execute(base.order_by(order, ProfilePhotoRequest.id).offset((page - 1) * page_size).limit(page_size))
        ).scalars().all()
        emp_ids = {r.employee_id for r in rows}
        employees = {}
        if emp_ids:
            result = await self.db.execute(
                select(Employee, func.coalesce(func.length(Employee.photo_thumbnail), 0))
                .options(selectinload(Employee.department), selectinload(Employee.site))
                .where(Employee.id.in_(emp_ids))
            )
            employees = {e.id: (e, bool(n)) for e, n in result.all()}
        items = []
        for r in rows:
            emp, has_photo = employees.get(r.employee_id, (None, False))
            items.append(
                {
                    "id": r.id,
                    "action": r.action,
                    "status": r.status,
                    "created_at": r.created_at,
                    "decided_at": r.decided_at,
                    "decided_by_name": r.decided_by_name,
                    "reject_reason": r.reject_reason,
                    "image_size": r.image_size,
                    "employee_id": r.employee_id,
                    "employee_name": f"{emp.first_name} {emp.last_name}" if emp else "—",
                    "personnel_code": emp.personnel_code if emp else None,
                    "department": emp.department.name if emp and emp.department else None,
                    "site": emp.site.name if emp and emp.site else None,
                    "has_current_photo": has_photo,
                }
            )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def _get_for_hr(self, request_id: int, sites: set[int] | None, *, with_images: bool = False) -> ProfilePhotoRequest:
        stmt = select(ProfilePhotoRequest).where(ProfilePhotoRequest.id == request_id)
        if with_images:
            stmt = stmt.options(undefer(ProfilePhotoRequest.image), undefer(ProfilePhotoRequest.thumbnail))
        req = (await self.db.execute(self._site_filter(stmt, sites))).scalar_one_or_none()
        if req is None:
            raise ProfilePhotoError("درخواست یافت نشد")
        return req

    async def request_image(self, request_id: int, sites: set[int] | None) -> bytes | None:
        req = await self._get_for_hr(request_id, sites)
        return (
            await self.db.execute(select(ProfilePhotoRequest.image).where(ProfilePhotoRequest.id == req.id))
        ).scalar_one_or_none()

    async def current_image(self, request_id: int, sites: set[int] | None) -> bytes | None:
        req = await self._get_for_hr(request_id, sites)
        return (
            await self.db.execute(select(Employee.photo_thumbnail).where(Employee.id == req.employee_id))
        ).scalar_one_or_none()

    async def approve(self, request_id: int, sites: set[int] | None, user: User) -> dict:
        req = await self._get_for_hr(request_id, sites, with_images=True)
        if req.status != "pending":
            raise ProfilePhotoError("این درخواست قبلاً بررسی شده است")
        employee = await self.db.get(Employee, req.employee_id, options=[undefer(Employee.photo_thumbnail)])
        if employee is None:
            raise ProfilePhotoError("پرسنل این درخواست یافت نشد")
        mapping = (
            await self.db.execute(select(EmployeeMapping).where(EmployeeMapping.site_id == employee.site_id))
        ).scalar_one_or_none()
        connection = (
            await self.db.execute(
                select(SiteConnection).where(SiteConnection.site_id == employee.site_id, SiteConnection.is_active.is_(True))
            )
        ).scalar_one_or_none()
        if not await self._upload_ready(employee.site_id) or connection is None:
            raise ProfilePhotoError("نگاشت عکس یا اتصال دیتابیس سایت این پرسنل کامل نیست")
        try:
            emp_no = int(employee.personnel_code)
        except (TypeError, ValueError) as e:
            raise ProfilePhotoError("کد پرسنلی این کارمند عددی نیست") from e

        image = req.image if req.action == "upload" else None
        thumb = req.thumbnail if req.action == "upload" else None
        try:
            outcome = await asyncio.to_thread(_write_photo_sync, connection, mapping, emp_no, image, thumb)
        except Exception as e:  # noqa: BLE001 - خطای واقعی درایور برای منابع انسانی نمایش داده می‌شود
            raise ProfilePhotoError(f"ثبت عکس در دیتابیس منبع ناموفق بود: {e}") from e

        # نمایش فوری در پرتال (بدون انتظار برای همگام‌سازی بعدی)
        employee.photo_thumbnail = image
        req.status = "approved"
        req.decided_at = datetime.now(timezone.utc)
        req.decided_by_id = user.id
        req.decided_by_name = await self._actor_name(user)
        req.image = None  # نسخه‌ی نهایی حالا در منبع و پرتال است
        req.thumbnail = None
        await self.db.commit()
        return {"outcome": outcome}

    async def reject(self, request_id: int, sites: set[int] | None, user: User, reason: str) -> None:
        reason = (reason or "").strip()
        if not reason:
            raise ProfilePhotoError("دلیل رد را بنویسید")
        req = await self._get_for_hr(request_id, sites)
        if req.status != "pending":
            raise ProfilePhotoError("این درخواست قبلاً بررسی شده است")
        await self.db.execute(
            update(ProfilePhotoRequest)
            .where(ProfilePhotoRequest.id == req.id)
            .values(
                status="rejected",
                decided_at=datetime.now(timezone.utc),
                decided_by_id=user.id,
                decided_by_name=await self._actor_name(user),
                reject_reason=reason[:1000],
                image=None,
                thumbnail=None,
            )
        )
        await self.db.commit()
