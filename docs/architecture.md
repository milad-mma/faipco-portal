# معماری FAIPCO Portal

## دلایل انتخاب تکنولوژی

### Backend: FastAPI
- عملکرد بالا (بر پایه Starlette + Pydantic)
- تولید خودکار مستندات API (Swagger/ReDoc) — فقط وقتی `DEBUG=true` است
  (`/api/docs`، `/api/redoc`)؛ روی Production خاموش است
- پشتیبانی native از Async — برای Sync Engine که هم‌زمان به چند دیتابیس خارجی وصل می‌شود، و برای WebSocket حضور آنلاین
- Type Hinting کامل → کمتر باگ در مراحل توسعه توسط دستیارهای کد

### Frontend: React
- اکوسیستم بزرگ و مناسب پروژه‌های Enterprise بلندمدت
- کتابخانه MUI (Material UI) پشتیبانی رسمی و پایدار از RTL دارد — برای پنل فارسی مناسب است
- Build با Vite و PWA با `vite-plugin-pwa` (استراتژی injectManifest)

### دیتابیس اصلی: PostgreSQL
- Open Source، پایدار، مناسب Enterprise
- پشتیبانی خوب از JSON برای ذخیره Mapping های پویا
- Advisory Lock برای جلوگیری از اجرای تکراری Job های زمان‌بندی‌شده بین Worker ها

## الگوی لایه‌بندی Backend

```
Request → API (Router) → Service (منطق تجاری) → Model (ORM) → DB
```

- **API Layer** (`app/api/v1/endpoints/`): اعتبارسنجی ورودی (Pydantic در `app/schemas/`)،
  بررسی مجوز با Dependency ها (`app/core/deps.py`، `site_permission_deps.py`) و فراخوانی Service.
- **Service Layer** (`app/services/`): قوانین کسب‌وکار (مثلاً «کاربر فقط اطلاعیه‌های مخاطب خودش را می‌بیند»).
  بیشتر Service ها مستقیماً با SQLAlchemy Async کوئری می‌زنند؛ لایه Repository جداگانه فقط برای
  User/Employee وجود دارد (`app/repositories/user_repository.py`).
- **Core** (`app/core/`): منطق‌های خالص و قابل‌تست (مثل `leave_request_rules`، `evaluation_rules`،
  `backup_schedule_logic`، `profanity_filter`، `persian_date`) + امنیت، Rate Limit، IP Allowlist و Scheduler.

## Sync Engine — طراحی Plugin-based

هر نوع دیتابیس (SQL Server، MySQL، PostgreSQL) یک Adapter مجزا در
`backend/app/sync_engine/adapters/` دارد که اینترفیس مشترک `BaseSiteAdapter` را پیاده‌سازی می‌کند
و با `adapter_factory.get_adapter` ساخته می‌شود:

```python
class BaseSiteAdapter(ABC):
    async def test_connection(self) -> tuple[bool, str | None]: ...
    async def fetch_rows(self, table_name: str, columns: list[str]) -> list[dict]: ...
    async def update_field(...): ...            # Write-back (مثل ویرایش ایمیل/موبایل)
    async def discover_schema(self) -> dict: ...  # کشف ساختار (Schema Discovery)
    async def sample_column_values(self, table_name, column_name, limit=5) -> list: ...
```

اضافه کردن دیتابیس جدید (مثلاً Oracle) = ساخت یک Adapter جدید، بدون تغییر در Core.

Sync Service (`sync_engine/sync_service.py`) این مراحل را برای هر Site اجرا می‌کند:
1. خواندن `site_connections` (رمزگشایی پسورد) و `employee_mappings`
2. در صورت تعریف، خواندن جدول Lookup واحدها (مثل `dbo.Sections`) برای ترجمه کد واحد به نام
3. خواندن ردیف‌های خام پرسنل از طریق Adapter
4. تبدیل هر ردیف به فیلدهای `Employee` طبق Mapping — شامل ساخت خودکار واحد سازمانی
5. Insert/Update بر اساس `personnel_code` در همان Site
6. غیرفعال‌کردن (نه حذف) پرسنلی که دیگر در منبع نیستند یا غیرفعال اعلام شده‌اند
7. ثبت نتیجه در `sync_logs` و به‌روزرسانی `last_sync_*`

علاوه بر Sync پرسنل، اتصال هر سایت برای این موارد هم استفاده می‌شود: تردد خام دستگاه
(`attendance_mappings` → گزارش تردد ماهانه)، و در سایت‌های کاراوب، ثبت درخواست مرخصی/ماموریت و
تردد فراموش‌شده و نوشتن در کارکرد (`leave_request_service`، `kara_attendance_writeback`، `kara_schema`)
— جزئیات در [`kara-integration.md`](kara-integration.md).

## Job های زمان‌بندی‌شده (APScheduler)

همه در `app/core/scheduler.py`، هنگام بالا آمدن سرویس ثبت می‌شوند و هر کدام با یک
PostgreSQL Advisory Lock محافظت می‌شوند تا بین Worker ها فقط یک‌بار اجرا شوند:

| Job | زمان‌بندی |
|---|---|
| Sync خودکار پرسنل همه سایت‌ها | هر ۱ دقیقه چک می‌شود؛ فاصله واقعی از پنل (دیتابیس) خوانده می‌شود (خاموش با `SYNC_ENABLED=false`) |
| پیام تبریک تولد | روزانه، ساعت قابل‌تنظیم از پنل |
| خلاصه تبریک‌های تولد (ری‌اکشن‌ها) برای متولد | روزانه ۲۰:۰۰ |
| نمونه‌برداری CPU/RAM/دیسک سرور | هر ۱۰ دقیقه یک نمونه |
| بکاپ زمان‌بندی‌شده + ارسال به SMB/FTP/ایمیل | هر ۵ دقیقه چک می‌شود؛ زمان‌بندی از پنل |
| یادآوری ارزیابی‌های انجام‌نشده | روزانه ۰۹:۰۰ |

## امنیت

- پسورد کاربران: bcrypt (یک‌طرفه)
- Credential دیتابیس سایت‌ها و رمزهای SMTP/SMS/بکاپ راه‌دور: Fernet (AES) — دوطرفه، چون سرویس باید بتواند آن را بخواند
- JWT با Access Token کوتاه‌مدت + Refresh Token، الگوریتم HS256 با لیست سفید صریح (در برابر حمله `alg: none` مقاوم)
- تمام کلیدها از Environment Variables (`backend/.env`) خوانده می‌شوند، هرگز در کد نیستند
- احراز هویت فقط با Bearer Token (نه Cookie)؛ به همین دلیل CORS با `allow_credentials=False`
- قفل موقت ورود و محدودیت ارسال اطلاعیه — با شمارنده در دیتابیس (نه درون‌حافظه‌ای)، بین همه Worker های سرویس مشترک ([`rate-limiting.md`](rate-limiting.md))
- رنج‌های IP مجاز (ضدVPN) — به‌همراه محدودیت Firewall الزامی روی سرور اصلی برای جلوگیری از دورزدن با جعل `X-Forwarded-For` ([`ip-allowlist.md`](ip-allowlist.md)، [`reverse-proxy-firewall.md`](reverse-proxy-firewall.md))
- هدرهای امنیتی HTTP کامل (CSP، Permissions-Policy، HSTS، X-Frame-Options و...) در پیکربندی Nginx که `install.sh` می‌سازد، بدون هیچ وابستگی به CDN خارجی (فونت Vazirmatn Self-Host است)
- واترمارک نام/کد پرسنلیِ بیننده روی عکس پرسنل (`image_watermark.py`)
- عملیات‌های سطح-زیرساخت از پنل (بازیابی بکاپ، اعمال آپدیت) از یک الگوی مشترک استفاده می‌کنند: یک قانون Sudoers محدود و دقیق + اجرا در یک Scope مستقل با `systemd-run` (نه زیرمجموعه Cgroup خودِ سرویس، که باعث می‌شد وقتی سرویس Restart می‌شود، خودِ عملیات هم کشته شود) — جزئیات در [`backup.md`](backup.md)

## پشته فناوری

| لایه | تکنولوژی |
|---|---|
| Backend | Python + FastAPI (Async) + SQLAlchemy 2 (Async، asyncpg) + Alembic |
| دیتابیس اصلی Portal | PostgreSQL |
| اتصال به دیتابیس سایت‌ها | pymssql (SQL Server/کاراوب)، PyMySQL، asyncpg/psycopg2 |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Scheduler | APScheduler |
| Realtime | WebSocket (`/api/v1/attendance/presence-ws`) برای حضور آنلاین |
| Frontend | React 18 + React Router 6 + MUI 6 (RTL کامل با `stylis-plugin-rtl`) + Vite 5 + Axios |
| PWA / Push | vite-plugin-pwa + Workbox، Web Push (VAPID، `pywebpush`) |
| PDF | ReportLab + arabic-reshaper + python-bidi (فیش حقوقی/کارکرد) |
| XLSX | openpyxl (فیش کارکرد، خروجی مرخصی/ارزیابی) |
| تاریخ شمسی | jdatetime |
| تصویر | Pillow (واترمارک، بندانگشتی عکس پرسنل، لوگو) |
| آمار سرور | psutil |
| پیامک | ippanel Edge API از طریق httpx |
| ایمیل | smtplib استاندارد (تنظیمات SMTP از پنل) |
| Web Server تولید | Nginx (Reverse Proxy + Serve فایل‌های Frontend) + systemd (`faipco-backend`، Uvicorn با ۲ Worker) |
