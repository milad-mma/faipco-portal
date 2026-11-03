"""
دبیرخانه و شماره‌گذاری (فاز ۳ب، سند مرجع بخش ۷):
- هر سایت یک دبیرخانه؛ پیشوند فقط از پرتال (automation.settings همان سایت)، بدون مقدار پیش‌فرض، یکتا، پس از اولین
  شماره‌ی صادرشده قفل. هر تغییر با مقدار قبلی/جدید در audit.
- صدور شماره فقط در ثبت نهایی (برای نامه‌ی داخلی همان «ارسال»)، داخل همان تراکنش با قفل ردیف شمارنده؛
  سال شمسی به وقت تهران؛ شماره‌ی void هرگز دوباره صادر نمی‌شود (شمارنده فقط جلو می‌رود).
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import jdatetime
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import oa_numbering_rules as nrules
from app.models.office_automation import OaIssuedNumber, OaNumberCounter, OaSecretariat
from app.models.site import Site
from app.models.user import User
from app.services.oa_file_service import OaFileService

_TEHRAN = ZoneInfo("Asia/Tehran")


class OaSecretariatError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def jalali_year_of(dt: datetime) -> int:
    return jdatetime.date.fromgregorian(date=dt.astimezone(_TEHRAN).date()).year


def jalali_date_str(dt: datetime | None) -> str | None:
    """تاریخ رسمی نامه به شمسی «۱۴۰۵/۰۸/۱۲» (ارقام لاتین؛ رابط فارسی‌سازی می‌کند)."""
    if dt is None:
        return None
    d = jdatetime.date.fromgregorian(date=dt.astimezone(_TEHRAN).date())
    return f"{d.year:04d}/{d.month:02d}/{d.day:02d}"


class OaSecretariatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.files = OaFileService(db)

    async def _for_site(self, site_id: int) -> OaSecretariat | None:
        return (await self.db.execute(select(OaSecretariat).where(OaSecretariat.site_id == site_id))).scalar_one_or_none()

    async def _issued_count(self, secretariat_id: int) -> int:
        return int((await self.db.execute(
            select(func.count(OaIssuedNumber.id)).where(OaIssuedNumber.secretariat_id == secretariat_id)
        )).scalar() or 0)

    # ---------- تنظیمات (automation.settings) ----------

    async def list_for_admin(self, sites: set[int] | None) -> list[dict]:
        stmt = select(Site).where(Site.is_active.is_(True)).order_by(Site.name)
        if sites is not None:
            stmt = stmt.where(Site.id.in_(sites or {-1}))
        out = []
        year = jalali_year_of(datetime.now(timezone.utc))
        for site in (await self.db.execute(stmt)).scalars():
            sec = await self._for_site(site.id)
            issued = await self._issued_count(sec.id) if sec else 0
            last = None
            if sec:
                last = (await self.db.execute(
                    select(OaNumberCounter.last_value).where(OaNumberCounter.secretariat_id == sec.id,
                                                             OaNumberCounter.jalali_year == year)
                )).scalar_one_or_none()
            out.append({
                "site_id": site.id, "site_name": site.name,
                "secretariat_id": sec.id if sec else None,
                "name": sec.name if sec else "دبیرخانه",
                "number_prefix": sec.number_prefix if sec else None,
                "locked": issued > 0,
                "issued_count": issued,
                "current_year": year,
                "last_number_this_year": last or 0,
                "sample": nrules.format_number(sec.number_prefix, year, (last or 0) + 1)
                if sec and sec.number_prefix else None,
            })
        return out

    async def save(self, user: User, sites: set[int] | None, site_id: int, *, number_prefix: str | None,
                   name: str | None) -> list[dict]:
        if sites is not None and site_id not in sites:
            raise OaSecretariatError("تنظیمات اتوماسیون این سایت با شما نیست", 403)
        if await self.db.get(Site, site_id) is None:
            raise OaSecretariatError("سایت یافت نشد", 404)
        try:
            prefix = nrules.clean_prefix(number_prefix)
        except nrules.NumberingError as e:
            raise OaSecretariatError(str(e)) from None
        name = (name or "").strip()[:200] or "دبیرخانه"
        sec = await self._for_site(site_id)
        old_prefix = sec.number_prefix if sec else None
        if sec is None:
            sec = OaSecretariat(site_id=site_id, name=name)
            self.db.add(sec)
            await self.db.flush()
        if prefix != old_prefix:
            if old_prefix and await self._issued_count(sec.id) > 0:
                raise OaSecretariatError("بعد از صدور اولین شماره، پیشوند قابل تغییر نیست", 409)
            clash = (await self.db.execute(
                select(OaSecretariat.id).where(func.lower(OaSecretariat.number_prefix) == prefix.lower(),
                                               OaSecretariat.id != sec.id)
            )).scalar_one_or_none()
            if clash:
                raise OaSecretariatError("این پیشوند برای دبیرخانه‌ی سایت دیگری استفاده شده است", 409)
            sec.number_prefix = prefix
        sec.name = name
        sec.updated_by = user.id
        self.files.audit("secretariat.prefix", user, entity="secretariat", entity_id=sec.id, site_id=site_id,
                         details={"old": old_prefix, "new": prefix, "name": name})
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise OaSecretariatError("این پیشوند برای دبیرخانه‌ی سایت دیگری استفاده شده است", 409) from None
        return await self.list_for_admin(sites)

    # ---------- صدور شماره (داخل تراکنش ارسال؛ commit با فراخواننده) ----------

    async def ensure_ready(self, site_id: int) -> OaSecretariat:
        sec = await self._for_site(site_id)
        if sec is None or not sec.number_prefix or not sec.is_active:
            raise OaSecretariatError(nrules.MISSING_PREFIX_MESSAGE, 409)
        return sec

    async def issue(self, site_id: int, letter_id: int, now: datetime) -> tuple[OaSecretariat, str]:
        sec = await self.ensure_ready(site_id)
        year = jalali_year_of(now)
        await self.db.execute(
            pg_insert(OaNumberCounter).values(secretariat_id=sec.id, jalali_year=year, last_value=0)
            .on_conflict_do_nothing(constraint="uq_oa_counter_year")
        )
        counter = (await self.db.execute(
            select(OaNumberCounter).where(OaNumberCounter.secretariat_id == sec.id, OaNumberCounter.jalali_year == year)
            .with_for_update()
        )).scalar_one()
        counter.last_value += 1
        number = nrules.format_number(sec.number_prefix, year, counter.last_value)
        self.db.add(OaIssuedNumber(secretariat_id=sec.id, number=number, letter_id=letter_id, status="used", issued_at=now))
        await self.db.flush()
        return sec, number
