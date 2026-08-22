# راه‌اندازی Sync Engine


```bash
TOKEN="<access_token از /auth/login>"

# ۱. ساخت Site
curl -X POST http://localhost:8000/api/v1/sites \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "کارخانه ۱", "code": "SITE1"}'

# ۲. تعریف اتصال دیتابیس مبدأ (پسورد خودکار رمزنگاری و ذخیره می‌شود)
curl -X PUT http://localhost:8000/api/v1/sites/1/connection \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "db_type": "mssql", "host": "192.168.1.10", "port": 1433,
    "database_name": "HRDB", "username": "sa", "password": "SourceDbPass123"
  }'

# ۳. تعریف Mapping ستون‌ها (طبق ساختار واقعی جدول در آن Site)
curl -X PUT http://localhost:8000/api/v1/sites/1/mapping \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "table_name": "Personnel", "personnel_code_column": "Code",
    "national_code_column": "NationalID", "first_name_column": "Name",
    "last_name_column": "Family", "mobile_column": "Phone"
  }'

# ۴. تست اتصال، سپس اجرای دستی Sync
curl -X POST http://localhost:8000/api/v1/sync/1/test-connection -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/api/v1/sync/1/run -H "Authorization: Bearer $TOKEN"

# ۵. مشاهده تاریخچه Sync
curl http://localhost:8000/api/v1/sync/1/logs -H "Authorization: Bearer $TOKEN"
```

برای سایتی که ستون‌هایش فرق دارد (مثلاً `employees`, `personnel_code`,
`national_code`, ...)، کافی است در مرحله ۳ مقادیر متفاوتی برای Mapping بفرستید —
**هیچ خط کدی تغییر نمی‌کند**.

### فاصله زمانی اجرای خودکار Sync

پیش‌فرض هر ۳۰ دقیقه (`SYNC_INTERVAL_MINUTES` در `.env`)، ولی از داخل پنل هم
قابل تغییر است — بدون نیاز به Restart سرور:

```bash
curl -X GET http://localhost:8000/api/v1/sync/settings -H "Authorization: Bearer $TOKEN"
curl -X PUT http://localhost:8000/api/v1/sync/settings \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"interval_minutes": 15}'
```

مقدار جدید در دیتابیس (`system_settings`) ذخیره می‌شود (پس بعد از Restart هم
باقی می‌ماند). اگر `SYNC_ENABLED=false` باشد، Sync خودکار اصلاً اجرا
نمی‌شود (اجرای دستی از پنل همچنان کار می‌کند).

⚠️ **رفع یک باگ واقعی (۲۰۲۶-۰۸)**: نسخه قبلی این پروژه، فاصله زمانی جدید
را مستقیم روی Job زمان‌بندی‌شده اعمال می‌کرد (`scheduler.reschedule_job`).
چون سرویس با ۲ Worker جدا (`uvicorn --workers 2`) اجرا می‌شود و هرکدام یک
نسخه کاملاً مستقل از APScheduler دارد، این Reschedule فقط روی همان
Worker ای که درخواست HTTP را گرفته بود اعمال می‌شد — Worker دیگر با فاصله
زمانی قدیمی (از آخرین Startup) کار می‌کرد. نتیجه: رفتار غیرقابل‌پیش‌بینی،
مخصوصاً روی فاصله‌های بزرگ (مثلاً کاربری که ۷۲۰ دقیقه تنظیم کرده بود، هر
~۷۲ دقیقه Sync می‌دید؛ روی ۱۴۴۰ دقیقه اصلاً کار نمی‌کرد).

**رفع فعلی**: به‌جای Reschedule کردن Job، هر Worker هر ۱ دقیقه
(`SYNC_CHECK_INTERVAL_MINUTES` در `backend/app/core/scheduler.py`) یک چک
سبک می‌زند: «طبق فاصله زمانی و آخرین Sync موفق (هر دو مستقیم از دیتابیس،
نه حافظه محلی هر Worker)، الان وقتش رسیده یا نه؟». چون این تصمیم از یک
منبع مشترک خوانده می‌شود، همه Worker ها همیشه هماهنگ‌اند — بدون نیاز به
هیچ Reschedule ای. دقت واقعی زمان‌بندی حالا ±۱ دقیقه است (نه لحظه‌به‌لحظه)،
که برای این کاربرد کاملاً کافی است.

پنل «همگام‌سازی دیتابیس» زمان **«آخرین Sync خودکار»** را هم نشان می‌دهد —
مستقیم از همین مکانیزم — تا بشود بدون حدس زدن تأیید کرد که واقعاً طبق
فاصله تنظیم‌شده اجرا می‌شود.
