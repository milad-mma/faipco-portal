"""
سرویس Web Push: ذخیره اشتراک هر دستگاه و ارسال اعلان به کاربران هدف.

Ordinary sends are durably queued. The transport reports provider acceptance,
not OS display; missing VAPID is a retryable configuration failure.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from pywebpush import WebPushException, webpush
from sqlalchemy import and_, delete, select, or_, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.push_receipts import issue_receipt
from app.services import notification_templates
from app.core.config import get_settings
from app.models.push_subscription import PushSubscription
from app.models.user_session import UserSession
from app.models.user import User
from app.models.employee import Employee
from app.schemas.push import PushSubscriptionIn
from app.core.push_endpoint_policy import PushHTTPSession, valid_push_endpoint

logger = logging.getLogger("faipco.push")
settings = get_settings()


MAX_TTL_SECONDS = 7 * 24 * 3600
MAX_PAYLOAD_BYTES = 3500  # leave room for Web Push encryption overhead


def provider_retry_after(response):
    """Retry-After may be seconds or an HTTP date. Do not store response text."""
    from email.utils import parsedate_to_datetime
    raw = (getattr(response, "headers", {}) or {}).get("Retry-After")
    if raw is None:
        return None
    try:
        seconds = int(raw)
    except (ValueError, TypeError):
        try:
            seconds = int((parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0, min(seconds, MAX_TTL_SECONDS))


def bounded_payload(data: dict) -> str:
    # json.dumps defaults to ASCII escapes (Persian/emoji expand substantially).
    # Preserve text semantics and bound the final UTF-8 payload, not raw chars.
    data = dict(data)
    data["body"] = str(data.get("body") or "")[:500]
    data["title"] = str(data.get("title") or "")[:200]
    while True:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        if len(payload.encode("utf-8")) <= MAX_PAYLOAD_BYTES:
            return payload
        if not data["body"]:
            raise ValueError("Push metadata exceeds payload limit")
        data["body"] = data["body"][:max(0, len(data["body"]) - 50)]


def send_webpush(**kwargs):
    # Do not allow redirects even to another approved vendor: credentials are
    # bound to the original origin. pywebpush 2.0 supports requests_session.
    with PushHTTPSession() as session:
        return webpush(requests_session=session, **kwargs)


def eligible_subscriptions(user_ids: set[int], *, all_transports=False):
    # No legacy/unbound or revoked/expired sessions may receive any Push.
    # The same rule applies to notices, payroll and OA, not just OA.
    expires_before = datetime.now(timezone.utc) - timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    stmt = (
        select(PushSubscription, UserSession.sid)
        .join(UserSession, PushSubscription.session_id == UserSession.id)
        .join(User, PushSubscription.user_id == User.id)
        .outerjoin(Employee, User.employee_id == Employee.id)
        .where(
            PushSubscription.user_id.in_(user_ids),
            # A modern client is not eligible until its local session gate is durable.
            PushSubscription.client_ready.is_not(False),
            UserSession.user_id == PushSubscription.user_id,
            UserSession.revoked_at.is_(None),
            UserSession.last_seen_at >= expires_before,
            User.is_active.is_(True),
            or_(User.employee_id.is_(None),
                (Employee.is_active.is_(True) & Employee.is_enabled.is_(True))),
        )
    )
    from sqlalchemy.orm import aliased
    from app.models.mobile_device import MobileDevice
    from app.models.system_setting import SystemSetting
    native = aliased(PushSubscription)
    ready = (select(native.id).join(MobileDevice, native.native_device_id == MobileDevice.id)
             .where(native.session_id == UserSession.id, native.user_id == UserSession.user_id,
                    MobileDevice.user_id == UserSession.user_id, MobileDevice.session_sid == UserSession.sid,
                    MobileDevice.revoked_at.is_(None), MobileDevice.perm_notifications.is_(True),
                    select(SystemSetting.key).where(SystemSetting.key == "mobile_app_feature_enabled",
                                                    SystemSetting.value == "true").exists())
             .correlate(UserSession))
    if all_transports:
        return stmt
    return stmt.where(or_(
        and_(PushSubscription.native_device_id.is_(None), ~ready.exists()),
        PushSubscription.id == ready.order_by(native.id.desc()).limit(1).scalar_subquery()))


async def bindings_are_ready(db, bindings: dict) -> bool:
    """True only when every exact subscription/session binding is ready."""
    pairs = {(int(sid), int(session_id)) for sid, session_id in bindings.items()}
    if not pairs:
        return False
    rows = (await db.execute(select(PushSubscription.id, PushSubscription.session_id).where(
        tuple_(PushSubscription.id, PushSubscription.session_id).in_(pairs),
        PushSubscription.client_ready.is_(True),
    ))).all()
    return set(map(tuple, rows)) == pairs


class PushService:
    """ثبت/حذف اشتراک‌های Web Push و ارسال اعلان به مجموعه‌ای از کاربران."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_subscription(self, user_id: int, payload: PushSubscriptionIn, *, session_id: int) -> None:
        """Bind exactly one browser endpoint to its verified authenticated session.

        PostgreSQL UPSERT avoids duplicate unique-endpoint inserts when login and
        layout both register in parallel. An endpoint moved to another account
        must never remain associated with the previous user's session.
        """
        readiness = getattr(payload, "client_ready", None)
        if readiness is True:
            raise ValueError("Readiness must confirm an existing binding")
        stmt = pg_insert(PushSubscription).values(
            user_id=user_id, session_id=session_id, endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh, auth=payload.keys.auth, client_ready=readiness,
        )
        changed = (await self.db.execute(stmt.on_conflict_do_update(
            index_elements=[PushSubscription.endpoint],
            set_={"user_id": user_id, "session_id": session_id,
                  "p256dh": payload.keys.p256dh, "auth": payload.keys.auth,
                  "client_ready": readiness},
            where=or_(PushSubscription.user_id.is_distinct_from(user_id),
                      PushSubscription.session_id.is_distinct_from(session_id),
                      PushSubscription.p256dh.is_distinct_from(payload.keys.p256dh),
                      PushSubscription.auth.is_distinct_from(payload.keys.auth)),
        ).returning(PushSubscription.id))).scalar_one_or_none()
        await self.db.commit()
        if changed is not None and readiness is None:
            # Legacy registration is already committed. Modern clients wait
            # for an explicit readiness confirmation before waking the queue.
            # A wake failure cannot prevent login; periodic recovery remains.
            from app.services.push_dispatch import wake_waiting_jobs
            try:
                await wake_waiting_jobs(self.db, user_id)
                await self.db.commit()
            except Exception as exc:
                await self.db.rollback()
                logger.warning("Deferred push wake failed (user_id=%s): %s", user_id, type(exc).__name__)

    async def confirm_subscription_ready(self, user_id: int, payload: PushSubscriptionIn, *, session_id: int):
        """Confirm only the exact current binding; never rebind on an ACK.

        An obsolete ACK after logout/account switch cannot move the endpoint.
        Returns None for a missing binding, otherwise (job IDs, OA keys, changed).
        """
        match = (PushSubscription.user_id == user_id,
                 PushSubscription.session_id == session_id,
                 PushSubscription.endpoint == payload.endpoint,
                 PushSubscription.p256dh == payload.keys.p256dh,
                 PushSubscription.auth == payload.keys.auth)
        changed = (await self.db.execute(update(PushSubscription).where(
            *match, PushSubscription.client_ready.is_not(True),
        ).values(client_ready=True).returning(PushSubscription.id))).scalar_one_or_none()
        if changed is None:
            exists = await self.db.scalar(select(PushSubscription.id).where(
                *match, PushSubscription.client_ready.is_(True)))
            await self.db.commit()
            return ([], [], False) if exists is not None else None
        await self.db.commit()
        # The readiness flag is durable even if the queue hint fails. The
        # normal scheduler will still find eligible devices after a restart.
        from app.services.push_dispatch import wake_waiting_jobs
        try:
            jobs, oa_keys = await wake_waiting_jobs(self.db, user_id, ready=True)
            await self.db.commit()
            return jobs, oa_keys, True
        except Exception as exc:
            await self.db.rollback()
            logger.warning("Ready push wake failed (user_id=%s): %s", user_id, type(exc).__name__)
            return [], [], True

    async def remove_subscription(self, endpoint: str, user_id: int | None = None) -> None:
        """اشتراک با endpoint داده‌شده را (در صورت وجود) حذف می‌کند؛ با user_id فقط اگر متعلق به همان کاربر باشد."""
        query = select(PushSubscription).where(PushSubscription.endpoint == endpoint)
        if user_id is not None:
            query = query.where(PushSubscription.user_id == user_id)
        result = await self.db.execute(query)
        sub = result.scalar_one_or_none()
        if sub is not None:
            await self.db.delete(sub)
            await self.db.commit()

    async def notify_users(
        self,
        user_ids: set[int],
        url: str = "/notices",
        priority: str = "normal",
        notice_type: str = "normal",
        body: str | None = None,
        return_stats: bool = False,
        subscription_ids: set[int] | None = None,
        notification_key: str | None = None,
        session_bindings: dict[int, int] | None = None,
        ttl_seconds: int = 24 * 3600,
    ) -> dict | None:
        """
        به همه دستگاه‌های کاربران user_ids یک اعلان Push می‌فرستد (موازی، حداکثر ۲۰ هم‌زمان).
        ورودی: آدرس مقصد کلیک، اولویت، نوع اطلاعیه و متن اختیاری body؛ اگر body داده نشود،
        متن پیش‌فرض «اطلاعیه جدید» استفاده می‌شود. اشتراک‌های منقضی (404/410) حذف می‌شوند.
        """
        if not user_ids:
            logger.info("Push skipped: no target users")
            return {"attempted": 0, "sent": 0, "failed": 0, "stale": 0, "results": []} if return_stats else None
        # Existing non-statistical callers enqueue instead of waiting on provider I/O.
        # OA and the durable dispatch worker explicitly request delivery stats.
        if not return_stats:
            from app.services.push_dispatch import enqueue_generic_push
            await enqueue_generic_push(user_ids, url, body, priority, notice_type, key=notification_key)
            return None
        stmt = eligible_subscriptions(user_ids)
        if subscription_ids is not None:
            stmt = stmt.where(PushSubscription.id.in_(subscription_ids))
        if session_bindings is not None:
            stmt = stmt.where(tuple_(PushSubscription.id, PushSubscription.session_id).in_(list(session_bindings.items())))
        subscription_rows = (await self.db.execute(stmt)).all()
        subscriptions = [row[0] for row in subscription_rows]
        marker_by_subscription = {row[0].id: row[1] for row in subscription_rows}
        if not subscriptions:
            logger.info("Push skipped: no eligible session-bound subscriptions (target_users=%s)", len(user_ids))
            return {"attempted": 0, "sent": 0, "failed": 0, "stale": 0, "results": []} if return_stats else None

        # نام و نام‌خانوادگی هرکدام از مخاطبان (برای شخصی‌سازی متن اعلان) —
        # کاربران مدیریتی محض (بدون employee_id، مثل admin) در این نگاشت
        # نیستند و همان متن عمومی اطلاعیه را بدون خطاب شخصی می‌گیرند.
        name_result = await self.db.execute(
            select(User.id, Employee.first_name, Employee.last_name)
            .join(Employee, Employee.id == User.employee_id)
            .where(User.id.in_(user_ids))
        )
        name_by_user_id = {row[0]: f"{row[1]} {row[2]}" for row in name_result.all()}

        # صرف‌نظر از اولویت اطلاعیه، Urgency همیشه high فرستاده می‌شود تا FCM
        # حتی در حالت Doze/کم‌مصرف گوشی هم آن را فوری (بدون Batch) تحویل بدهد.

        # ارسال‌ها با asyncio.gather به‌صورت موازی انجام می‌شوند و یک Semaphore
        # تعداد ارسال هم‌زمان را به ۲۰ محدود می‌کند تا فشار روی سرویس Push/شبکه
        # کنترل شود؛ به این ترتیب ارسال به صدها گیرنده از Timeout درخواست HTTP عبور نمی‌کند.
        # متن پیش‌فرض اعلان اطلاعیه (قابل‌ویرایش در «متن اعلان‌ها»ی اطلاعیه‌ها؛ جدا برای فیش حقوقی/کارکرد)
        default_body = None
        if not body:
            key = {"payroll": "notices.payroll", "attendance_card": "notices.attendance_card"}.get(
                notice_type, "notices.new"
            )
            default_body = await notification_templates.render(self.db, None, key)
        sent_count = 0
        failed_count = 0
        stale_rows: list[PushSubscription] = []  # شناسه اشتراک‌های منقضی برای حذف
        delivery_results: list[dict] = []  # subscription IDs only, never endpoints/keys
        semaphore = asyncio.Semaphore(20)

        async def send_one(sub: PushSubscription) -> None:
            """اعلان را برای یک اشتراک می‌سازد و ارسال می‌کند و شمارنده‌های نتیجه را به‌روز می‌کند."""
            nonlocal sent_count, failed_count
            recipient_name = name_by_user_id.get(sub.user_id)
            # عنوان/متن واقعی اطلاعیه در اعلان نمایش داده نمی‌شود؛ یک پیام
            # استاندارد و ثابت که فقط با نام مخاطب شخصی‌سازی می‌شود.
            notification_title = f"{recipient_name} عزیز،" if recipient_name else "پرتال سازمانی"
            notification_body = body or default_body
            payload = bounded_payload(
                {
                    "title": notification_title,
                    "body": notification_body,
                    "url": url,
                    "priority": priority,
                    "notice_type": notice_type,
                    # Not a credential: device-session correlation so a delayed
                    # Push from a previous login cannot appear after account switch.
                    "session_marker": marker_by_subscription[sub.id],
                    **({"receipt_token": issue_receipt(notification_key, sub)} if session_bindings and notification_key else {}),
                    **({"notification_key": notification_key} if notification_key else {}),
                }
            )
            target = sub
            inbox_id = None
            if getattr(sub, "native_device_id", None) is not None:
                from app.services.android_delivery import offer, finish_web
                decision, fallback = await offer(sub, json.loads(payload), ttl_seconds)
                if decision in ("accepted", "queued"):
                    sent_count += 1
                    delivery_results.append({"id": sub.id, "status": "sent"})
                    return
                if fallback is None:
                    failed_count += 1
                    delivery_results.append({"id": sub.id, "status": "failed", "error": "awaiting_native_receipt"})
                    return
                inbox_id, target = decision, fallback
                payload = bounded_payload({**json.loads(payload), "android_fallback": True})
            if not valid_push_endpoint(target.endpoint) or not settings.VAPID_PRIVATE_KEY:
                if inbox_id:
                    await finish_web(inbox_id, False)
                failed_count += 1
                delivery_results.append({"id": sub.id, "status": "failed", "error": "web_transport_unavailable"})
                return
            delivered_web = False
            async with semaphore:
                try:
                    # خودِ webpush() یک تابع مسدودکننده (Blocking) است — با
                    # asyncio.to_thread در یک Thread جدا اجرا می‌شود تا
                    # Event Loop اصلی را برای بقیه درخواست‌های هم‌زمان سرور
                    # مسدود نکند.
                    await asyncio.to_thread(
                        send_webpush,
                        subscription_info={
                            "endpoint": target.endpoint,
                            "keys": {"p256dh": target.p256dh, "auth": target.auth},
                        },
                        data=payload,
                        vapid_private_key=settings.VAPID_PRIVATE_KEY,
                        vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}"},
                        # TTL is bounded by the remaining lifetime of the event.
                        ttl=max(0, min(int(ttl_seconds), MAX_TTL_SECONDS)),
                        headers={"Urgency": "high"},
                        timeout=15,  # سرور Push کند/در دسترس نیست → بقیه‌ی گیرندگان معطل نمانند
                    )
                    delivered_web = True
                    sent_count += 1
                    delivery_results.append({"id": sub.id, "status": "sent"})
                except WebPushException as e:
                    status_code = getattr(getattr(e, "response", None), "status_code", None)
                    if status_code in (404, 410):
                        # اشتراک منقضی/لغوشده در مرورگر — از دیتابیس پاک می‌شود
                        stale_rows.append(target)
                        delivery_results.append({"id": sub.id, "status": "failed" if inbox_id else "stale"})
                    else:
                        failed_count += 1
                        permanent = status_code in (400, 405, 413, 422) or (status_code is not None and 300 <= status_code < 400)
                        response = getattr(e, "response", None)
                        retry_after = provider_retry_after(response)
                        delivery_results.append({"id": sub.id, "status": "permanent" if permanent else "failed",
                            "error": f"http_{status_code}" if status_code else "provider_error",
                            **({"retry_after": retry_after} if retry_after is not None else {})})
                        logger.warning(
                            "ارسال Push ناموفق (user_id=%s, subscription_id=%s, status=%s): %s",
                            sub.user_id, sub.id, status_code, type(e).__name__,
                        )
                except Exception as e:  # noqa: BLE001
                    # خطای شبکه (DNS، قطع اتصال، Timeout) برای یک دستگاه: فقط همان دستگاه ناموفق شمرده می‌شود.
                    # قبلاً این خطا کل ارسال را با «خطای سرور» متوقف می‌کرد و پاک‌سازی اشتراک‌های منقضی و لاگ خلاصه
                    # اجرا نمی‌شد. اشتراک حذف نمی‌شود چون مشکل از شبکه‌ی سرور است، نه از دستگاه.
                    failed_count += 1
                    delivery_results.append({"id": sub.id, "status": "failed", "error": "network_or_transport_error"})
                    host = sub.endpoint.split("/")[2] if sub.endpoint.count("/") >= 2 else "?"
                    logger.warning(
                        "ارسال Push ناموفق (user_id=%s, subscription_id=%s, provider=%s): %s",
                        sub.user_id,
                        sub.id,
                        host,
                        type(e).__name__,
                    )

                finally:
                    if inbox_id:
                        await finish_web(inbox_id, delivered_web)

        await asyncio.gather(*(send_one(sub) for sub in subscriptions))

        # حذف اشتراک‌های منقضی از دیتابیس
        if stale_rows:
            # A concurrent re-registration may already have rebound this endpoint.
            # Delete only the exact registration that the provider rejected.
            await self.db.execute(delete(PushSubscription).where(or_(*[
                and_(PushSubscription.id == sub.id,
                     PushSubscription.session_id == sub.session_id,
                     PushSubscription.user_id == sub.user_id,
                     PushSubscription.p256dh == sub.p256dh,
                     PushSubscription.auth == sub.auth)
                for sub in stale_rows
            ])).execution_options(synchronize_session=False))
            await self.db.commit()

        # خلاصه نتیجه ارسال همیشه (حتی در موفقیت کامل) لاگ می‌شود تا هر
        # ارسال یک خط قابل‌جستجو در لاگ داشته باشد.
        logger.info(
            "ارسال Push اطلاعیه به %s مخاطب هدف: %s موفق، %s ناموفق، %s اشتراک منقضی حذف شد",
            len(user_ids),
            sent_count,
            failed_count,
            len(stale_rows),
        )
        if return_stats:
            return {"attempted": len(subscriptions), "sent": sent_count,
                    "failed": failed_count, "stale": len(stale_rows), "results": delivery_results,
                    "session_bindings": {sub.id: getattr(sub, "session_id", None) for sub in subscriptions}}
