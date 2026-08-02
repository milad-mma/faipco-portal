"""Schema های Pydantic برای مدیریت واحدهای سازمانی (Department)."""
from pydantic import BaseModel, ConfigDict


class DepartmentCreate(BaseModel):
    site_id: int
    name: str
    code: str


class DepartmentOut(BaseModel):
    id: int
    site_id: int
    name: str
    code: str
    supervisor_user_id: int | None
    supervisor_name: str | None = None  # نام و نام خانوادگی واقعی سرپرست (نه Username)


class AssignSupervisorIn(BaseModel):
    employee_id: int | None  # None یعنی حذف سرپرست فعلی؛ در غیر این صورت شناسه پرسنل (نه User)
