"""
مقادیر درخواست جاری که لایه‌های پایین‌تر (بدون دسترسی به Request) لازم دارند؛ با ContextVar و یک
Middleware در main.py پر می‌شوند و برای هر درخواست جدا هستند.

- user_agent: برای تشخیص گوشی اندروید در پیش‌نیاز «اپ اندروید با دسترسی موقعیت» (access_gate_service).
- client_app: هدر X-Client-App که پرتال داخل اپ اندروید می‌فرستد (فقط اطلاعاتی، نه امنیتی).
"""
from contextvars import ContextVar

current_user_agent: ContextVar[str] = ContextVar("current_user_agent", default="")
current_client_app: ContextVar[str] = ContextVar("current_client_app", default="")


def is_android_user_agent(user_agent: str | None) -> bool:
    """مرورگر یا اپ روی گوشی/تبلت اندروید؟ (حالت دسکتاپ Chrome اندروید، Android را در UA ندارد)"""
    return "android" in (user_agent or "").lower()
