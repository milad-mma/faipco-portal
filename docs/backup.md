# پشتیبان‌گیری و بازیابی

⚠️ این قابلیت فقط برای بازیابی **روی همین سرور** طراحی شده — نه Clone به
یک سرور دیگر. برای ساخت یک نسخه کامل روی سرور دیگری، پروژه را با
`install.sh` روی آن سرور تازه نصب کنید (نگاه کنید
[`docs/deployment.md`](deployment.md)).

## دسترسی و صفحه

صفحه `/backup` (منوی «پشتیبان‌گیری»). همه Endpoint های `/backup/*` مجوز
`system.backup` می‌خواهند که طبق `scripts/seed_permissions.py` فقط به
superadmin تعلق دارد (به هیچ نقش دیگری داده نمی‌شود). همین صفحه برای
دارندگان `system.cache_bust` هم باز است (`can_manage_backup || can_bust_cache`)
و سه بخش دیگر هم دارد: کارت «نگهداری اپلیکیشن» (پاک‌کردن کش اپ برای همه
کاربران — نگاه کنید [`pwa.md`](pwa.md)) و کارت زمان‌بندی بکاپ خودکار
([`backup-scheduling.md`](backup-scheduling.md)).

## پشتیبان‌گیری

`GET /backup/export` یک فایل Zip با نام `faipco-backup-YYYYMMDD-HHMMSS.zip`
برمی‌گرداند شامل `database.dump` (Dump کامل Schema + Data با
`pg_dump --format=custom --no-owner --no-privileges`) و یک `manifest.json`
(`format: faipco-portal-backup-v3-fullsnapshot`). این عملیات کاملاً
فقط‌خواندنی است — هیچ‌وقت چیزی روی سرور تغییر نمی‌کند. مسیر `pg_dump`/
`pg_restore`/`psql` حتی اگر PATH سرویس systemd محدود باشد، از مسیرهای
رایج (`/usr/bin`، `/usr/lib/postgresql/*`) پیدا می‌شود.

## بازیابی

از همان صفحه، فایل بکاپ را آپلود و عبارت `RESTORE` را برای تأیید تایپ
می‌کنید. مراحل (همه در پس‌زمینه، بعد از یک پاسخ فوری «شروع شد»):

1. سرویس `faipco-backend` کامل متوقف می‌شود — چون در حال اجرا ماندنش باعث
   قفل‌شدن دائمی مرحله بعد می‌شود (Connection Pool زنده‌اش روی همان
   جدول‌هایی که باید بازسازی شوند قفل می‌گیرد).
2. Schema فعلی (`public`) پاک نمی‌شود، بلکه به `public_prerestore` تغییر نام
   می‌دهد و یک `public` خالی ساخته می‌شود.
3. `pg_restore --single-transaction --no-owner --no-privileges` روی این
   Schema خالی اجرا می‌شود.
4. `alembic upgrade head` اجرا می‌شود (برای بکاپ‌های قدیمی‌تر از نسخه فعلی
   کد؛ Migration ها هیچ‌وقت داده حذف نمی‌کنند).
5. موفق ← `public_prerestore` پاک می‌شود. ناموفق (مرحله ۳ یا ۴) ← داده
   قبلی خودکار برگردانده می‌شود (بخش «برگشت خودکار» پایین).
6. سرویس دوباره روشن می‌شود — چه موفق چه ناموفق، همیشه.

قبل از همه این‌ها، خودِ درخواست `POST /backup/restore` (فیلدهای `file` و
`confirm`) فقط اعتبارسنجی می‌کند: عبارت تأیید (سمت سرور هم چک می‌شود)،
Zip معتبر و وجود `database.dump`؛ فایل در `/tmp/faipco-restore-staging`
باز می‌شود و خطاهای این مرحله فوراً با ۴۰۰ برمی‌گردند.

پنل هر ۳ ثانیه (حداکثر ۳ دقیقه) `GET /backup/restore-status` را می‌پرسد و
لاگ زنده (`/tmp/faipco-restore.log`) را نشان می‌دهد؛ خطاهای شبکه در لحظه
Stop/Start سرویس با Retry پوشش داده می‌شوند. وضعیت از روی متن لاگ
(`Restore finished successfully` / `Restore FAILED`) و `systemctl is-active
faipco-restore` تعیین می‌شود. بعد از موفقیت، صفحه خودکار Reload می‌شود.

## نکته امنیتی مهم — چرا systemd-run

چون این عملیات از داخل همان سرویسی صدا زده می‌شود که در مرحله ۱ باید
متوقف شود، اجرای مستقیم (حتی با `setsid`) باعث می‌شد systemd کل Cgroup آن
سرویس — از جمله خودِ اسکریپت اجراکننده — را همان لحظه بکشد. به‌جایش، کل
فرآیند با `sudo -n /usr/bin/systemd-run --unit=faipco-restore --collect
/bin/sh /tmp/faipco-restore-run.sh` در یک Unit کاملاً مستقل (و به‌عنوان
root، پشت یک قانون Sudoers دقیق در `install.sh` و محدود به همین یک دستور
ثابت) اجرا می‌شود. اگر همین راه‌اندازی شکست بخورد (مثلاً Sudoers درست
نصب نشده باشد)، Endpoint با خطای ۵۰۰ و پیام روشن برمی‌گردد و دیتابیس
دست‌نخورده می‌ماند.

فایل لاگ عمداً از داخل سرویس (کاربر `www-data`) پاک نمی‌شود — چون مالکش
root است و `/tmp` Sticky Bit دارد؛ خودِ اسکریپت (root) هر بار با `>` آن را
از نو می‌سازد.

---

## برگشت خودکار در بازیابی ناموفق

قبلاً Schema فعلی قبل از بازیابی پاک می‌شد و اگر `pg_restore` یا Migration شکست می‌خورد، دیتابیس خالی می‌ماند (پیام پایانی به‌اشتباه می‌گفت «روی داده قبلی»). حالا:

1. Schema فعلی پاک نمی‌شود، فقط به `public_prerestore` تغییر نام می‌دهد و یک `public` خالی ساخته می‌شود.
2. بازیابی و Migration روی `public` جدید اجرا می‌شوند.
3. موفق: `public_prerestore` پاک می‌شود. ناموفق: `public` نیمه‌کاره پاک و `public_prerestore` دوباره `public` می‌شود - یعنی دقیقاً داده قبل از شروع.
4. اگر حتی این برگشت هم شکست بخورد، داده قبلی در `public_prerestore` دست‌نخورده می‌ماند و لاگ صریحاً می‌گوید بازیابی دیگری اجرا نشود.
