"""
اتوماسیون اداری — فاز ۲: قالب نامه (سربرگ/پابرگ/حاشیه، نسخه‌دار) و پیش‌نویس شخصی (docs/office-automation.md).

- قالب‌ها: مجوز automation.templates همان سایت (ادمین کل همه‌ی سایت‌ها).
- پیش‌نویس: مجوز automation.compose همان سایت؛ هر پیش‌نویس فقط برای سازنده‌اش دیده و ویرایش می‌شود.
- لوگوی قالب: فقط PNG/JPG/WEBP؛ نمایش برای دارندگان compose یا templates همان سایت.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.ip_allowlist import get_client_ip
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.site import Site
from app.models.user import User
from app.services.oa_file_service import OaFileError, file_out
from app.services.oa_letter_service import LOGO_EXTENSIONS, OaLetterError, OaLetterService

router = APIRouter()

UPLOAD_CHUNK = 1 << 20
LOGO_FORMATS = ["png", "jpg", "webp"]


def _raise(e: Exception):
    raise HTTPException(status_code=getattr(e, "status_code", 400), detail=str(e))


async def _sites(db: AsyncSession, user: User, code: str, label: str) -> set[int] | None:
    sites = await get_sites_with_permission(db, user, code)
    if sites is not None and not sites:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"اجازه‌ی {label} را ندارید")
    return sites


def _check(sites: set[int] | None, site_id: int) -> None:
    if sites is not None and site_id not in sites:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="به این سایت دسترسی ندارید")


async def _site_list(db: AsyncSession, sites: set[int] | None) -> list[dict]:
    from sqlalchemy import select

    rows = (await db.execute(select(Site).order_by(Site.id))).scalars().all()
    return [{"id": s.id, "name": s.name} for s in rows if sites is None or s.id in sites]


# ================= قالب‌ها =================


class TemplateIn(BaseModel):
    site_id: int
    name: str = Field(max_length=120)
    default_paper_size: str = "A4"
    is_active: bool = True
    layouts: dict


@router.get("/templates")
async def list_templates(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """قالب‌های سایت‌هایی که بیننده automation.templates آن‌ها را دارد + فهرست همان سایت‌ها و چیدمان پیش‌فرض."""
    from app.core import oa_letter_rules as rules

    sites = await _sites(db, current_user, "automation.templates", "مدیریت قالب نامه")
    return {
        "sites": await _site_list(db, sites),
        "templates": await OaLetterService(db).list_templates(sites),
        "default_layouts": rules.default_layouts(),
        "paper_mm": rules.PAPER_SIZES,
    }


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(payload: TemplateIn, request: Request, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    _check(await _sites(db, current_user, "automation.templates", "مدیریت قالب نامه"), payload.site_id)
    try:
        return await OaLetterService(db).save_template(template_id=None, user=current_user, ip=get_client_ip(request),
                                                       **payload.model_dump())
    except OaLetterError as e:
        _raise(e)


@router.put("/templates/{template_id}")
async def update_template(template_id: int, payload: TemplateIn, request: Request, db: AsyncSession = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    sites = await _sites(db, current_user, "automation.templates", "مدیریت قالب نامه")
    service = OaLetterService(db)
    try:
        t = await service.get_template(template_id)
        _check(sites, t.site_id)
        return await service.save_template(template_id=template_id, user=current_user, ip=get_client_ip(request),
                                           **payload.model_dump())
    except OaLetterError as e:
        _raise(e)


@router.get("/templates/{template_id}/versions")
async def template_versions(template_id: int, db: AsyncSession = Depends(get_db),
                            current_user: User = Depends(get_current_user)):
    sites = await _sites(db, current_user, "automation.templates", "مدیریت قالب نامه")
    service = OaLetterService(db)
    try:
        _check(sites, (await service.get_template(template_id)).site_id)
    except OaLetterError as e:
        _raise(e)
    return await service.template_versions(template_id)


@router.post("/templates/logo", status_code=status.HTTP_201_CREATED)
async def upload_logo(request: Request, site_id: int = Form(...), file: UploadFile = File(...),
                      db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """بارگذاری لوگوی سربرگ (PNG/JPG/WEBP). تا وقتی در یک نسخه‌ی قالب ذخیره نشود موقت است."""
    _check(await _sites(db, current_user, "automation.templates", "مدیریت قالب نامه"), site_id)
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
        row = await service.files.upload(site_id=site_id, filename=file.filename or "", chunks=chunks(),
                                         user=current_user, purpose="template", ip=get_client_ip(request),
                                         formats=LOGO_FORMATS)
    except OaFileError as e:
        _raise(e)
    if row.status != "clean":
        raise HTTPException(status_code=409, detail="لوگو هنوز بررسی نشده (اسکن ویروس)؛ چند دقیقه بعد دوباره بارگذاری کنید")
    return file_out(row)


@router.get("/templates/logo/{file_id}")
async def show_logo(file_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """تصویر لوگو برای پیش‌نمایش؛ فقط دارندگان automation.templates یا automation.compose همان سایت."""
    service = OaLetterService(db)
    try:
        f = await service.logo_file(file_id)
    except OaLetterError as e:
        _raise(e)
    allowed = False
    for code in ("automation.templates", "automation.compose"):
        sites = await get_sites_with_permission(db, current_user, code)
        if sites is None or f.site_id in sites:
            allowed = True
            break
    if not allowed:
        raise HTTPException(status_code=403, detail="به این فایل دسترسی ندارید")
    return StreamingResponse(
        service.files.storage.iter_file(f.storage_key),
        media_type=f.content_type or "application/octet-stream",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=86400",
                 "Content-Disposition": "inline", "Content-Length": str(f.size)},
    )


# ================= پیش‌نویس =================


class DraftCreateIn(BaseModel):
    site_id: int
    paper_size: str = "A4"
    template_id: int | None = None


class DraftSaveIn(BaseModel):
    subject: str = Field(default="", max_length=2000)
    body_html: str = ""
    paper_size: str = "A4"
    template_id: int | None = None
    urgency: str = "normal"
    confidentiality: str = "normal"
    row_version: int


@router.get("/compose/options")
async def compose_options(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """سایت‌هایی که کاربر در آن‌ها می‌تواند نامه بنویسد + قالب‌های فعال هر سایت + برچسب فوریت/محرمانگی."""
    from app.core import oa_letter_rules as rules

    sites = await _sites(db, current_user, "automation.compose", "نوشتن نامه")
    templates = await OaLetterService(db).list_templates(sites, include_inactive=False)
    return {
        "sites": await _site_list(db, sites),
        "templates": [
            {"id": t["id"], "site_id": t["site_id"], "name": t["name"], "default_paper_size": t["default_paper_size"]}
            for t in templates if t["version_id"]
        ],
        "urgencies": rules.URGENCIES,
        "confidentiality": rules.CONFIDENTIALITY,
    }


@router.get("/drafts")
async def my_drafts(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _sites(db, current_user, "automation.compose", "نوشتن نامه")
    return await OaLetterService(db).my_drafts(current_user)


@router.post("/drafts", status_code=status.HTTP_201_CREATED)
async def create_draft(payload: DraftCreateIn, db: AsyncSession = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    _check(await _sites(db, current_user, "automation.compose", "نوشتن نامه"), payload.site_id)
    try:
        return await OaLetterService(db).create_draft(user=current_user, **payload.model_dump())
    except OaLetterError as e:
        _raise(e)


async def _draft_site_check(db: AsyncSession, user: User, letter_id: int) -> OaLetterService:
    sites = await _sites(db, user, "automation.compose", "نوشتن نامه")
    service = OaLetterService(db)
    try:
        letter = await service._own_letter(letter_id, user)
    except OaLetterError as e:
        _raise(e)
    _check(sites, letter.site_id)
    return service


@router.get("/drafts/{letter_id}")
async def get_draft(letter_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = await _draft_site_check(db, current_user, letter_id)
    return await service.draft_out(letter_id, current_user)


@router.put("/drafts/{letter_id}")
async def save_draft(letter_id: int, payload: DraftSaveIn, db: AsyncSession = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    service = await _draft_site_check(db, current_user, letter_id)
    try:
        return await service.save_draft(letter_id, user=current_user, **payload.model_dump())
    except OaLetterError as e:
        _raise(e)


@router.delete("/drafts/{letter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def discard_draft(letter_id: int, db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    service = await _draft_site_check(db, current_user, letter_id)
    try:
        await service.discard_draft(letter_id, current_user)
    except OaLetterError as e:
        _raise(e)
