# FAIPCO Portal

پرتال سازمانی برای مدیریت پرسنل، اطلاعیه‌ها (متنی، فیش حقوقی، فیش کارکرد)،
دسترسی‌ها (RBAC)، حضور مبتنی بر GPS، پیام تبریک تولد خودکار، و اتصال به
دیتابیس‌های چندگانه‌ی سایت‌های مختلف یک سازمان (چند کارخانه/شعبه، هرکدام با
ساختار دیتابیس پرسنلی متفاوت).

**پشته فناوری**: FastAPI (Async) + PostgreSQL در بک‌اند، React + MUI (RTL) در
فرانت‌اند، PWA با Web Push. جزئیات کامل در [`docs/architecture.md`](docs/architecture.md).

## نصب روی سرور (Production)

روی یک Ubuntu Server (22.04 یا 24.04)، با دسترسی root:

```bash
curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh | sudo bash
```

یا با آرگومان‌های دلخواه — **اگر یک Reverse Proxy خارجی برای SSL دارید،
حتماً `--reverse-proxy-ip` را هم بدهید** (یک یافته امنیتی واقعی، نه یک
احتیاط نظری — جزئیات در [`docs/deployment.md`](docs/deployment.md)):

```bash
curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh -o install.sh
sudo bash install.sh --domain portal.mycompany.com --admin-username admin --reverse-proxy-ip <IP-پروکسی>
```

همین دستور برای **آپدیت** نصب موجود هم استفاده می‌شود (خودکار تشخیص داده
می‌شود). علاوه بر خط‌فرمان، از داخل پنل هم (منوی «بررسی و اعمال آپدیت»، فقط
Admin) می‌توانید نسخه فعلی را با GitHub مقایسه و آپدیت را مستقیم اجرا کنید —
جزئیات کامل، همه آرگومان‌ها، و نکات SSL در [`docs/deployment.md`](docs/deployment.md).

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
| [`docs/design-system.md`](docs/design-system.md) | ⚠️ طراحی جدید پرتال + راه برگشت (`NEW_DESIGN_ENABLED`) |
| [`docs/vehicles.md`](docs/vehicles.md) | قابلیت «خودروهای من» + نقش «حراست» |
| [`docs/role-management.md`](docs/role-management.md) | پنل مدیریت نقش/مجوز |
| [`docs/removed-code-archive.md`](docs/removed-code-archive.md) | بایگانی کد حذف‌شده (کد کامل + دلیل حذف، برای بازسازی احتمالی) |
| [`docs/branding.md`](docs/branding.md) | برندینگ قابل‌تغییر (نام + لوگوی سامانه، از پنل «تنظیمات سامانه») |
| [`docs/monthly-attendance.md`](docs/monthly-attendance.md) | گزارش تردد ماهانه (از دستگاه‌های حضور و غیاب، با نگاشت قابل‌تنظیم) |
| [`docs/feedback.md`](docs/feedback.md) | انتقادات و پیشنهادات (با امکان ناشناس‌بودن) |
| [`docs/development.md`](docs/development.md) | راه‌اندازی محیط توسعه محلی |
| [`docs/deployment.md`](docs/deployment.md) | نصب/آپدیت روی سرور Production |
| [`docs/sync-engine.md`](docs/sync-engine.md) | راه‌اندازی Sync خودکار پرسنل |
| [`docs/notices.md`](docs/notices.md) | سیستم اطلاعیه‌ها |
| [`docs/payroll-notices.md`](docs/payroll-notices.md) | اطلاعیه فیش حقوقی (XML/XLSX) و فیش کارکرد (XLSX) |
| [`docs/employee-management.md`](docs/employee-management.md) | مدیریت پرسنل از پنل Admin |
| [`docs/rbac.md`](docs/rbac.md) | نقش‌ها، سطوح دسترسی، و انتصاب دسته‌جمعی نقش |
| [`docs/rate-limiting.md`](docs/rate-limiting.md) | قفل موقت ورود و محدودیت ارسال اطلاعیه |
| [`docs/ip-allowlist.md`](docs/ip-allowlist.md) | محدودکردن ورود به رنج‌های IP مجاز (ضدVPN) |
| [`docs/gps-attendance.md`](docs/gps-attendance.md) | حضور مبتنی بر GPS + ثبت ورود/خروج آزمایشی |
| [`docs/birthday-greetings.md`](docs/birthday-greetings.md) | پیام‌های تبریک تولد (ارسال خودکار روزانه) |
| [`docs/backup.md`](docs/backup.md) | پشتیبان‌گیری و بازیابی از پنل |
| [`docs/pgadmin.md`](docs/pgadmin.md) | ⚠️ نصب pgAdmin 4 برای مدیریت مستقیم دیتابیس (فقط شبکه محلی) |
| [`docs/usage-stats.md`](docs/usage-stats.md) | نمودار میزان استفاده از پرتال و مصرف سرور (CPU/RAM/دیسک) |
| [`docs/pwa.md`](docs/pwa.md) | PWA، Service Worker، و مشکلات نصب روی اندروید/iOS |
| [`docs/android-app-twa.md`](docs/android-app-twa.md) | ⚠️ بسته‌بندی به اپلیکیشن اندروید واقعی (TWA) — رفع محدودیت نصب مرورگری |
| [`docs/reverse-proxy-firewall.md`](docs/reverse-proxy-firewall.md) | ⚠️ محدودکردن دسترسی مستقیم به سرور (یافته امنیتی واقعی) |
| [`docs/design-decisions.md`](docs/design-decisions.md) | تصمیم‌های طراحی آگاهانه |

### گزارش‌های تست نفوذ (تاریخی)

نتیجه ممیزی‌های امنیتی قبلی، برای مرجع — یافته‌های واقعی همگی رفع شده‌اند
(نگاه کنید بخش‌های امنیتی اسناد بالا برای وضعیت فعلی):
[`docs/pentest-report-2026-08-16.md`](docs/pentest-report-2026-08-16.md),
[`docs/pentest-manual-checklist.md`](docs/pentest-manual-checklist.md).
