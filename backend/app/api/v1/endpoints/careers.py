"""Careers: anonymous application, authenticated HR management and public copy."""
import hashlib
import hmac
import json
import logging
import os
import secrets
import socket
import struct
from pathlib import Path
from fastapi import BackgroundTasks, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from app.core.permission_grants import grants_subquery
from app.core.ip_allowlist import get_client_ip
from app.core.config import get_settings
from app.models.user import Permission
from app.db.session import AsyncSessionLocal
from app.services.push_service import PushService
import re
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.careers import CareerApplication, CareerPageSetting
from app.models.user import User

router = APIRouter()
DEFAULT_PAGE = {"title": "همکاری با فواد الیاف", "introduction": "برای همکاری با شرکت فواد الیاف فرم زیر را تکمیل کنید.", "instructions": "درج اطلاعات صحیح ضروری است. تکمیل این فرم تعهدی برای استخدام ایجاد نمی‌کند.", "is_open": True}
STATUSES = {"new", "reviewing", "interview", "accepted", "rejected", "archived"}


class CareerPageIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    introduction: str = Field(min_length=5, max_length=8000)
    instructions: str = Field(min_length=5, max_length=8000)
    is_open: bool = True


class CareerSubmitIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=160)
    mobile: str = Field(pattern=r"^09\d{9}$")
    requested_position: str = Field(min_length=2, max_length=160)
    details: dict = Field(default_factory=dict)
    consent: bool
    # Hidden honeypot - should remain empty on real browser forms
    website: str = Field(default="", max_length=100)

    @field_validator("details")
    @classmethod
    def limit_data(cls, v):
        import json
        if len(json.dumps(v, ensure_ascii=False)) > 30000:
            raise ValueError("حجم اطلاعات فرم بیش از حد مجاز است")
        return v


class HrReviewIn(BaseModel):
    status: str
    hr_note: str = Field(default="", max_length=8000)


# The recruitment application contains sensitive personal/medical data. A grant
# MUST be global; grants scoped to one site do not expose all applicants.
async def require_hr(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> User:
    if user.is_superuser:
        return user
    g = grants_subquery()
    allowed = await db.scalar(select(g.c.user_id).where(
        g.c.user_id == user.id, g.c.code == "careers.manage", g.c.site_id.is_(None)).limit(1))
    if allowed is None:
        raise HTTPException(403, detail="دسترسی سراسری منابع انسانی برای پرونده‌های استخدامی لازم است")
    return user


logger = logging.getLogger("faipco.careers")
# Keep outside web root and shared mounts; configure this path explicitly in production.
RESUME_DIR = Path(get_settings().CAREERS_RESUME_DIR)
MAX_RESUME_BYTES = 3 * 1024 * 1024
MAX_BODY_BYTES = 4 * 1024 * 1024
RATE_WINDOW_MINUTES = 60


async def notify_recruiters(application_id: int) -> None:
    """Push only to global HR grant holders; no applicant-sensitive data in notification."""
    try:
        async with AsyncSessionLocal() as db:
            g = grants_subquery()
            ids = {int(x) for x in (await db.scalars(
                select(g.c.user_id).join(User, User.id == g.c.user_id).where(
                    g.c.code == "careers.manage", g.c.site_id.is_(None), User.is_active.is_(True))
            )).all()}
            ids.update(int(x) for x in (await db.scalars(
                select(User.id).where(User.is_superuser.is_(True), User.is_active.is_(True))
            )).all())
            if ids:
                await PushService(db).notify_users(ids, url="/careers/admin", body="درخواست استخدام جدیدی ثبت شده است.")
    except Exception:
        logger.exception("Recruitment notification failed for application %s", application_id)


def validate_application(payload: CareerSubmitIn) -> None:
    if payload.website or not payload.consent or payload.details.get("accuracy_confirmed") is not True:
        raise HTTPException(422, detail="درخواست یا تأییدیه آن معتبر نیست")
    d = payload.details
    if any(not isinstance(k, str) or len(k) > 80 or k.startswith("_") for k in d):
        raise HTTPException(422, detail="کلیدهای فرم معتبر نیستند")
    required = ("gender", "religion", "denomination", "city", "employment_type", "available_from", "education", "skills", "employed_now", "has_work_experience", "health_status", "had_surgery", "smokes")
    if any(not isinstance(d.get(k), str) or not d[k].strip() for k in required):
        raise HTTPException(422, detail="فیلدهای الزامی فرم کامل نشده‌اند")
    values = {"gender": {"male", "female"}, "employment_type": {"fulltime", "parttime", "project"},
              "employed_now": {"yes", "no"}, "has_work_experience": {"yes", "no"},
              "health_status": {"healthy", "condition"}, "had_surgery": {"yes", "no"}, "smokes": {"yes", "no"}}
    if any(d[k] not in choices for k, choices in values.items()):
        raise HTTPException(422, detail="یکی از گزینه‌های انتخابی معتبر نیست")
    if d["gender"] == "male":
        if d.get("military_status") not in {"completed", "subject", "exempt", "serving"}:
            raise HTTPException(422, detail="وضعیت نظام وظیفه الزامی است")
        if d["military_status"] == "exempt" and not str(d.get("military_exemption_reason") or "").strip():
            raise HTTPException(422, detail="علت معافیت الزامی است")
    for key in ("work_history", "education_history", "training_history", "references", "dependents"):
        rows = d.get(key, [])
        if not isinstance(rows, list) or len(rows) > 12 or any(not isinstance(row, dict) for row in rows):
            raise HTTPException(422, detail="تعداد یا ساختار سوابق معتبر نیست")
        for row in rows:
            if len(row) > 20 or any(not isinstance(k, str) or len(k)>80 or not isinstance(v, str) or len(v)>500 for k,v in row.items()):
                raise HTTPException(422, detail="اطلاعات سابقه نامعتبر است")
    if d["has_work_experience"] == "yes":
        if not d.get("work_history") or not all(str(r.get("company") or "").strip() and str(r.get("position") or "").strip() for r in d["work_history"]):
            raise HTTPException(422, detail="نام شرکت و سمت در سوابق کاری الزامی‌اند")
    if any(len(str(v)) > 4000 for v in d.values() if isinstance(v, str)):
        raise HTTPException(422, detail="طول برخی توضیحات بیش از حد مجاز است")


def scan_pdf_with_clamav(content: bytes) -> None:
    """Optional local ClamAV INSTREAM; fail closed when configured but unavailable."""
    sock = get_settings().CAREERS_CLAMAV_SOCKET.strip()
    if not sock:
        return
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(10)
            connection.connect(sock)
            connection.sendall(b"zINSTREAM\0")
            for offset in range(0, len(content), 65536):
                chunk = content[offset:offset+65536]
                connection.sendall(struct.pack(">I", len(chunk)) + chunk)
            connection.sendall(struct.pack(">I", 0))
            reply = connection.recv(4096)
        if b"OK" not in reply or b"FOUND" in reply:
            raise HTTPException(422, detail="رزومه در بررسی امنیتی تأیید نشد")
    except HTTPException:
        raise
    except Exception:
        logger.exception("ClamAV is configured but failed; rejecting resume")
        raise HTTPException(503, detail="بررسی امنیتی فایل در دسترس نیست")


async def store_resume(file: UploadFile | None) -> str | None:
    if file is None or not file.filename:
        return None
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(422, detail="رزومه باید PDF باشد")
    content = await file.read(MAX_RESUME_BYTES + 1)
    if len(content) > MAX_RESUME_BYTES or len(content) < 8 or not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]:
        raise HTTPException(422, detail="فایل PDF نامعتبر یا بزرگ‌تر از ۳ مگابایت است")
    if b"/JavaScript" in content or b"/JS " in content or b"/Launch" in content or b"/EmbeddedFile" in content:
        raise HTTPException(422, detail="فایل PDF دارای محتوای فعال یا پیوست است")
    # Run blocking socket scan outside async event loop.
    import asyncio
    await asyncio.to_thread(scan_pdf_with_clamav, content)
    RESUME_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    stored = secrets.token_hex(24) + ".pdf"
    destination = RESUME_DIR / stored
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return stored


async def save_application(payload: CareerSubmitIn, request: Request, db: AsyncSession, resume_name: str | None = None) -> int:
    page = await get_page(db)
    if page and not page.is_open:
        raise HTTPException(403, detail="ثبت درخواست استخدام غیرفعال است")
    validate_application(payload)
    # Only use the actual peer IP. Never trust user-provided X-Forwarded-For.
    ip = get_client_ip(request)
    salt = get_settings().CAREERS_RATE_LIMIT_SECRET or get_settings().SECRET_KEY
    digest = hmac.new(salt.encode(), ip.encode(), hashlib.sha256).hexdigest()
    # PostgreSQL transaction locks make the rate limit and duplicate check race-safe.
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(digest))))
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(payload.mobile + payload.requested_position.strip()))))
    recent = datetime.now(timezone.utc) - timedelta(minutes=RATE_WINDOW_MINUTES)
    count = await db.scalar(select(func.count(CareerApplication.id)).where(CareerApplication.ip_digest == digest, CareerApplication.created_at >= recent))
    if (count or 0) >= 3:
        raise HTTPException(429, detail="تعداد درخواست‌های ثبت‌شده بیش از حد مجاز است")
    # Avoid repeated applications with identical contact and job title over a short interval.
    duplicate = await db.scalar(select(CareerApplication.id).where(
        CareerApplication.mobile == payload.mobile, CareerApplication.requested_position == payload.requested_position.strip(),
        CareerApplication.created_at >= datetime.now(timezone.utc) - timedelta(hours=24)).limit(1))
    if duplicate:
        raise HTTPException(429, detail="برای این شماره و عنوان شغلی اخیراً درخواستی ثبت شده است")
    d = dict(payload.details)
    if resume_name:
        d["_resume_file"] = resume_name
    record = CareerApplication(full_name=payload.full_name.strip(), mobile=payload.mobile,
        requested_position=payload.requested_position.strip(), details=d, ip_digest=digest)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record.id


async def get_page(db):
    return await db.get(CareerPageSetting, 1)


@router.get("/page")
async def public_page(db: AsyncSession = Depends(get_db)):
    record = await get_page(db)
    return {k: getattr(record, k) for k in DEFAULT_PAGE} if record else DEFAULT_PAGE


@router.put("/page")
async def save_page(payload: CareerPageIn, db: AsyncSession = Depends(get_db), user: User = Depends(require_hr)):
    record = await get_page(db)
    if record is None:
        record = CareerPageSetting(id=1, **payload.model_dump(), updated_by=user.id)
        db.add(record)
    else:
        for key, value in payload.model_dump().items():
            setattr(record, key, value)
        record.updated_by = user.id
    await db.commit()
    return {"success": True}


@router.post("/apply", status_code=201)
async def apply(payload: CareerSubmitIn, request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    application_id = await save_application(payload, request, db)
    background_tasks.add_task(notify_recruiters, application_id)
    return {"success": True, "message": "درخواست استخدام شما با موفقیت ثبت شد."}


@router.post("/apply-with-resume", status_code=201)
async def apply_with_resume(request: Request, background_tasks: BackgroundTasks,
                            data: str = Form(..., max_length=32000), resume: UploadFile | None = File(None),
                            db: AsyncSession = Depends(get_db)):
    if len(data) > 32000:
        raise HTTPException(413, detail="حجم فرم بیش از حد مجاز است")
    try:
        payload = CareerSubmitIn.model_validate_json(data)
    except Exception:
        raise HTTPException(422, detail="ساختار درخواست نامعتبر است")
    validate_application(payload)
    if request.headers.get("content-length"):
        try:
            if int(request.headers["content-length"]) > MAX_BODY_BYTES:
                raise HTTPException(413, detail="حجم درخواست بیش از حد مجاز است")
        except ValueError:
            raise HTTPException(400, detail="اندازه درخواست نامعتبر است")
    # Reject duplicate / throttled requests BEFORE writing candidate files.
    ip = get_client_ip(request)
    salt = get_settings().CAREERS_RATE_LIMIT_SECRET or get_settings().SECRET_KEY
    digest = hmac.new(salt.encode(), ip.encode(), hashlib.sha256).hexdigest()
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    rate = await db.scalar(select(func.count(CareerApplication.id)).where(CareerApplication.ip_digest == digest, CareerApplication.created_at >= recent))
    if (rate or 0) >= 3:
        raise HTTPException(429, detail="تعداد درخواست‌های ثبت‌شده بیش از حد مجاز است")
    name = await store_resume(resume)
    try:
        application_id = await save_application(payload, request, db, name)
    except Exception:
        if name:
            (RESUME_DIR / name).unlink(missing_ok=True)
        raise
    background_tasks.add_task(notify_recruiters, application_id)
    return {"success": True, "message": "درخواست استخدام شما با موفقیت ثبت شد."}


@router.get("/applications/{application_id}/resume")
async def download_resume(application_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_hr)):
    a = await db.get(CareerApplication, application_id)
    if a is None:
        raise HTTPException(404, detail="درخواست یافت نشد")
    name = (a.details or {}).get("_resume_file")
    if not isinstance(name, str) or not re.fullmatch(r"[0-9a-f]{48}\.pdf", name):
        raise HTTPException(404, detail="رزومه‌ای ثبت نشده است")
    path = RESUME_DIR / name
    if not path.is_file() or path.is_symlink():
        raise HTTPException(404, detail="فایل رزومه یافت نشد")
    return FileResponse(path, media_type="application/octet-stream", filename="resume.pdf",
        content_disposition_type="attachment", headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.get("/latest")
async def latest_application(db: AsyncSession = Depends(get_db), _user: User = Depends(require_hr)):
    # Only a numeric id; no PII appears in polling/notifications.
    latest = await db.scalar(select(func.max(CareerApplication.id)))
    return {"latest_id": latest or 0}


@router.get("/access")
async def careers_access(_user: User = Depends(require_hr)):
    return {"allowed": True}


@router.get("/applications")
async def list_applications(page: int = 1, page_size: int = 20, status_filter: str | None = None,
                            db: AsyncSession = Depends(get_db), user: User = Depends(require_hr)):
    page = max(page, 1)
    page_size = min(100, max(1, page_size))
    query = select(CareerApplication)
    count_query = select(func.count(CareerApplication.id))
    if status_filter in STATUSES:
        query = query.where(CareerApplication.status == status_filter)
        count_query = count_query.where(CareerApplication.status == status_filter)
    total = await db.scalar(count_query)
    items = (await db.scalars(query.order_by(CareerApplication.created_at.desc()).offset((page-1)*page_size).limit(page_size))).all()
    return {"total": total, "items": [{"id": a.id, "full_name": a.full_name, "requested_position": a.requested_position,
        "status": a.status, "created_at": a.created_at} for a in items]}


@router.get("/applications/{application_id}")
async def get_application(application_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(require_hr)):
    a = await db.get(CareerApplication, application_id)
    if not a:
        raise HTTPException(404, detail="درخواست یافت نشد")
    return {"id": a.id, "full_name": a.full_name, "mobile": a.mobile, "requested_position": a.requested_position,
            "details": a.details, "status": a.status, "hr_note": a.hr_note, "created_at": a.created_at}


@router.put("/applications/{application_id}/review")
async def review(application_id: int, payload: HrReviewIn, db: AsyncSession = Depends(get_db), user: User = Depends(require_hr)):
    if payload.status not in STATUSES:
        raise HTTPException(422, detail="وضعیت نامعتبر است")
    a = await db.get(CareerApplication, application_id)
    if not a:
        raise HTTPException(404, detail="درخواست یافت نشد")
    a.status, a.hr_note, a.changed_by = payload.status, payload.hr_note, user.id
    await db.commit()
    return {"success": True}
