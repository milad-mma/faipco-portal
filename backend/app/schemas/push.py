"""Schema های Pydantic برای اشتراک Web Push (دقیقاً همان ساختاری که PushSubscription.toJSON() مرورگر می‌دهد)."""
from pydantic import BaseModel


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys


class UnsubscribeIn(BaseModel):
    endpoint: str
