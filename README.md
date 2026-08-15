# FAIPCO Portal

پرتال سازمانی برای مدیریت پرسنل، اطلاعیه‌ها (متنی، فیش حقوقی، فیش کارکرد)،
دسترسی‌ها (RBAC)، و اتصال به دیتابیس‌های چندگانه‌ی سایت‌های مختلف یک سازمان
(چند کارخانه/شعبه، هرکدام با ساختار دیتابیس پرسنلی متفاوت).

**پشته فناوری**: FastAPI (Async) + PostgreSQL در بک‌اند، React + MUI (RTL) در
فرانت‌اند، PWA با Web Push. جزئیات کامل در [`docs/architecture.md`](docs/architecture.md).

## نصب روی سرور (Production)

روی یک Ubuntu Server (22.04 یا 24.04)، با دسترسی root:

```bash
curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh | sudo bash
```

یا با آرگومان‌های دلخواه:

```bash
curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh -o install.sh
sudo bash install.sh --domain portal.mycompany.com --admin-username admin
```

همین دستور برای **آپدیت** نصب موجود هم استفاده می‌شود (خودکار تشخیص داده
می‌شود) — جزئیات کامل، همه آرگومان‌ها، و نکات SSL در
[`docs/deployment.md`](docs/deployment.md).

## اجرای محلی (Development)

```bash
# Backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # کلیدها را طبق docs/development.md تنظیم کنید
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (در یک ترمینال دیگر)
cd frontend && npm install && npm run dev
```

راهنمای کامل (متغیرهای `.env`، Migration ها، Seed اولیه، تست سریع API) در
[`docs/development.md`](docs/development.md).

## مستندات کامل

| سند | موضوع |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | معماری، دلایل انتخاب تکنولوژی، پشته فناوری |
| [`docs/project-structure.md`](docs/project-structure.md) | ساختار پوشه‌ها و فایل‌های پروژه |
| [`docs/features.md`](docs/features.md) | فهرست کامل ویژگی‌ها |
| [`docs/development.md`](docs/development.md) | راه‌اندازی محیط توسعه محلی |
| [`docs/deployment.md`](docs/deployment.md) | نصب/آپدیت روی سرور Production |
| [`docs/sync-engine.md`](docs/sync-engine.md) | راه‌اندازی Sync خودکار پرسنل |
| [`docs/notices.md`](docs/notices.md) | سیستم اطلاعیه‌ها |
| [`docs/payroll-notices.md`](docs/payroll-notices.md) | اطلاعیه فیش حقوقی (آپلود XML/XLSX) |
| [`docs/employee-management.md`](docs/employee-management.md) | مدیریت پرسنل از پنل Admin |
| [`docs/rbac.md`](docs/rbac.md) | نقش‌ها و سطوح دسترسی |
| [`docs/rate-limiting.md`](docs/rate-limiting.md) | قفل موقت ورود و محدودیت ارسال اطلاعیه |
| [`docs/ip-allowlist.md`](docs/ip-allowlist.md) | محدودکردن ورود به رنج‌های IP مجاز (ضدVPN) |
| [`docs/gps-attendance.md`](docs/gps-attendance.md) | حضور مبتنی بر GPS + ثبت ورود/خروج آزمایشی |
| [`docs/birthday-greetings.md`](docs/birthday-greetings.md) | پیام‌های تبریک تولد (ارسال خودکار روزانه) |
| [`docs/design-decisions.md`](docs/design-decisions.md) | تصمیم‌های طراحی آگاهانه + کارهای باز |
