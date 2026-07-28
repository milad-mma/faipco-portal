"""Schema های Pydantic مربوط به User."""
from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    id: int
    username: str
    email: str | None
    is_active: bool
    is_superuser: bool

    model_config = ConfigDict(from_attributes=True)
