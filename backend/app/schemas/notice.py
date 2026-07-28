"""Schema های Pydantic برای سیستم اطلاعیه سازمانی."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.notice import NoticePriority, NoticeStatus, NoticeTargetType


class NoticeTargetIn(BaseModel):
    target_type: NoticeTargetType
    # برای target_type == "all" باید None باشد؛ در غیر این‌صورت شناسه Site/Department/Role/Employee مقصد
    target_id: int | None = None

    @model_validator(mode="after")
    def validate_target_id(self) -> "NoticeTargetIn":
        if self.target_type == NoticeTargetType.all and self.target_id is not None:
            raise ValueError("برای مخاطب 'all' نباید target_id مقداردهی شود")
        if self.target_type != NoticeTargetType.all and self.target_id is None:
            raise ValueError("برای این نوع مخاطب، target_id الزامی است")
        return self


class NoticeTargetOut(BaseModel):
    target_type: NoticeTargetType
    target_id: int | None

    model_config = ConfigDict(from_attributes=True)


class NoticeCreate(BaseModel):
    title: str
    body: str
    priority: NoticePriority = NoticePriority.normal
    publish_at: datetime | None = None
    expire_at: datetime | None = None
    targets: list[NoticeTargetIn]

    @model_validator(mode="after")
    def validate_targets(self) -> "NoticeCreate":
        if not self.targets:
            raise ValueError("حداقل یک مخاطب برای اطلاعیه الزامی است")
        return self


class NoticeOut(BaseModel):
    id: int
    sender_id: int
    title: str
    body: str
    priority: NoticePriority
    status: NoticeStatus
    publish_at: datetime | None
    expire_at: datetime | None
    created_at: datetime
    targets: list[NoticeTargetOut]

    model_config = ConfigDict(from_attributes=True)
