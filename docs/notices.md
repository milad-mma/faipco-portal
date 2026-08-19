# سیستم اطلاعیه

## ساخت و ارسال

```bash
curl -X POST http://localhost:8000/api/v1/notices \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "title": "اطلاعیه تعطیلی", "body": "روز پنج‌شنبه تعطیل است.", "priority": "high",
    "targets": [{"target_type": "site", "target_id": 1}, {"target_type": "role", "target_id": 1}]
  }'

curl -X POST http://localhost:8000/api/v1/notices/1/publish -H "Authorization: Bearer $TOKEN"
```

ساخت (`POST /notices`) فقط پیش‌نویس می‌سازد — تا وقتی `/publish` صدا زده
نشود، به هیچ‌کس نمایش داده و Push هم فرستاده نمی‌شود. `/publish` تابع
[محدودیت ارسال پیاپی](rate-limiting.md) است؛ ساخت پیش‌نویس محدود نیست.

## دریافت اطلاعیه‌ها

```bash
curl http://localhost:8000/api/v1/notices/me -H "Authorization: Bearer $TOKEN"
```

`/notices/me` هوشمند است: بر اساس Site/Department/نقش‌های کاربر، فقط اطلاعیه‌های
واقعاً مرتبط را برمی‌گرداند — دقیقاً طبق طراحی `notice_targets`
(all / site / department / role / employee).

## گزارش‌ها

```bash
curl "http://localhost:8000/api/v1/notices/sent-by-me?page=1&page_size=10" -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/api/v1/notices/admin-report?page=1&page_size=10" -H "Authorization: Bearer $TOKEN"
```

- `/sent-by-me`: فقط اطلاعیه‌هایی که خودِ کاربر جاری فرستاده — همه کاربرانی
  که مجوز ارسال دارند می‌بینند.
- `/admin-report`: همه اطلاعیه‌های کل سیستم (نیازمند `notices.view`) — چه
  کسی، چه زمانی، برای چه کسانی فرستاده و چند نفر دیده‌اند. روی موبایل به‌صورت
  کارتی (بدون اسکرول افقی) نمایش داده می‌شود، روی دسکتاپ جدول کامل.

## حذف اطلاعیه

حذف همیشه **Soft-Delete** است:

```bash
curl -X DELETE http://localhost:8000/api/v1/notices/1 -H "Authorization: Bearer $TOKEN"
```

- بلافاصله از پنل همه‌ی کسانی که اطلاعیه را دریافت کرده بودند کنار می‌رود.
- رکورد فیزیکی هرگز پاک نمی‌شود — در گزارش‌های بالا با برچسب «حذف شده»
  باقی می‌ماند (تا آمار بازدید از دست نرود).
- فقط خودِ فرستنده یا Admin اجازه حذف دارند.

## اطلاعیه فیش حقوقی و فیش کارکرد

این دو مسیر ارسال، ساختار متفاوتی دارند (بدون انتخاب دستی Target — مخاطبان
از روی فایل آپلودی تعیین می‌شوند). جزئیات کامل در
[`docs/payroll-notices.md`](payroll-notices.md).
