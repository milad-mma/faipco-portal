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

مقدار جدید هم در دیتابیس (`system_settings`) ذخیره می‌شود (پس بعد از Restart هم
باقی می‌ماند) و هم بلافاصله روی Job در حال اجرا اعمال می‌شود. اگر `SYNC_ENABLED=false`
باشد، Sync خودکار اصلاً اجرا نمی‌شود (اجرای دستی از پنل همچنان کار می‌کند).
