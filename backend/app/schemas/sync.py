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


class SyncSettingsUpdate(BaseModel):
    interval_minutes: int = Field(ge=1, le=1440, description="فاصله زمانی اجرای خودکار Sync، بر حسب دقیقه (۱ تا ۱۴۴۰)")
