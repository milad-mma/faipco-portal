"""
اتوماسیون اداری — فاز ۱: تنظیمات پیوست هر سایت، وضعیت اسکنر/فضا و آزمایش آپلود (docs/office-automation.md).

همه با مجوز automation.settings همان سایت (سایت‌محور؛ ادمین کل همه‌ی سایت‌ها). آپلود عمومی پیوست نامه از فاز ۳الف
(با automation.access و دسترسی نامه) اضافه می‌شود.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.ip_allowlist import get_client_ip
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.user import User
from app.services.oa_file_service import OaFileError, OaFileService, file_out

router = APIRouter()

UPLOAD_CHUNK = 1 << 20


def _raise(e: OaFileError):
    raise HTTPException(status_code=e.status_code, detail=str(e))


async def _settings_sites(db: AsyncSession, user: User) -> set[int] | None:
    sites = await get_sites_with_permission(db, user, "automation.settings")
    if sites is not None and not sites:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="اجازه‌ی تنظیمات اتوماسیون اداری را ندارید")
    return sites


def _check_site(sites: set[int] | None, site_id: int) -> None:
    if sites is not None and site_id not in sites:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="به این سایت دسترسی ندارید")


@router.get("/settings/attachments")
async def list_attachment_settings(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """تنظیمات پیوست سایت‌هایی که بیننده automation.settings آن‌ها را دارد + فهرست فرمت‌ها و سقف سرور."""
    sites = await _settings_sites(db, current_user)
    service = OaFileService(db)
    return {"catalog": service.catalog(), "sites": await service.settings_for_sites(sites)}


class AttachmentSettingsIn(BaseModel):
    letter_max_files: int
    letter_max_file_mb: int
    letter_max_total_mb: int
    action_max_files: int
    action_max_file_mb: int
    action_max_total_mb: int
    letter_all_max_total_mb: int
    allowed_formats: list[str]


@router.put("/settings/attachments/{site_id}")
async def save_attachment_settings(
    site_id: int,
    payload: AttachmentSettingsIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_site(await _settings_sites(db, current_user), site_id)
    try:
        return await OaFileService(db).save_site_settings(
            site_id, payload.model_dump(), current_user, ip=get_client_ip(request)
        )
    except OaFileError as e:
        _raise(e)


@router.get("/settings/status")
async def files_status(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """وضعیت ClamAV (نسخه، بانک، قدیمی بودن)، فضای دیسک پوشه‌ی فایل‌ها و تعداد فایل‌ها به تفکیک وضعیت."""
    await _settings_sites(db, current_user)
    return await OaFileService(db).status()


@router.post("/files/test-upload", status_code=status.HTTP_201_CREATED)
async def test_upload(
    request: Request,
    site_id: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    آزمایش آپلود با تنظیمات پیوست یک سایت (چک‌لیست سرور تست: پسوند جعلی، ماکرو، EICAR، ZIP bomb، …). فایل موقت است و
    پس از مهلت پاک‌سازی حذف می‌شود.
    """
    _check_site(await _settings_sites(db, current_user), site_id)

    async def chunks():
        while True:
            block = await file.read(UPLOAD_CHUNK)
            if not block:
                return
            yield block

    try:
        row = await OaFileService(db).upload(
            site_id=site_id, filename=file.filename or "", chunks=chunks(), user=current_user,
            purpose="test", ip=get_client_ip(request),
        )
    except OaFileError as e:
        _raise(e)
    return file_out(row)


@router.get("/files/mine")
async def my_files(
    site_id: int | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """فایل‌های اخیر بارگذاری‌شده توسط خود کاربر (فاز ۱: آزمایش آپلود)."""
    await _settings_sites(db, current_user)
    return [file_out(r) for r in await OaFileService(db).my_recent(current_user, site_id)]


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """دانلود جریانی؛ فقط فایل سالم (clean). فاز ۱: فقط بارگذارنده."""
    service = OaFileService(db)
    try:
        row, name = await service.open_download(file_id, current_user, ip=get_client_ip(request))
    except OaFileError as e:
        _raise(e)
    from urllib.parse import quote

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}",
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
        "Content-Length": str(row.size),
    }
    return StreamingResponse(
        service.storage.iter_file(row.storage_key),
        media_type=row.content_type or "application/octet-stream",
        headers=headers,
    )


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """حذف فایل موقت خود کاربر (فایل ثبت‌شده حذف نمی‌شود)."""
    try:
        await OaFileService(db).delete_own_temp(file_id, current_user, ip=get_client_ip(request))
    except OaFileError as e:
        _raise(e)
