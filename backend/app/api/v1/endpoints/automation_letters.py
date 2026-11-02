"""
اتوماسیون اداری — قالب نامه (سربرگ/پابرگ/حاشیه، نسخه‌دار) و پیش‌نویس شخصی (docs/office-automation.md).

- قالب‌ها برای همه‌ی سایت‌ها یکسان‌اند؛ مدیریت با مجوز automation.templates (هر سایت).
- پیش‌نویس: مجوز automation.access (ادغام compose در access، Migration 138)؛ نامه متعلق به سایت خود پرسنل است و هر پیش‌نویس
  فقط برای سازنده‌اش دیده و ویرایش می‌شود.
- لوگوی قالب: فقط PNG/JPG/WEBP؛ نمایش برای دارندگان templates یا access.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.ip_allowlist import get_client_ip
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.employee import Employee
from app.models.site import Site
from app.models.user import User
from app.services.oa_file_service import OaFileError, file_out
from app.services.oa_letter_service import (
    LOGO_EXTENSIONS,
    OaLetterError,
    OaLetterService,
)

router = APIRouter()

UPLOAD_CHUNK = 1 << 20
LOGO_FORMATS = ["png", "jpg", "webp"]


def _raise(e: Exception):
    raise HTTPException(status_code=getattr(e, "status_code", 400), detail=str(e))


async def _require(db: AsyncSession, user: User, code: str, label: str) -> set[int] | None:
    sites = await get_sites_with_permission(db, user, code)
    if sites is not None and not sites:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"اجازه‌ی {label} را ندارید")
    return sites


async def _templates_perm(db: AsyncSession, user: User) -> None:
    await _require(db, user, "automation.templates", "مدیریت قالب نامه")


async def _access_perm(db: AsyncSession, user: User) -> None:
    await _require(db, user, "automation.access", "استفاده از اتوماسیون اداری")


# ================= قالب‌ها =================


class TemplateIn(BaseModel):
    name: str = Field(max_length=120)
    default_paper_size: str = "A4"
    is_active: bool = True
    layouts: dict


@router.get("/templates")
async def list_templates(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """همه‌ی قالب‌ها (برای همه‌ی سایت‌ها یکسان) + چیدمان پیش‌فرض."""
    from app.core import oa_letter_rules as rules

    await _templates_perm(db, current_user)
    return {
        "templates": await OaLetterService(db).list_templates(),
        "default_layouts": rules.default_layouts(),
        "paper_mm": rules.PAPER_SIZES,
    }


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(payload: TemplateIn, request: Request, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    await _templates_perm(db, current_user)
    try:
        return await OaLetterService(db).save_template(template_id=None, user=current_user, ip=get_client_ip(request),
                                                       **payload.model_dump())
    except OaLetterError as e:
        _raise(e)


@router.put("/templates/{template_id}")
async def update_template(template_id: int, payload: TemplateIn, request: Request, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    await _templates_perm(db, current_user)
    try:
        return await OaLetterService(db).save_template(template_id=template_id, user=current_user,
                                                       ip=get_client_ip(request), **payload.model_dump())
    except OaLetterError as e:
        _raise(e)


@router.get("/templates/{template_id}/versions")
async def template_versions(template_id: int, db: AsyncSession = Depends(get_db),
                            current_user: User = Depends(get_current_user)):
    await _templates_perm(db, current_user)
    service = OaLetterService(db)
    try:
        await service.get_template(template_id)
    except OaLetterError as e:
        _raise(e)
    return await service.template_versions(template_id)


async def _upload_site(db: AsyncSession, user: User) -> int:
    """فایل اتوماسیون به یک سایت نیاز دارد (تنظیمات حجم): سایت خود پرسنل، وگرنه اولین سایت."""
    if user.employee_id:
        site_id = await db.scalar(select(Employee.site_id).where(Employee.id == user.employee_id))
        if site_id:
            return site_id
    site_id = await db.scalar(select(Site.id).order_by(Site.id).limit(1))
    if site_id is None:
        raise HTTPException(status_code=400, detail="هیچ سایتی تعریف نشده است")
    return site_id


@router.post("/templates/logo", status_code=status.HTTP_201_CREATED)
async def upload_logo(request: Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    """بارگذاری لوگوی سربرگ (PNG/JPG/WEBP). تا وقتی در یک نسخه‌ی قالب ذخیره نشود موقت است."""
    await _templates_perm(db, current_user)
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in LOGO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="لوگو باید PNG، JPG یا WEBP باشد")

    async def chunks():
        while True:
            block = await file.read(UPLOAD_CHUNK)
            if not block:
                return
            yield block

    service = OaLetterService(db)
    try:
        row = await service.files.upload(site_id=await _upload_site(db, current_user), filename=file.filename or "",
                                         chunks=chunks(), user=current_user, purpose="template",
                                         ip=get_client_ip(request), formats=LOGO_FORMATS)
    except OaFileError as e:
        _raise(e)
    if row.status != "clean":
        raise HTTPException(status_code=409, detail="لوگو هنوز بررسی نشده (اسکن ویروس)؛ چند دقیقه بعد دوباره بارگذاری کنید")
    return file_out(row)


@router.get("/templates/logo/{file_id}")
async def show_logo(file_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """تصویر لوگو برای پیش‌نمایش؛ دارندگان automation.templates یا automation.access."""
    allowed = False
    for code in ("automation.templates", "automation.access"):
        sites = await get_sites_with_permission(db, current_user, code)
        if sites is None or sites:
            allowed = True
            break
    if not allowed:
        raise HTTPException(status_code=403, detail="به این فایل دسترسی ندارید")
    service = OaLetterService(db)
    try:
        f = await service.logo_file(file_id)
    except OaLetterError as e:
        _raise(e)
    return StreamingResponse(
        service.files.storage.iter_file(f.storage_key),
        media_type=f.content_type or "application/octet-stream",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=86400",
                 "Content-Disposition": "inline", "Content-Length": str(f.size)},
    )


# ================= پیش‌نویس =================


class DraftCreateIn(BaseModel):
    paper_size: str | None = None
    template_id: int | None = None


class DraftSaveIn(BaseModel):
    subject: str = Field(default="", max_length=2000)
    body_html: str = ""
    paper_size: str = "A4"
    template_id: int | None = None
    urgency: str = "normal"
    confidentiality: str = "normal"
    requires_action: bool = False
    action_due_at: datetime | None = None
    row_version: int


@router.get("/compose/options")
async def compose_options(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """قالب‌های فعال (برای همه یکسان) + برچسب فوریت/محرمانگی."""
    from app.core import oa_letter_rules as rules

    await _access_perm(db, current_user)
    templates = await OaLetterService(db).list_templates(include_inactive=False)
    return {
        "templates": [
            {"id": t["id"], "name": t["name"], "default_paper_size": t["default_paper_size"]}
            for t in templates if t["version_id"]
        ],
        "urgencies": rules.URGENCIES,
        "confidentiality": rules.CONFIDENTIALITY,
    }


@router.get("/drafts")
async def my_drafts(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _access_perm(db, current_user)
    return await OaLetterService(db).my_drafts(current_user)


@router.post("/drafts", status_code=status.HTTP_201_CREATED)
async def create_draft(payload: DraftCreateIn, db: AsyncSession = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    await _access_perm(db, current_user)
    try:
        return await OaLetterService(db).create_draft(user=current_user, **payload.model_dump())
    except OaLetterError as e:
        _raise(e)


@router.get("/drafts/{letter_id}")
async def get_draft(letter_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _access_perm(db, current_user)
    service = OaLetterService(db)
    try:
        out = await service.draft_out(letter_id, current_user)
        if out["status"] == "draft":
            from app.services.oa_cartable_service import OaCartableService

            letter = await service._own_letter(letter_id, current_user)
            out.update(await OaCartableService(db).draft_extras(letter))
    except OaLetterError as e:
        _raise(e)
    return out


@router.put("/drafts/{letter_id}")
async def save_draft(letter_id: int, payload: DraftSaveIn, db: AsyncSession = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    await _access_perm(db, current_user)
    try:
        return await OaLetterService(db).save_draft(letter_id, user=current_user, **payload.model_dump())
    except OaLetterError as e:
        _raise(e)


@router.delete("/drafts/{letter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_draft(letter_id: int, db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    await _access_perm(db, current_user)
    try:
        await OaLetterService(db).discard_draft(letter_id, current_user)
    except OaLetterError as e:
        _raise(e)
