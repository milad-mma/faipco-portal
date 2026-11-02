"""
Endpoint های عکس پرسنلی (پیشوند /profile-photo).

پرسنل:
  GET    /profile-photo/me                 وضعیت: عکس دارد؟ فعال است؟ درخواست در انتظار / آخرین تصمیم
  POST   /profile-photo/me/upload          درخواست بارگذاری (multipart: file) — حجم و عکس کوچک مثل کاراوب در سرور
  POST   /profile-photo/me/delete          درخواست حذف عکس
  DELETE /profile-photo/me/pending         لغو درخواست در انتظار
  GET    /profile-photo/me/pending/image   عکس درخواست در انتظار (پیش‌نمایش)

منابع انسانی (photo.approve، محدود به سایت‌های مجاز):
  GET    /profile-photo/requests?box=pending|done&page=
  GET    /profile-photo/requests/{id}/image | /current
  POST   /profile-photo/requests/{id}/approve   ثبت در دیتابیس منبع (کاراوب) و پرتال
  POST   /profile-photo/requests/{id}/reject    رد با دلیل
"""
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.profile_photo_rules import MAX_INPUT_BYTES, image_media_type
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.employee import Employee
from app.models.user import User
from app.services.profile_photo_service import ProfilePhotoError, ProfilePhotoService

router = APIRouter()

PERMISSION = "photo.approve"


class RejectIn(BaseModel):
    reason: str


def _bad(e: Exception):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


def _image_response(data: bytes | None) -> Response:
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="عکسی یافت نشد")
    return Response(content=data, media_type=image_media_type(data), headers={"Cache-Control": "private, no-store"})


async def _employee(db: AsyncSession, user: User) -> Employee:
    if user.employee_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="این حساب به پرسنلی متصل نیست")
    employee = await db.get(Employee, user.employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل موردنظر یافت نشد")
    return employee


async def _sites(db: AsyncSession, user: User) -> set[int] | None:
    sites = await get_sites_with_permission(db, user, PERMISSION)
    if sites is not None and not sites:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="اجازه بررسی عکس پرسنل را ندارید")
    return sites


# ---------- پرسنل ----------


@router.get("/me")
async def my_photo_status(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await ProfilePhotoService(db).my_status(await _employee(db, current_user))


@router.post("/me/upload", status_code=status.HTTP_201_CREATED)
async def request_upload(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    employee = await _employee(db, current_user)
    content = await file.read(MAX_INPUT_BYTES + 1)
    try:
        await ProfilePhotoService(db).request_upload(employee, content)
    except ProfilePhotoError as e:
        _bad(e)
    return await ProfilePhotoService(db).my_status(employee)


@router.post("/me/delete", status_code=status.HTTP_201_CREATED)
async def request_delete(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _employee(db, current_user)
    try:
        await ProfilePhotoService(db).request_delete(employee)
    except ProfilePhotoError as e:
        _bad(e)
    return await ProfilePhotoService(db).my_status(employee)


@router.delete("/me/pending")
async def cancel_pending(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _employee(db, current_user)
    try:
        await ProfilePhotoService(db).cancel_pending(employee)
    except ProfilePhotoError as e:
        _bad(e)
    return await ProfilePhotoService(db).my_status(employee)


@router.get("/me/pending/image")
async def my_pending_image(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    employee = await _employee(db, current_user)
    return _image_response(await ProfilePhotoService(db).pending_image(employee))


# ---------- منابع انسانی ----------


@router.get("/requests")
async def list_requests(
    box: str = "pending",
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sites = await _sites(db, current_user)
    return await ProfilePhotoService(db).list_requests(sites, "done" if box == "done" else "pending", max(1, page))


@router.get("/requests/{request_id}/image")
async def request_image(request_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    sites = await _sites(db, current_user)
    try:
        return _image_response(await ProfilePhotoService(db).request_image(request_id, sites))
    except ProfilePhotoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/requests/{request_id}/current")
async def request_current_image(request_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    sites = await _sites(db, current_user)
    try:
        return _image_response(await ProfilePhotoService(db).current_image(request_id, sites))
    except ProfilePhotoError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/requests/{request_id}/approve")
async def approve(request_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    sites = await _sites(db, current_user)
    try:
        return await ProfilePhotoService(db).approve(request_id, sites, current_user)
    except ProfilePhotoError as e:
        _bad(e)


@router.post("/requests/{request_id}/reject")
async def reject(
    request_id: int,
    payload: RejectIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sites = await _sites(db, current_user)
    try:
        await ProfilePhotoService(db).reject(request_id, sites, current_user, payload.reason)
    except ProfilePhotoError as e:
        _bad(e)
    return {"ok": True}
