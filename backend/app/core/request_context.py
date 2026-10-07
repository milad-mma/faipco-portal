"""
مقادیر درخواست جاری که لایه‌های پایین‌تر (بدون دسترسی به Request) لازم دارند؛ با ContextVar و یک
Middleware در main.py پر می‌شوند و برای هر درخواست جدا هستند.

- user_agent: برای تشخیص گوشی اندروید در پیش‌نیاز «اپ اندروید با دسترسی موقعیت» (access_gate_service).
- client_app: هدر X-Client-App که پرتال داخل اپ اندروید می‌فرستد (فقط اطلاعاتی، نه امنیتی).
"""
from contextvars import ContextVar

current_user_agent: ContextVar[str] = ContextVar("current_user_agent", default="")
current_client_app: ContextVar[str] = ContextVar("current_client_app", default="")
# برای گزارش خطاها (error_log_service): کد پیگیری، درخواست، IP و کاربر درخواست جاری.
# asyncio.to_thread این مقادیر را به Thread هم می‌برد، پس خطای کاراوب داخل Thread هم با همین درخواست ثبت می‌شود.
current_request_id: ContextVar[str] = ContextVar("current_request_id", default="")
current_request_label: ContextVar[str] = ContextVar("current_request_label", default="")
current_client_ip: ContextVar[str] = ContextVar("current_client_ip", default="")
current_user_ref: ContextVar[tuple[int, str] | None] = ContextVar("current_user_ref", default=None)


def is_android_user_agent(user_agent: str | None) -> bool:
    """مرورگر یا اپ روی گوشی/تبلت اندروید؟ (حالت دسکتاپ Chrome اندروید، Android را در UA ندارد)"""
    return "android" in (user_agent or "").lower()
