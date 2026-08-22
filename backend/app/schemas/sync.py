"""Schema های Pydantic برای Sync Management."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.sync_log import SyncRunStatus


class TestConnectionResult(BaseModel):
    success: bool
    message: str | None = None


class SyncLogOut(BaseModel):
    id: int
    site_id: int
    started_at: datetime
    finished_at: datetime | None
    status: SyncRunStatus
    inserted_count: int
    updated_count: int
    deactivated_count: int
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)


class SyncSettingsOut(BaseModel):
    interval_minutes: int
    last_auto_sync_at: datetime | None = None


class SyncSettingsUpdate(BaseModel):
    interval_minutes: int = Field(ge=1, le=1440, description="فاصله زمانی اجرای خودکار Sync، بر حسب دقیقه (۱ تا ۱۴۴۰)")


class SyncStatusSummaryOut(BaseModel):
    """خلاصه وضعیت Sync امروز، برای کارت آمار داشبورد Admin."""

    total_sites: int
    success_today: int
    failed_today: int
    not_run_today: int
