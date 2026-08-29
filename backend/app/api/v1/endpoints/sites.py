"""Endpoint های مدیریت Site ها، اتصال دیتابیس هر Site و Mapping ستون‌های پرسنلی."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.site import (
    EmployeeMappingIn,
    EmployeeMappingOut,
    SiteActiveUpdate,
    SiteConnectionActiveUpdate,
    SiteConnectionIn,
    SiteConnectionOut,
    SiteCreate,
    SiteGpsLocationIn,
    SiteKaraWorkflowUpdate,
    SiteOut,
)
from app.services.site_service import SiteService

router = APIRouter()


@router.get("", response_model=list[SiteOut])
async def list_sites(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    # فهرست ساده سایت‌ها (نام/کد) اطلاعات حساسی نیست؛ هر کاربر لاگین‌شده برای
    # فرم ارسال اطلاعیه (نمایش نام سایت خودش) به آن نیاز دارد. اطلاعات حساس
    # (اتصال دیتابیس، پسورد) در Endpoint های جداگانه و همچنان محافظت‌شده هستند.
    return await SiteService(db).list_sites()


@router.get("/my-accessible")
async def my_accessible_sites(
    permission: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    برای فیلترهای «سایت» در صفحات گزارش‌گیری (ورود/خروج، پرسنل آنلاین،
    گزارش اطلاعیه‌ها، مدیریت دسترسی، ...) — نه فهرست همه سایت‌های سیستم
    (که GET /sites بدون فیلتر برمی‌گرداند)، بلکه دقیقاً همان سایت‌هایی
    که کاربر جاری برای این Permission Code مشخص واقعاً دسترسی دارد.

    ⚠️ رفع یک نقص واقعی UX (نه خطای امنیتی — خودِ Endpoint های داده،
    مثل GET /attendance/clock-logs، از قبل درست فیلتر می‌کردند): چند
    صفحه فیلتر «سایت» را از GET /sites (همه سایت‌های سیستم) پر می‌کردند
    — یعنی کاربری با دسترسی فقط به یک سایت، در دراپ‌داون همه سایت‌های
    دیگر را هم می‌دید (که انتخابشان فقط یک نتیجه خالی می‌داد، نه خطای
    روشن) — به‌اشتباه به‌نظر می‌رسید «فیلتر سایتی اصلاً کار نمی‌کند».

    unrestricted=True یعنی Admin واقعی یا انتصاب سراسری این مجوز — همه
    سایت‌ها را ببیند (site_ids در این حالت خالی است؛ Frontend باید در
    این حالت خودش GET /sites معمولی را برای «همه سایت‌ها» صدا بزند).
    """
    accessible = await get_sites_with_permission(db, current_user, permission)
    if accessible is None:
        return {"unrestricted": True, "sites": []}
    sites = await SiteService(db).list_sites()
    return {"unrestricted": False, "sites": [SiteOut.model_validate(s) for s in sites if s.id in accessible]}


@router.post("", response_model=SiteOut)
async def create_site(
    payload: SiteCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage")),
):
    return await SiteService(db).create_site(payload)


@router.patch("/{site_id}", response_model=SiteOut)
async def update_site_active(
    site_id: int,
    payload: SiteActiveUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    """فعال/غیرفعال‌کردن یک Site (بدون حذف داده‌ها)."""
    site = await SiteService(db).set_active(site_id, payload.is_active)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="سایت یافت نشد")
    return site


@router.put("/{site_id}/gps", response_model=SiteOut)
async def update_site_gps_location(
    site_id: int,
    payload: SiteGpsLocationIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    """
    موقعیت GPS + شعاع مجاز این سایت را تنظیم می‌کند — برای «حضور دوره‌ای» و
    «ثبت ورود/خروج آزمایشی». برای پاک‌کردن (غیرفعال‌کردن محدودیت مکانی این
    سایت)، هر سه فیلد را null بفرستید.
    """
    site = await SiteService(db).set_gps_location(
        site_id, payload.gps_latitude, payload.gps_longitude, payload.gps_radius_meters
    )
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="سایت یافت نشد")
    return site


@router.put("/{site_id}/kara-workflow", response_model=SiteOut)
async def update_site_kara_workflow(
    site_id: int,
    payload: SiteKaraWorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    """روشن/خاموش‌کردن «گزارش تردد ماهانه» (کاراوب) برای این Site."""
    try:
        site = await SiteService(db).set_kara_workflow_enabled(site_id, payload.kara_workflow_enabled)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="سایت یافت نشد")
    return site


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    """
    حذف کامل و برگشت‌ناپذیر یک Site — همراه با تمام واحدهای سازمانی، پرسنل،
    اتصال دیتابیس و Mapping آن (به‌خاطر CASCADE در سطح دیتابیس). فرانت‌اند باید
    پیش از فراخوانی این Endpoint، تأییدیه صریح (مثل تایپ‌کردن «DELETE») از Admin بگیرد.
    """
    deleted = await SiteService(db).delete_site(site_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="سایت یافت نشد")


# ---------- Site Connection ----------

@router.get("/{site_id}/connection", response_model=SiteConnectionOut | None)
async def get_connection(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    return await SiteService(db).get_connection(site_id)


@router.put("/{site_id}/connection", response_model=SiteConnectionOut)
async def upsert_connection(
    site_id: int,
    payload: SiteConnectionIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    try:
        return await SiteService(db).upsert_connection(site_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{site_id}/connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    await SiteService(db).delete_connection(site_id)


@router.patch("/{site_id}/connection/status", response_model=SiteConnectionOut)
async def update_connection_active(
    site_id: int,
    payload: SiteConnectionActiveUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sync.manage", site_scoped=True)),
):
    """روشن/خاموش‌کردن همگام‌سازی خودکار این Site (بدون تغییر اطلاعات اتصال)."""
    conn = await SiteService(db).set_connection_active(site_id, payload.is_active)
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="اتصال دیتابیس این سایت تعریف نشده است")
    return conn


# ---------- Employee Mapping ----------

@router.get("/{site_id}/mapping", response_model=EmployeeMappingOut | None)
async def get_mapping(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    return await SiteService(db).get_mapping(site_id)


@router.put("/{site_id}/mapping", response_model=EmployeeMappingOut)
async def upsert_mapping(
    site_id: int,
    payload: EmployeeMappingIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    return await SiteService(db).upsert_mapping(site_id, payload)


@router.delete("/{site_id}/mapping", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mapping(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("sites.manage", site_scoped=True)),
):
    await SiteService(db).delete_mapping(site_id)
