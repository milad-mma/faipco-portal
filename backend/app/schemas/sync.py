"""
Schema های Pydantic برای Sync Management: نتیجه تست اتصال، تاریخچه اجراها،
تنظیم فاصله اجرای خودکار و خلاصه وضعیت امروز.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.sync_log import SyncRunStatus


class TestConnectionResult(BaseModel):
    """خروجی POST /sync/{site_id}/test-connection."""

    success: bool
    message: str | None = None


class SyncLogOut(BaseModel):
    """خروجی یک اجرای Sync در POST /sync/{site_id}/run و GET /sync/{site_id}/logs."""

    id: int
    site_id: int
    started_at: datetime
    finished_at: datetime | None
    status: SyncRunStatus
    inserted_count: int
    updated_count: int
    deactivated_count: int
    skipped_inactive_count: int = 0
    skipped_unassigned_count: int = 0  # پرسنلی که واحدشان زیر هیچ واحد ریشه‌ای نیست
    transferred_count: int = 0  # پرسنل منتقل‌شده از سایت هم‌منبع دیگر
    warning_message: str | None = None
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)


class SyncSettingsOut(BaseModel):
    """خروجی GET/PUT /sync/settings: فاصله اجرای خودکار و زمان آخرین اجرای خودکار."""

    interval_minutes: int
    last_auto_sync_at: datetime | None = None


class SyncSettingsUpdate(BaseModel):
    """ورودی PUT /sync/settings برای تغییر فاصله اجرای خودکار Sync."""

    interval_minutes: int = Field(ge=1, le=1440, description="فاصله زمانی اجرای خودکار Sync، بر حسب دقیقه (۱ تا ۱۴۴۰)")


class SyncStatusSummaryOut(BaseModel):
    """خروجی GET /sync/status-summary: خلاصه وضعیت Sync امروز برای کارت آمار داشبورد Admin."""

    total_sites: int
    success_today: int
    failed_today: int
    not_run_today: int
