# معماری FAIPCO Portal

## دلایل انتخاب تکنولوژی

### Backend: FastAPI
- عملکرد بالا (بر پایه Starlette + Pydantic)
- تولید خودکار مستندات API (Swagger/ReDoc) — برای پروژه‌ای که قراره به مشتریان مختلف تحویل داده بشه، مستندسازی خودکار API حیاتی است
- پشتیبانی native از Async — برای Sync Engine که هم‌زمان به چند دیتابیس خارجی وصل می‌شود، ضروری است
- Type Hinting کامل → کمتر باگ در مراحل توسعه توسط دستیارهای کد

### Frontend: React
- بازار کار و اکوسیستم بزرگ‌تر نسبت به Vue برای پروژه‌های Enterprise بلندمدت
- کتابخانه MUI (Material UI) پشتیبانی رسمی و پایدار از RTL دارد — برای پنل مدیریت فارسی مناسب‌تر است
- سازگاری بهتر با کتابخانه‌های Table/Grid پیشرفته (مثل AG Grid) که برای نمایش هزاران رکورد پرسنل لازم است

### دیتابیس اصلی: PostgreSQL
- Open Source، پایدار، مناسب Enterprise
- پشتیبانی خوب از JSON برای ذخیره Mapping های پویا

## الگوی لایه‌بندی Backend

```
Request → API (Router) → Service (منطق تجاری) → Repository (دسترسی داده) → Model (ORM) → DB
```

- **API Layer**: فقط اعتبارسنجی ورودی و فراخوانی Service. منطق تجاری اینجا نباید باشد.
- **Service Layer**: قوانین کسب‌وکار (مثلاً: "کاربر فقط می‌تواند اطلاعیه‌های Site خودش را ببیند")
- **Repository Layer**: کوئری‌های دیتابیس، جدا از منطق تجاری تا تست‌پذیر باشد

## Sync Engine — طراحی Plugin-based

هر نوع دیتابیس (SQL Server، MySQL، PostgreSQL و ...) یک Adapter مجزا در
`backend/app/sync_engine/adapters/` دارد که یک اینترفیس مشترک را پیاده‌سازی می‌کند:

```python
class BaseSiteAdapter:
    async def test_connection(self) -> bool: ...
    async def fetch_employees(self, mapping: EmployeeMapping) -> list[dict]: ...
```

اضافه کردن دیتابیس جدید (مثلاً Oracle) = ساخت یک Adapter جدید، بدون تغییر در Core.

Sync Service این مراحل را برای هر Site اجرا می‌کند:
1. خواندن `site_connections` برای گرفتن اطلاعات اتصال (رمزگشایی پسورد)
2. خواندن `employee_mappings` برای فهمیدن نام جدول/ستون‌های آن Site
3. فراخوانی Adapter مناسب برای خواندن داده خام
4. تطبیق (Map) داده خام به مدل داخلی `Employee`
5. Insert/Update/Deactivate در جدول داخلی `employees`
6. ثبت لاگ نتیجه Sync (موفق/خطا) برای نمایش در پنل Sync Management

## امنیت

- پسورد کاربران: bcrypt (یک‌طرفه)
- Credential دیتابیس سایت‌ها: Fernet (AES) — دوطرفه، چون Sync Engine باید بتواند آن را بخواند
- JWT با Access Token کوتاه‌مدت + Refresh Token
- تمام کلیدها از Environment Variables خوانده می‌شوند، هرگز در کد نیستند

## نقشه راه توسعه

جزئیات هر مرحله در README.md اصلی پروژه آمده است.

## پشته فناوری

| لایه | تکنولوژی |
|---|---|
| Backend | FastAPI (Async) + SQLAlchemy 2 (Async) + Alembic |
| دیتابیس اصلی Portal | PostgreSQL |
| Auth | JWT (Access + Refresh با Sliding Window) |
| Scheduler | APScheduler (Sync خودکار پرسنل) |
| Frontend | React + MUI (RTL کامل با `stylis-plugin-rtl`) + Vite |
| Push | Web Push (VAPID) |
| PDF (فیش حقوقی) | ReportLab + arabic-reshaper + python-bidi |
| XLSX (فیش حقوقی) | openpyxl |
| Web Server تولید | Nginx (Reverse Proxy + Serve فایل‌های Frontend) |

