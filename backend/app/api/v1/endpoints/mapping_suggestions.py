"""
Endpoint «پیشنهاد نگاشت بر اساس نام ستون» برای فرم نگاشت داینامیک سایت.

هیچ اتصال دیتابیسی برقرار نمی‌کند و هیچ داده‌ای نمی‌خواند؛ فقط یک
الگوریتم خالص روی نام ستون‌هایی که Frontend از مرحله کشف ساختار
در اختیار دارد اجرا می‌کند. برای همین به site_id نیازی ندارد.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import require_permission
from app.services.mapping_suggestion_service import suggest_mapping

router = APIRouter()


class MappingSuggestionRequest(BaseModel):
    """بدنه درخواست پیشنهاد نگاشت: فهرست نام ستون‌های جدول منبع و فهرست مفهوم‌های موردنیاز."""

    columns: list[str]
    concepts: list[str]


@router.post("")
async def suggest_column_mapping(
    payload: MappingSuggestionRequest,
    _user=Depends(require_permission("sites.manage")),
):
    """
    برای هر مفهوم درخواستی (مثلاً "personnel_code"، "email"، "date"،
    "enter_date"، ...)، بهترین ستون کاندید از بین نام ستون‌های داده‌شده
    را پیشنهاد می‌دهد - یا null اگر هیچ‌کدام هم‌خوانی معناداری نداشتند.
    فقط یک پیشنهاد است؛ تأیید نهایی همیشه دستی و توسط مدیر است.
    خروجی: دیکشنری {مفهوم: جزئیات ستون پیشنهادی یا null}. مجوز لازم: sites.manage.
    """
    return suggest_mapping(payload.columns, payload.concepts)
