# نصب روی سرور Production


روی یک Ubuntu Server (22.04 یا 24.04)، با دسترسی root:

```bash
curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh | sudo bash
```

یا با آرگومان‌های دلخواه:

```bash
curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh -o install.sh
sudo bash install.sh --domain portal.mycompany.com --admin-username admin
```

اسکریپت به‌صورت خودکار **نصب یا آپدیت** را تشخیص می‌دهد (بر اساس اینکه
`backend/.env` از قبل وجود دارد یا نه). لاگ کامل هر اجرا در
`/var/log/faipco-install.log` ذخیره می‌شود.

- **نصب تازه**: در صورت کمبود RAM، فعال‌سازی Swap → پیش‌نیازها (Python،
  FreeTDS برای SQL Server، Nginx، UFW، `smbclient` برای بکاپ SMB، Node.js 20،
  PostgreSQL) → Clone سورس → ساخت venv و نصب `requirements.txt` → ساخت
  دیتابیس و کاربر `faipco_user` با پسورد تصادفی امن → تولید `.env` با کلیدهای
  امنیتی یکتا + کلیدهای VAPID (`DEBUG=false`، `APP_VERSION` از تگ Git) →
  Migration ها (`alembic upgrade head`) → Build فرانت‌اند
  (`VITE_API_BASE_URL=/api/v1`) → سرویس systemd `faipco-backend` (Uvicorn روی
  `127.0.0.1:8000` با ۲ Worker) + قانون Sudoers محدود برای بازیابی/آپدیت از پنل
  → پیکربندی Nginx (سرو فرانت‌اند، Proxy مسیر `/api` و WebSocket، هدرهای امنیتی،
  قوانین Cache برای `sw.js`/`index.html`) → `seed_permissions` + ساخت کاربر Admin
  → تنظیم فایروال (UFW).
- **آپدیت** (وقتی نصب قبلی پیدا شود): `.env`، پسورد دیتابیس، کلیدهای VAPID و
  خودِ دیتابیس **هرگز دست‌خورده نمی‌شوند** (فقط `APP_VERSION` به‌روز می‌شود و
  کلیدهای جاافتاده اضافه می‌شوند) — سورس رفرش، وابستگی‌ها دوباره نصب، Migration
  های جدید به‌صورت افزایشی اجرا (هیچ‌وقت داده‌ای پاک نمی‌کند)، Permission های
  جدید Seed، فرانت‌اند دوباره Build، و سرویس‌ها Restart می‌شوند. کاربر Admin
  دوباره ساخته نمی‌شود. یعنی هر بار که روی GitHub Push می‌کنید، همین یک دستور
  برای Deploy کافی است.

**آرگومان‌های قابل استفاده:**

| آرگومان | توضیح | پیش‌فرض |
|---|---|---|
| `--domain` | دامنه پرتال (فقط برای CORS استفاده می‌شود) | ندارد (فقط IP سرور) |
| `--admin-username` | نام کاربری Admin اولیه (فقط نصب تازه) | `admin` |
| `--admin-password` | رمز عبور Admin اولیه (فقط نصب تازه) | `admin` |
| `--install-dir` | مسیر نصب روی سرور | `/var/www/html` |
| `--repo` | آدرس Git Repository | `github.com/milad-mma/faipco-portal` |
| `--branch` | Branch مورد استفاده | `main` |
| `--reverse-proxy-ip` | ⚠️ در ادامه توضیح داده شده — به‌شدت توصیه‌شده اگر یک Reverse Proxy خارجی دارید | ندارد |

به‌جای آرگومان، می‌توان از متغیرهای محیطی `FAIPCO_REPO_URL`، `FAIPCO_BRANCH`،
`FAIPCO_INSTALL_DIR`، `FAIPCO_ADMIN_USERNAME` و `FAIPCO_ADMIN_PASSWORD` هم استفاده کرد.

⚠️ اگر `--admin-password` ندهید، پسورد پیش‌فرض `admin` است — چون این رمز
قانون قدرت رمز (حداقل ۱۰ کاراکتر + حرف کوچک + حرف بزرگ + عدد؛ نگاه کنید
[`docs/rbac.md`](rbac.md#قانون-قدرت-رمز-عبور-و-اجبار-به-تغییر)) را رعایت
نمی‌کند، سیستم خودش همان اولین ورود شما را مجبور به تعیین یک رمز جدید
می‌کند — نیازی نیست خودتان یادتان بماند.

**نکته مهم امنیتی — `--reverse-proxy-ip`**: اگر یک Reverse Proxy خارجی (برای
SSL) جلوی این سرور دارید، حتماً IP آن را با این آرگومان بدهید:

```bash
sudo bash install.sh --reverse-proxy-ip <IP-که-این-سرور-واقعاً-می‌بیند>
```

بدون این، پورت‌های ۸۰/۴۴۳ به کل اینترنت باز می‌مانند — یعنی هرکسی که IP مستقیم
این سرور را بداند می‌تواند با جعل هدر `X-Forwarded-For` محدودیت‌های مبتنی بر
IP (مثل «رنج‌های IP مجاز») را دور بزند؛ این یک یافته واقعی از یک تست نفوذ
زنده است، نه یک احتیاط نظری — جزئیات کامل در
[`docs/reverse-proxy-firewall.md`](reverse-proxy-firewall.md). نکته مهم: اگر
Proxy روی یک شبکه محلی/خصوصی جدا از این سرور است (توپولوژی دو‌لایه رایج)،
باید IP **محلی** پروکسی را بدهید، نه IP عمومی‌ای که دامنه به آن اشاره می‌کند
— چون این سرور هیچ‌وقت آن IP عمومی را به‌عنوان مبدأ نمی‌بیند. این مقدار یک‌بار
تنظیم شود، در تمام آپدیت‌های بعدی (حتی بدون تکرار این آرگومان) خودکار حفظ
می‌شود.

**نکته مهم درباره SSL**: این اسکریپت دیگر خودش SSL/Let's Encrypt را مدیریت
نمی‌کند — Nginx محلی همیشه روی HTTP ساده (پورت ۸۰) اجرا می‌شود و SSL باید توسط
یک Reverse Proxy خارجی (که از قبل روی سرور یا جلوی آن راه‌اندازی شده) تأمین
شود. آرگومان `--domain` فقط برای تنظیم صحیح CORS استفاده می‌شود.

نصب با Docker از پروژه حذف شده است؛ تنها روش پشتیبانی‌شده همین `install.sh` است.

## آپدیت از داخل پنل

علاوه بر اجرای دستی `install.sh`، از منوی «بررسی و اعمال آپدیت» (فقط Admin
اصلی، مسیر `/update`) می‌توانید نسخه فعلی را با آخرین Tag منتشرشده در GitHub
مقایسه کنید و آپدیت را مستقیم از پنل اجرا کنید — این قابلیت عملاً معادل اجرای
دستی همین `install.sh` است (با `systemd-run`، خارج از Cgroup سرویس)، فقط از راه
دور، پشت تأیید دوباره رمز عبور و عبارت تأیید، با نمایش لاگ زنده. جزئیات در
کامنت‌های `backend/app/services/update_service.py`. در همان صفحه، متن «اعلان
تغییرات پرتال» هم برای نمایش به کاربران قابل ویرایش است.

## دستورات مفید پس از نصب

```bash
systemctl status faipco-backend     # وضعیت سرویس Backend
journalctl -u faipco-backend -f     # لاگ زنده
systemctl restart faipco-backend    # بعد از ویرایش backend/.env
```

ابزارهای جانبی: `install-pgadmin.sh` برای نصب اختیاری pgAdmin 4
([`pgadmin.md`](pgadmin.md))، و `scripts/pentest-live.sh` برای تست نفوذ
غیرمخرب روی دامنه خودتان ([`pentest-manual-checklist.md`](pentest-manual-checklist.md)).

## اتصال به کاراوب (مرخصی/ماموریت و تردد فراموش‌شده)

`install.sh` هنگام آپدیت، Migration ها (`alembic upgrade head`) و
وابستگی‌های Python را خودکار اجرا می‌کند. برای قابلیت‌هایی که در دیتابیس
کاراوب می‌نویسند، کاربر SQL Server ای که در «تنظیمات سایت ← اتصال» تعریف شده
باید مجوزهای جدول
[`kara-integration.md` بخش ۷](kara-integration.md#۷-مجوزهای-لازم-کاربر-پرتال-در-دیتابیس-کاراوب)
را داشته باشد. بعد از اولین نصب/آپدیت:

1. تنظیمات سایت ← تب «نگاشت تردد» و «نگاشت مرخصی/ماموریت» ← «پر کردن
   فیلدهای خالی با نام‌های کاراوب» ← ذخیره.
2. «تنظیمات مرخصی/ماموریت» ← نوع‌های درخواست و مسئول نیروی انسانی هر سایت.

