"""
اتوماسیون اداری فاز ۳الف: گیرنده و پیوست پیش‌نویس، ارسال، کارتابل، مشاهده‌ی نامه، ارجاع، انجام مسئولیت، هامش، محرمانه کردن.

- کارتابل و هر کاری روی نامه: مجوز automation.access (هر سایت) + دسترسی صریح به همان نامه (core/oa_access_rules.can).
- گیرنده/پیوست/ارسال پیش‌نویس: فقط سازنده با automation.access (ادغام compose، Migration 138).
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.ip_allowlist import get_client_ip
from app.core.site_access import get_sites_with_permission
from app.db.session import get_db
from app.models.user import User
from app.services.oa_cartable_service import (
    OaCartableError,
    OaCartableService,
    send_pushes,
)
from app.services.oa_secretary_service import OaSecretaryService
from app.services.oa_secretariat_service import OaSecretariatError, OaSecretariatService
from app.services.oa_signature_service import OaSignatureError, OaSignatureService
from app.services.oa_approval_service import OaApprovalService

router = APIRouter()
UPLOAD_CHUNK = 1 << 20


def _raise(e: Exception):
    raise HTTPException(status_code=getattr(e, "status_code", 400), detail=str(e))


async def _require(db: AsyncSession, user: User, code: str, label: str) -> set[int] | None:
    sites = await get_sites_with_permission(db, user, code)
    if sites is not None and not sites:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"اجازه‌ی {label} را ندارید")
    return sites


async def _compose_draft(db: AsyncSession, user: User, letter_id: int) -> OaCartableService:
    await _require(db, user, "automation.access", "نوشتن نامه")
    service = OaCartableService(db)
    try:
        await service._own_draft(letter_id, user)
    except OaCartableError as e:
        _raise(e)
    return service


def _stream(service: OaCartableService, f, name: str) -> StreamingResponse:
    return StreamingResponse(
        service.files.storage.iter_file(f.storage_key),
        media_type=f.content_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}", "X-Content-Type-Options": "nosniff",
                 "Cache-Control": "private, no-store", "Content-Length": str(f.size)},
    )


# ================= انتخاب گیرنده =================


@router.get("/people")
async def people(q: str = "", department_id: int | None = None, title: str = "", db: AsyncSession = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """پرسنل قابل انتخاب به‌عنوان گیرنده/ارجاع (فقط نام، سمت، واحد)."""
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        return await OaCartableService(db).picker(current_user, q=q[:100], department_id=department_id, title=title[:100])
    except OaCartableError as e:
        _raise(e)


# ================= پیش‌نویس: گیرنده، پیوست، ارسال =================


class RecipientIn(BaseModel):
    employee_id: int
    role: str
    selected_via: str = "direct"


class RecipientsIn(BaseModel):
    items: list[RecipientIn] = Field(max_length=500)


@router.get("/drafts/{letter_id}/extras")
async def draft_extras(letter_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = await _compose_draft(db, current_user, letter_id)
    return await service.draft_extras(await service._own_draft(letter_id, current_user))


@router.put("/drafts/{letter_id}/recipients")
async def set_recipients(letter_id: int, payload: RecipientsIn, db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    service = await _compose_draft(db, current_user, letter_id)
    try:
        return await service.set_recipients(letter_id, current_user, [i.model_dump() for i in payload.items])
    except OaCartableError as e:
        _raise(e)


@router.post("/drafts/{letter_id}/attachments", status_code=status.HTTP_201_CREATED)
async def add_attachment(letter_id: int, request: Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    service = await _compose_draft(db, current_user, letter_id)

    async def chunks():
        while True:
            block = await file.read(UPLOAD_CHUNK)
            if not block:
                return
            yield block

    try:
        return await service.add_attachment(letter_id, current_user, filename=file.filename or "", chunks=chunks(),
                                            ip=get_client_ip(request))
    except OaCartableError as e:
        _raise(e)


@router.delete("/drafts/{letter_id}/attachments/{attachment_id}")
async def remove_attachment(letter_id: int, attachment_id: int, db: AsyncSession = Depends(get_db),
                            current_user: User = Depends(get_current_user)):
    service = await _compose_draft(db, current_user, letter_id)
    try:
        return await service.remove_attachment(letter_id, attachment_id, current_user)
    except OaCartableError as e:
        _raise(e)


@router.get("/drafts/{letter_id}/attachments/{attachment_id}/download")
async def download_draft_attachment(letter_id: int, attachment_id: int, db: AsyncSession = Depends(get_db),
                                    current_user: User = Depends(get_current_user)):
    service = await _compose_draft(db, current_user, letter_id)
    try:
        f, name = await service.draft_attachment_for_download(letter_id, attachment_id, current_user)
    except OaCartableError as e:
        _raise(e)
    return _stream(service, f, name)


class SendIn(BaseModel):
    row_version: int


@router.post("/drafts/{letter_id}/send")
async def send_letter(letter_id: int, payload: SendIn, background_tasks: BackgroundTasks,
                      db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """ارسال نامه‌ی داخلی به گیرندگان (بدون شماره در فاز ۳الف). تکرار همان درخواست نامه را دوباره نمی‌فرستد."""
    service = await _compose_draft(db, current_user, letter_id)
    try:
        lid = await service.send(letter_id, current_user, payload.row_version)
    except OaCartableError as e:
        _raise(e)
    background_tasks.add_task(send_pushes, service.pushes)
    return {"letter_id": lid}


# ================= گردش تأیید ترتیبی (پاراف / تأیید / امضا) =================


class ApprovalStepIn(BaseModel):
    employee_id: int
    kind: str


class ApprovalPlanIn(BaseModel):
    steps: list[ApprovalStepIn] = Field(max_length=20)


class ApprovalActIn(BaseModel):
    note: str = Field(default="", max_length=2000)


@router.put("/drafts/{letter_id}/approval-steps")
async def set_approval_steps(letter_id: int, payload: ApprovalPlanIn, db: AsyncSession = Depends(get_db),
                             current_user: User = Depends(get_current_user)):
    """مسیر تأیید پیش‌نویس (به ترتیب). نامه‌ی «از طرف» مدیر: امضای مدیر خودکار در آخر اضافه می‌شود."""
    await _compose_draft(db, current_user, letter_id)
    try:
        return await OaApprovalService(db).set_plan(letter_id, current_user, [s.model_dump() for s in payload.steps])
    except OaCartableError as e:
        _raise(e)


@router.post("/drafts/{letter_id}/submit")
async def submit_for_approval(letter_id: int, payload: SendIn, background_tasks: BackgroundTasks,
                              db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _compose_draft(db, current_user, letter_id)
    service = OaApprovalService(db)
    try:
        lid = await service.submit(letter_id, current_user, payload.row_version)
    except OaCartableError as e:
        _raise(e)
    background_tasks.add_task(send_pushes, service.pushes)
    return {"letter_id": lid}


@router.post("/letters/{letter_id}/withdraw")
async def withdraw_from_approval(letter_id: int, db: AsyncSession = Depends(get_db),
                                 current_user: User = Depends(get_current_user)):
    """پس گرفتن نامه‌ی در انتظار تأیید توسط نویسنده (دوباره پیش‌نویس می‌شود)."""
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        return await OaApprovalService(db).withdraw(letter_id, current_user)
    except OaCartableError as e:
        _raise(e)


@router.post("/approval-steps/{step_id}/approve")
async def approve_step(step_id: int, payload: ApprovalActIn, background_tasks: BackgroundTasks,
                       db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """پاراف / تأیید / تأیید و امضا (مرحله‌ی فعال خود کاربر). آخرین مرحله ← شماره و ارسال خودکار."""
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    service = OaApprovalService(db)
    try:
        result = await service.approve(step_id, current_user, payload.note)
    except OaCartableError as e:
        _raise(e)
    background_tasks.add_task(send_pushes, service.pushes)
    return result


@router.post("/approval-steps/{step_id}/return")
async def return_step(step_id: int, payload: ApprovalActIn, background_tasks: BackgroundTasks,
                      db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """برگشت برای اصلاح (توضیح اجباری) — نامه به پیش‌نویس نویسنده برمی‌گردد."""
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    service = OaApprovalService(db)
    try:
        result = await service.return_for_changes(step_id, current_user, payload.note)
    except OaCartableError as e:
        _raise(e)
    background_tasks.add_task(send_pushes, service.pushes)
    return result


# ================= کارتابل و نامه =================


@router.get("/cartable")
async def cartable(box: str = "inbox", q: str = "", page: int = 1, db: AsyncSession = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        return await OaCartableService(db).cartable(current_user, box=box, q=q[:100], page=page)
    except OaCartableError as e:
        _raise(e)


@router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """کارت داشبورد: شمارنده‌ها + حداکثر سه مورد اولویت‌دار."""
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    service = OaCartableService(db)
    try:
        me = await service._me(current_user)
        return {"counters": await service.counters(me.id), "items": await service.dashboard_items(current_user)}
    except OaCartableError as e:
        _raise(e)


@router.get("/counters")
async def counters(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    if not current_user.employee_id:
        return {"unread": 0, "pending": 0, "overdue": 0}
    return await OaCartableService(db).counters(current_user.employee_id)


@router.get("/letters/{letter_id}")
async def letter_detail(letter_id: int, request: Request, db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        return await OaCartableService(db).letter_detail(letter_id, current_user, ip=get_client_ip(request))
    except OaCartableError as e:
        _raise(e)


@router.get("/letters/{letter_id}/attachments/{attachment_id}/download")
async def download_attachment(letter_id: int, attachment_id: int, request: Request, db: AsyncSession = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    service = OaCartableService(db)
    try:
        f, name = await service.attachment_for_download(letter_id, attachment_id, current_user, get_client_ip(request))
    except OaCartableError as e:
        _raise(e)
    return _stream(service, f, name)


class ReferIn(BaseModel):
    assignees: list[int] = Field(max_length=50)
    kind: str = "action"
    instruction: str = Field(default="", max_length=2000)
    allow_refer: bool = False
    due_at: datetime | None = None


@router.post("/letters/{letter_id}/refer")
async def refer(letter_id: int, payload: ReferIn, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    service = OaCartableService(db)
    try:
        await service.refer(letter_id, current_user, assignees=payload.assignees, kind=payload.kind,
                            instruction=payload.instruction, allow_refer=payload.allow_refer, due_at=payload.due_at)
    except OaCartableError as e:
        _raise(e)
    background_tasks.add_task(send_pushes, service.pushes)
    return {"success": True}


class DoneIn(BaseModel):
    note: str = Field(default="", max_length=4000)


@router.post("/tasks/{task_id}/done")
async def complete_task(task_id: int, payload: DoneIn, db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        await OaCartableService(db).complete_task(task_id, current_user, payload.note)
    except OaCartableError as e:
        _raise(e)
    return {"success": True}


def _chunks_of(file: UploadFile):
    async def gen():
        while True:
            block = await file.read(UPLOAD_CHUNK)
            if not block:
                return
            yield block

    return gen()


@router.post("/tasks/{task_id}/complete")
async def complete_task_with_files(task_id: int, request: Request, note: str = Form(default="", max_length=4000),
                                   files: list[UploadFile] = File(default=[]), db: AsyncSession = Depends(get_db),
                                   current_user: User = Depends(get_current_user)):
    """ثبت نتیجه همراه با پیوست (multipart: note + files[]). سقف از «پیوست اقدام» تنظیمات سایت نامه."""
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        await OaCartableService(db).complete_task(
            task_id, current_user, note, [(f.filename or "", _chunks_of(f)) for f in files if f.filename],
            ip=get_client_ip(request),
        )
    except OaCartableError as e:
        _raise(e)
    return {"success": True}


@router.get("/letters/{letter_id}/task-attachments/{attachment_id}/download")
async def download_task_attachment(letter_id: int, attachment_id: int, request: Request, db: AsyncSession = Depends(get_db),
                                   current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    service = OaCartableService(db)
    try:
        f, name = await service.task_attachment_for_download(letter_id, attachment_id, current_user, get_client_ip(request))
    except OaCartableError as e:
        _raise(e)
    return _stream(service, f, name)


class NoteIn(BaseModel):
    text: str = Field(max_length=4000)


@router.post("/letters/{letter_id}/notes", status_code=status.HTTP_201_CREATED)
async def add_note(letter_id: int, payload: NoteIn, db: AsyncSession = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        await OaCartableService(db).add_note(letter_id, current_user, payload.text)
    except OaCartableError as e:
        _raise(e)
    return {"success": True}


class ConfidentialIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


@router.post("/letters/{letter_id}/make-confidential")
async def make_confidential(letter_id: int, payload: ConfidentialIn, db: AsyncSession = Depends(get_db),
                            current_user: User = Depends(get_current_user)):
    """عادی → محرمانه، فقط ایجادکننده/فرستنده و فقط بعد از ارسال (محرمانه → عادی ممنوع)."""
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        await OaCartableService(db).make_confidential(letter_id, current_user, payload.reason)
    except OaCartableError as e:
        _raise(e)
    return {"success": True}


# ================= پاسخ و تنظیمات اعلان =================


class RelatedDraftIn(BaseModel):
    type: str = "reply"  # reply (پاسخ) | correction (اصلاحیه)


class CancelIn(BaseModel):
    reason: str = Field(max_length=2000)


@router.post("/letters/{letter_id}/cancel")
async def cancel_letter(letter_id: int, payload: CancelIn, background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """ابطال نامه‌ی ثبت‌شده (automation.cancel سایت نامه)؛ شماره باطل می‌شود و نامه و سابقه می‌مانند."""
    await _require(db, current_user, "automation.cancel", "ابطال نامه")
    service = OaCartableService(db)
    try:
        await service.cancel(letter_id, current_user, payload.reason)
    except OaCartableError as e:
        _raise(e)
    background_tasks.add_task(send_pushes, service.pushes)
    return {"success": True}


@router.post("/letters/{letter_id}/related-draft", status_code=status.HTTP_201_CREATED)
async def related_draft(letter_id: int, payload: RelatedDraftIn, db: AsyncSession = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    """پیش‌نویس پاسخ یا اصلاحیه (type: reply | correction) به نامه‌ای که کاربر به آن دسترسی دارد. خروجی: {draft_id}."""
    await _require(db, current_user, "automation.access", "نوشتن نامه")
    try:
        return {"draft_id": await OaCartableService(db).create_related_draft(letter_id, current_user, payload.type)}
    except OaCartableError as e:
        _raise(e)


class PrefsIn(BaseModel):
    enabled: dict[str, bool]


@router.get("/notification-prefs")
async def get_notification_prefs(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        return await OaCartableService(db).get_prefs(current_user)
    except OaCartableError as e:
        _raise(e)


@router.put("/notification-prefs")
async def set_notification_prefs(payload: PrefsIn, db: AsyncSession = Depends(get_db),
                                 current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        return await OaCartableService(db).set_prefs(current_user, payload.enabled)
    except OaCartableError as e:
        _raise(e)


# ================= منشی =================


class SecretaryIn(BaseModel):
    employee_id: int


class SecretaryPairIn(BaseModel):
    principal_employee_id: int
    secretary_employee_id: int


@router.get("/secretaries/mine")
async def my_secretaries(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """منشی‌های من (که از طرف من نامه می‌فرستند) و کسانی که من منشی آن‌ها هستم."""
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        return await OaSecretaryService(db).mine(current_user)
    except OaCartableError as e:
        _raise(e)


@router.post("/secretaries/mine")
async def add_my_secretary(payload: SecretaryIn, db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        return await OaSecretaryService(db).add_mine(current_user, payload.employee_id)
    except OaCartableError as e:
        _raise(e)


@router.delete("/secretaries/mine/{pair_id}")
async def remove_my_secretary(pair_id: int, db: AsyncSession = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        return await OaSecretaryService(db).remove_mine(current_user, pair_id)
    except OaCartableError as e:
        _raise(e)


@router.get("/secretaries")
async def all_secretaries(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """مدیریت منشی‌ها برای دارنده‌ی automation.settings (سایت‌محور بر اساس سایت مدیر)."""
    sites = await _require(db, current_user, "automation.settings", "تنظیمات اتوماسیون اداری")
    return await OaSecretaryService(db).admin_list(sites)


@router.get("/secretaries/people")
async def secretary_people(q: str = "", department_id: int | None = None, title: str = "",
                           db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """پرسنل قابل انتخاب به‌عنوان مدیر/منشی برای مسئول تنظیمات (بدون نیاز به پرسنل بودن خود او)."""
    sites = await _require(db, current_user, "automation.settings", "تنظیمات اتوماسیون اداری")
    return await OaSecretaryService(db).admin_people(sites, q=q[:100], department_id=department_id, title=title[:100])


@router.post("/secretaries")
async def admin_add_secretary(payload: SecretaryPairIn, db: AsyncSession = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    sites = await _require(db, current_user, "automation.settings", "تنظیمات اتوماسیون اداری")
    try:
        return await OaSecretaryService(db).admin_add(current_user, sites, payload.principal_employee_id,
                                                      payload.secretary_employee_id)
    except OaCartableError as e:
        _raise(e)


@router.delete("/secretaries/{pair_id}")
async def admin_remove_secretary(pair_id: int, db: AsyncSession = Depends(get_db),
                                 current_user: User = Depends(get_current_user)):
    sites = await _require(db, current_user, "automation.settings", "تنظیمات اتوماسیون اداری")
    try:
        return await OaSecretaryService(db).admin_remove(current_user, sites, pair_id)
    except OaCartableError as e:
        _raise(e)


# ================= دبیرخانه و پیشوند شماره (automation.settings) =================


class SecretariatIn(BaseModel):
    number_prefix: str = Field(max_length=20)
    name: str | None = Field(default=None, max_length=200)


@router.get("/secretariats")
async def list_secretariats(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    sites = await _require(db, current_user, "automation.settings", "تنظیمات اتوماسیون اداری")
    return await OaSecretariatService(db).list_for_admin(sites)


@router.put("/secretariats/{site_id}")
async def save_secretariat(site_id: int, payload: SecretariatIn, db: AsyncSession = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    sites = await _require(db, current_user, "automation.settings", "تنظیمات اتوماسیون اداری")
    try:
        return await OaSecretariatService(db).save(current_user, sites, site_id, number_prefix=payload.number_prefix,
                                                   name=payload.name)
    except OaSecretariatError as e:
        _raise(e)


# ================= امضای شخصی =================


def _png(service_files, f) -> StreamingResponse:
    return StreamingResponse(
        service_files.storage.iter_file(f.storage_key), media_type="image/png",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/signature/mine")
async def my_signature(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        return await OaSignatureService(db).mine(current_user)
    except OaSignatureError as e:
        _raise(e)


@router.post("/signature/mine")
async def create_my_signature(file: UploadFile = File(...), method: str = Form(default="upload"),
                              remove_background: bool = Form(default=False), db: AsyncSession = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    """ثبت امضای تازه (رسم: PNG بوم مرورگر؛ بارگذاری: PNG/JPG/WEBP تا ۲ مگابایت). نسخه‌ی قبلی غیرفعال می‌شود."""
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    from app.core.oa_signature_rules import MAX_UPLOAD_BYTES

    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        return await OaSignatureService(db).create(current_user, raw, method=method, remove_background=remove_background)
    except OaSignatureError as e:
        _raise(e)


@router.delete("/signature/mine")
async def deactivate_my_signature(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    try:
        return await OaSignatureService(db).deactivate_mine(current_user)
    except OaSignatureError as e:
        _raise(e)


@router.get("/signature/mine/image")
async def my_signature_image(version_id: int | None = None, db: AsyncSession = Depends(get_db),
                             current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    service = OaSignatureService(db)
    try:
        f = await service.my_file(current_user, version_id)
    except OaSignatureError as e:
        _raise(e)
    return _png(service.files, f)


@router.get("/letters/{letter_id}/signature-image")
async def letter_signature_image(letter_id: int, step_id: int | None = None, db: AsyncSession = Depends(get_db),
                                 current_user: User = Depends(get_current_user)):
    await _require(db, current_user, "automation.access", "استفاده از اتوماسیون اداری")
    service = OaCartableService(db)
    try:
        f = await service.signature_file(letter_id, current_user, step_id)
    except OaCartableError as e:
        _raise(e)
    return _png(service.files, f)
