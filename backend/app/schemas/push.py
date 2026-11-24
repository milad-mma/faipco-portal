"""Browser Web Push subscription input; validate before storing network destinations."""
from pydantic import BaseModel, Field, field_validator
from app.core.push_endpoint_policy import (
    MAX_ENDPOINT_LENGTH, valid_push_endpoint, validate_public_key, validate_auth_key,
)


class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=80, max_length=100)
    auth: str = Field(min_length=20, max_length=32)

    @field_validator("p256dh")
    @classmethod
    def public_key(cls, value):
        return validate_public_key(value)

    @field_validator("auth")
    @classmethod
    def auth_key(cls, value):
        return validate_auth_key(value)


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(min_length=1, max_length=MAX_ENDPOINT_LENGTH)
    keys: PushSubscriptionKeys
    session_marker: str | None = Field(default=None, max_length=128)

    @field_validator("endpoint")
    @classmethod
    def provider(cls, value):
        if not valid_push_endpoint(value):
            raise ValueError("Unapproved Web Push provider")
        return value


class UnsubscribeIn(BaseModel):
    endpoint: str = Field(min_length=1, max_length=MAX_ENDPOINT_LENGTH)
