"""Schema های Pydantic برای مدیریت واحدهای سازمانی (Department): ایجاد، نمایش و انتصاب سرپرست."""
from pydantic import BaseModel, ConfigDict


class DepartmentCreate(BaseModel):
    """ورودی POST /departments برای ایجاد واحد سازمانی."""

    site_id: int
    name: str
    code: str


class DepartmentOut(BaseModel):
    """خروجی واحد سازمانی در Endpoint های /departments، همراه نام سرپرست."""

    id: int
    site_id: int
    name: str
    code: str
    supervisor_user_id: int | None
    supervisor_name: str | None = None  # نام و نام خانوادگی واقعی سرپرست (نه Username)


class AssignSupervisorIn(BaseModel):
    """ورودی PUT /departments/{id}/supervisor."""

    employee_id: int | None  # None یعنی حذف سرپرست فعلی؛ در غیر این صورت شناسه پرسنل (نه User)
