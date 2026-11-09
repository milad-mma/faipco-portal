# تست و بررسی‌های قبل از انتشار

مرحله ۰ برنامه بازسازی ساختار (ماژولارسازی): قبل از هر جابه‌جایی کد، ابزارهایی که ثابت کنند «هیچ چیزی که نصب فعلی به آن وابسته است» تغییر نکرده.

## اجرای همه بررسی‌ها

```bash
bash scripts/check.sh          # همه (روی سرور یا محیط توسعه با venv و PostgreSQL)
bash scripts/check.sh --quick  # فقط بررسی‌های بدون وابستگی
```

## ۱. عکس فوری مسیرهای API (`backend/tests/api_snapshot.py`)

فرانت‌اند نصب‌شده و PWA کاربران به آدرس‌های `/api/v1/...` وابسته‌اند؛ بازسازی ساختار نباید حتی یک مسیر را عوض کند.

- `backend/tests/api_routes.snapshot.json`: مرجع - همه مسیرها (`METHOD /api/v1/path`)، الان ۲۴۶ مورد.
- `python3 tests/api_snapshot.py` (از پوشه backend): مسیرهای فعلی را با تحلیل ایستای کد (بدون نیاز به FastAPI) از `router.py` و `endpoints/*.py` می‌سازد و با مرجع مقایسه می‌کند. مسیر حذف‌شده → خروجی ۱؛ مسیر جدید → فقط اطلاع.
- `python3 tests/api_snapshot.py --write`: به‌روزرسانی مرجع - **فقط** وقتی تغییر مسیر عمدی است (مثلاً endpoint جدید).
- `tests/test_api_routes_runtime.py` (pytest): همان مرجع را با مسیرهای واقعی `app.routes` مقایسه می‌کند تا چیزی که تحلیل ایستا نمی‌بیند از قلم نیفتد.
- `install.sh` قبل از Migration ها این بررسی را اجرا می‌کند (Step 5 - Pre-flight)؛ **فقط هشدار** می‌دهد و آپدیت را متوقف نمی‌کند.

## ۲. زنجیره Migration ها (`scripts/test_migrations.sh`)

نصب جدید باید از صفر تا `head` بدون خطا برسد و آخرین Migration برگشت‌پذیر باشد.

- یک دیتابیس موقت `faipco_migtest_<pid>` با همان کاربر `DATABASE_URL` می‌سازد، `alembic upgrade head`، بررسی `current == head`، سپس `downgrade -1` و `upgrade head`، و در پایان دیتابیس موقت را حذف می‌کند (حتی در صورت خطا).
- دیتابیس واقعی پرتال دست نمی‌خورد.
- روی سرور به‌عنوان root اجرا می‌شود (`su postgres` برای ساخت/حذف دیتابیس).

## ۳. تست‌های واحد (`backend/tests/test_*.py`)

قوانین حساس (مرخصی/ماموریت، ارزیابی، زمان‌بندی بکاپ، فیلتر کلمات، پیشنهاد نگاشت):

```bash
cd backend && source .venv/bin/activate && python -m pytest -q tests
```

## قاعده برای مراحل بعدی بازسازی

هر مرحله فقط وقتی «تمام» است که `bash scripts/check.sh` سبز باشد و مرجع مسیرها (`api_routes.snapshot.json`) بدون تغییر مانده باشد.

## اجرا از پنل ادمین

در صفحه «بررسی و اعمال آپدیت» کارت «بررسی سلامت پروژه» با یک کلیک `scripts/check.sh --log` را اجرا می‌کند (مجوز `system.backup`، مثل آپدیت):

- `POST /system/run-checks` → `systemd-run --unit=faipco-check` به‌عنوان root (قانون sudoers در `install.sh`؛ روی نصب‌های قبلی با اولین آپدیت/اجرای install.sh اضافه می‌شود). فقط می‌خواند/تست می‌کند؛ به همین دلیل برخلاف آپدیت، رمز دوباره خواسته نمی‌شود.
- `GET /system/check-status` → لاگ زنده از `/var/log/faipco-check.log` (هر اجرا از نو نوشته می‌شود) + `is_running` / `is_passed` / `is_failed` (بر اساس خط `[CHECK] RESULT: PASS|FAIL` در انتهای لاگ).

## ثبت APIهای چاپ فیش در Snapshot (۹ نوامبر ۲۰۲۶)

دو Endpoint خواندنی جدیدِ چاپ مرورگر فیش حقوقی و کارکرد که از قبل در سورس موجود بودند، در مرجع `backend/tests/api_routes.snapshot.json` ثبت شدند. تعداد مرجع اکنون **۵۳۰ مسیر** است (قبلاً ۵۲۸). هدف رفع شکست `test_runtime_routes_match_snapshot` در «بررسی سلامت پروژه» است؛ هیچ Endpoint، رفتار Backend یا Migration تغییر نکرده است.

بررسی پس از نصب نسخه:

```bash
cd /var/www/html/backend
python3 tests/api_snapshot.py
.venv/bin/python -m pytest -q tests/test_api_routes_runtime.py
```

در صورت افزودن عمدی مسیر جدید در آینده، پیش از انتشار `python3 tests/api_snapshot.py --write` را اجرا کنید و فایل JSON مرجع را همراه تغییر مسیر در Git ثبت کنید؛ صرفاً برای سبز شدن تست، مسیر ناشناخته را بدون بررسی تأیید نکنید.


## تست‌های بهینه‌سازی مسیرهای پرتکرار (۱۴۰۵/۰۸/۱۸)

- `cd backend && .venv/bin/python -m pytest -q tests/test_performance_hotpaths.py` — بررسی برابری شمارنده با مجوز جانشینی و اشتراک خواندن تردد در درخواست‌های هم‌زمان، بدون اتصال واقعی به کاراوب.
- `cd frontend && npm run test:unit` — بررسی درخواست مشترک عکس، لغو فقط پس از آخرین مصرف‌کننده، و جداسازی داده در تعویض حساب. نیازمند Node.js دارای `node:test`.
- سپس اسکریپت «بررسی سلامت پروژه» و `npm run build` را اجرا کنید. تست واقعی روی پایگاه داده کاراوب و زیر بار چند Worker جداگانه همچنان به محیط تست نیاز دارد.
