# FAIPCO Portal

پرتال سازمانی برای مدیریت پرسنل، اطلاعیه‌ها، دسترسی‌ها و اتصال به دیتابیس‌های چندگانه سایت‌های سازمانی.

## وضعیت پروژه

در حال توسعه مرحله‌ای طبق نقشه راه زیر:

- [x] **مرحله ۱ — Backend Core**: اسکلت FastAPI، تنظیمات، اتصال دیتابیس، هسته امنیتی
- [x] **مرحله ۲ — Database Models**: مدل‌های Users/Roles/Permissions/Sites/Employees/Notices + Alembic Migrations
- [x] **مرحله ۳ — Authentication (JWT + RBAC)**: Login/Refresh/Me + Dependency بررسی مجوز
- [x] **مرحله ۴ — Employee Sync Engine**: Adapter های PostgreSQL/MySQL/SQL Server، Sync Service، Scheduler خودکار
- [x] **مرحله ۵ — Notification System**: CRUD اطلاعیه + تعیین خودکار مخاطب (Site/Department/Role/Employee/All)
- [x] **مرحله ۶ — Frontend Dashboard (React)**: پنل کامل RTL با MUI — Login، Dashboard، Employees، Sites، Sync، Notices
- [x] **مرحله ۷ — Installer**: `install.sh` نصب یک‌دستوری روی Ubuntu + `docker-compose.yml` اختیاری
- [ ] مرحله ۸ — Documentation کامل

## ساختار پروژه

```
faipco-portal/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # روترهای API (endpoints هر ماژول)
│   │   ├── core/            # تنظیمات، امنیت، JWT
│   │   ├── db/              # اتصال دیتابیس اصلی Portal
│   │   ├── models/          # مدل‌های SQLAlchemy (مرحله ۲)
│   │   ├── schemas/         # مدل‌های Pydantic برای ورودی/خروجی API
│   │   ├── services/        # منطق تجاری (Business Logic)
│   │   ├── repositories/    # لایه دسترسی به داده
│   │   ├── sync_engine/     # موتور همگام‌سازی با دیتابیس سایت‌ها (مرحله ۴)
│   │   └── main.py          # نقطه ورود برنامه
│   ├── requirements.txt
│   └── .env.example
├── frontend/                 # React Dashboard (RTL, MUI) — تکمیل‌شده در مرحله ۶
├── database/migrations/      # Alembic Migrations
├── scripts/                  # اسکریپت‌های کمکی (seed, create_admin, verify_models)
├── docs/                     # مستندات معماری و API
├── docker-compose.yml         # اجرای اختیاری با Docker
└── install.sh                 # اسکریپت نصب یک‌دستوری — تکمیل‌شده در مرحله ۷
```

## اجرای محلی (Development) — مرحله ۱

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# مقادیر SECRET_KEY و DB_CREDENTIALS_ENCRYPTION_KEY را طبق راهنمای داخل .env.example تولید و جایگزین کنید
# مقدار DATABASE_URL را با اطلاعات PostgreSQL خودتان تنظیم کنید

uvicorn app.main:app --reload
```

سپس:
- مستندات API: http://localhost:8000/api/docs
- بررسی سلامت سرویس: http://localhost:8000/api/health

## اجرای Migration ها و Seed اولیه — مرحله ۲

```bash
# بررسی صحت مدل‌ها (بدون نیاز به دیتابیس)
bash scripts/verify_models.sh

# ساخت اولین Migration بر اساس مدل‌ها
cd backend
alembic revision --autogenerate -m "initial tables"
alembic upgrade head

# Seed اولیه Permission ها و نقش superadmin
cd ..
python -m scripts.seed_permissions
```

### جداول ایجادشده در این مرحله
`users`, `roles`, `permissions`, `role_permissions`, `user_roles`, `sites`,
`site_connections`, `departments`, `employees`, `employee_mappings`,
`notices`, `notice_targets`, `sync_logs`

## ساخت کاربر Admin و تست ورود — مرحله ۳

```bash
# بعد از اجرای migration ها:
python -m scripts.create_admin --username admin --password 'StrongPass123!'

# تست Login:
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "StrongPass123!"}'

# با access_token دریافت‌شده:
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"

curl http://localhost:8000/api/v1/employees \
  -H "Authorization: Bearer <access_token>"
```

### نحوه کار RBAC
هر Endpoint حساس با `Depends(require_permission("employees.view"))` محافظت می‌شود.
اگر کاربر `is_superuser=True` باشد، همیشه دسترسی دارد. در غیر این‌صورت، Permission های مؤثر
کاربر (نقش‌های سراسری + نقش‌های مخصوص همان Site) از دیتابیس خوانده و بررسی می‌شود.

## راه‌اندازی Sync Engine — مرحله ۴

مثال کامل برای اضافه کردن یک Site جدید و اجرای اولین Sync:

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

# ۴. تست اتصال
curl -X POST http://localhost:8000/api/v1/sync/1/test-connection \
  -H "Authorization: Bearer $TOKEN"

# ۵. اجرای دستی Sync
curl -X POST http://localhost:8000/api/v1/sync/1/run \
  -H "Authorization: Bearer $TOKEN"

# ۶. مشاهده تاریخچه Sync
curl http://localhost:8000/api/v1/sync/1/logs \
  -H "Authorization: Bearer $TOKEN"
```

بعد از اجرای موفق، رکوردهای `employees` مربوط به Site 1 پر می‌شوند و از این پس هر
`SYNC_INTERVAL_MINUTES` دقیقه (پیش‌فرض ۳۰) به‌صورت خودکار توسط Scheduler به‌روزرسانی می‌شوند
(قابل غیرفعال‌سازی با `SYNC_ENABLED=false` در `.env`).

### نکته درباره کارخانه ۲ (مثال از Prompt اولیه)
برای Site ای که ستون‌هایش فرق دارد (`employees`, `personnel_code`, `national_code`, ...)،
کافی است در مرحله ۳ بالا مقادیر متفاوتی برای Mapping بفرستید — **هیچ خط کدی تغییر نمی‌کند**.

## سیستم اطلاعیه — مرحله ۵

```bash
TOKEN="<access_token>"

# ایجاد اطلاعیه (وضعیت اولیه: draft) — همزمان به همه پرسنل Site شماره ۱ و به نقش "superadmin"
curl -X POST http://localhost:8000/api/v1/notices \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "title": "اطلاعیه تعطیلی",
    "body": "روز پنج‌شنبه تعطیل است.",
    "priority": "high",
    "targets": [
      {"target_type": "site", "target_id": 1},
      {"target_type": "role", "target_id": 1}
    ]
  }'

# انتشار اطلاعیه (draft -> published)
curl -X POST http://localhost:8000/api/v1/notices/1/publish -H "Authorization: Bearer $TOKEN"

# مشاهده همه اطلاعیه‌ها (نیازمند notices.view — نمای Admin)
curl http://localhost:8000/api/v1/notices -H "Authorization: Bearer $TOKEN"

# مشاهده اطلاعیه‌های مربوط به خودِ کاربر لاگین‌شده (هر کاربری، بدون نیاز به Permission خاص)
curl http://localhost:8000/api/v1/notices/me -H "Authorization: Bearer $TOKEN"
```

`/notices/me` هوشمند است: بر اساس `employee_id` متصل به حساب کاربر (Site و Department او)
و نقش‌های تخصیص‌یافته‌اش، فقط اطلاعیه‌های واقعاً مرتبط را برمی‌گرداند — دقیقاً طبق طراحی
`notice_targets` که در Prompt اولیه خواسته بودید (all / site / department / role / employee).

## اجرای Frontend — مرحله ۶

```bash
cd frontend
npm install
cp .env.example .env
# در صورت نیاز VITE_API_BASE_URL را ویرایش کنید

npm run dev
```

سپس `http://localhost:3000` را باز کنید و با کاربر Admین ساخته‌شده در مرحله ۳ وارد شوید.

### ساختار Frontend
```
frontend/src/
├── api/          # توابع ارتباط با Backend (axios) — یک فایل به‌ازای هر ماژول
├── components/   # Layout، ProtectedRoute، SyncStatusChip
├── context/       # AuthContext (مدیریت Token و کاربر جاری)
├── pages/        # Login، Dashboard، Employees، Sites، Sync، Notices
├── theme.js      # Design Tokens (رنگ، تایپوگرافی)
└── rtlCache.js   # پیکربندی MUI برای چیدمان راست‌به‌چپ
```

### نکات فنی مهم
- **Refresh خودکار Token**: در `api/client.js`، اگر یک درخواست با خطای 401 مواجه شود،
  به‌صورت خودکار با `refresh_token` یک Access Token جدید گرفته و درخواست را تکرار می‌کند.
- **RTL واقعی**: با `stylis-plugin-rtl` تمام استایل‌های MUI (نه فقط متن) به‌درستی
  برای چیدمان راست‌به‌چپ تولید می‌شوند.
- صفحه «سایت‌ها» دقیقاً با API مرحله ۴ هماهنگ است: ساخت Site → تعریف اتصال دیتابیس
  (پسورد در همان لحظه رمزنگاری و ارسال می‌شود) → تعریف Mapping ستون‌ها.

## نصب روی سرور Linux — مرحله ۷

### روش ۱ — نصب مستقیم (بدون Docker، پیشنهادی برای Production)

روی یک Ubuntu Server تازه (22.04 یا 24.04)، با دسترسی root:

```bash
curl -fsSL https://raw.githubusercontent.com/USER/faipco-portal/main/install.sh | sudo bash
```

یا با دامنه و SSL خودکار:

```bash
curl -fsSL https://raw.githubusercontent.com/USER/faipco-portal/main/install.sh -o install.sh
sudo bash install.sh --domain portal.mycompany.com --admin-username admin
```

اسکریپت به‌صورت کاملاً خودکار انجام می‌دهد:
1. نصب پیش‌نیازها (Python، Node.js، PostgreSQL، Nginx)
2. ساخت دیتابیس و کاربر PostgreSQL با پسورد تصادفی امن
3. Clone سورس، نصب وابستگی‌های Backend در Virtual Environment
4. تولید `.env` با کلیدهای امنیتی یکتا (`SECRET_KEY`, `DB_CREDENTIALS_ENCRYPTION_KEY`)
5. اجرای Migration های دیتابیس
6. Build کردن Frontend
7. ساخت Service systemd (`faipco-backend`) برای اجرای همیشگی Backend
8. پیکربندی Nginx (Reverse Proxy + Serve فایل‌های Frontend)
9. صدور SSL رایگان با Let's Encrypt (در صورت دادن `--domain`)
10. Seed اولیه Permission ها و ساخت کاربر Admin
11. تنظیم فایروال (UFW)

در پایان، آدرس پرتال و اطلاعات ورود Admin روی صفحه نمایش داده می‌شود.

**آرگومان‌های قابل استفاده:**

| آرگومان | توضیح | پیش‌فرض |
|---|---|---|
| `--domain` | دامنه پرتال (برای SSL خودکار) | ندارد (فقط IP سرور) |
| `--no-ssl` | رد کردن SSL حتی با وجود دامنه | — |
| `--admin-username` | نام کاربری Admin اولیه | `admin` |
| `--admin-password` | رمز عبور Admin (وگرنه تصادفی) | تصادفی |
| `--install-dir` | مسیر نصب روی سرور | `/opt/faipco-portal` |

### روش ۲ — Docker (اختیاری)

```bash
cp .env.example .env                          # POSTGRES_PASSWORD را عوض کنید
cp backend/.env.example backend/.env
# SECRET_KEY و DB_CREDENTIALS_ENCRYPTION_KEY را طبق راهنمای داخل فایل تولید و جایگزین کنید
# DATABASE_URL داخل backend/.env توسط docker-compose بازنویسی می‌شود، نیازی به تغییرش نیست

docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_permissions
docker compose exec backend python -m scripts.create_admin --username admin --password 'ChangeMe123!'
```

سپس پرتال روی `http://<IP-سرور>` در دسترس است.

> **نکته:** Docker کاملاً اختیاری است. روش ۱ (`install.sh`) برای اکثر مشتریان (بدون نیاز به دانش Docker) ساده‌تر و توصیه‌شده است.

## معماری

جزئیات کامل معماری، دلایل انتخاب تکنولوژی‌ها، و طرح Sync Engine در [`docs/architecture.md`](docs/architecture.md) آمده است.

## لایسنس

طبق فایل [`LICENSE`](LICENSE) — در مراحل بعدی تکمیل می‌شود.
