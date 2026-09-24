"""Schema های Pydantic برای اشتراک Web Push (همان ساختاری که PushSubscription.toJSON() مرورگر می‌دهد)؛ مورد استفاده در endpointهای /push."""
from pydantic import BaseModel


class PushSubscriptionKeys(BaseModel):
    """کلیدهای رمزنگاری اشتراک (بخشی از PushSubscriptionIn)."""
    p256dh: str
    auth: str


class PushSubscriptionIn(BaseModel):
    """ورودی POST /push/subscribe برای ثبت اشتراک یک دستگاه."""
    endpoint: str
    keys: PushSubscriptionKeys


class UnsubscribeIn(BaseModel):
    """ورودی POST /push/unsubscribe برای حذف اشتراک یک دستگاه."""
    endpoint: str
