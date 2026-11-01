# سقف آپلود سرور (nginx) از پنل

**تصمیم کاربر (۱۴۰۵/۰۸/۱۱):** سقف آپلود nginx از پرتال کنترل شود.

- **محل:** «تنظیمات سامانه ← سقف آپلود سرور». فقط ادمین کل؛ API: `GET/PUT /api/v1/system/upload-limit`.
- **ذخیره:** `system_settings.server.upload_limit_mb` (پیش‌فرض ۲۵، بازه‌ی ۲ تا ۲۰۴۸) و فایل `/var/lib/faipco/upload-limit-mb`.
- **اعمال:** `scripts/nginx-upload-limit.sh apply` در Unit موقت `faipco-upload-limit` (systemd-run، root، قانون sudoers ثابت بدون
  آرگومان متغیر در install.sh). اسکریپت مقدار را از فایل می‌خواند و اعتبارسنجی می‌کند، `/etc/nginx/faipco-upload-limit.conf`
  (`client_max_body_size Nm;`) را می‌نویسد، `nginx -t` و `systemctl reload nginx` را اجرا می‌کند؛ اگر تست رد شود، فایل قبلی برمی‌گردد.
  لاگ: `/var/log/faipco-upload-limit.log` با `[UPLOAD-LIMIT] START/RESULT`.
- **install.sh:** تنظیم nginx پرتال به‌جای عدد ثابت `include /etc/nginx/faipco-upload-limit.conf;` دارد. فایل فقط اگر وجود نداشته
  باشد ساخته می‌شود (از مقدار پنل، وگرنه ۲۵)؛ آپدیت مقدار تعیین‌شده را حفظ می‌کند.
- **اثر روی اتوماسیون:** سقف حجم هر فایل در تنظیمات پیوست = این مقدار منهای ۱ مگابایت (سربار فرم آپلود)
  (`server_upload_limit.portal_max_file_mb`؛ جای متغیر قبلی `OA_SERVER_MAX_FILE_MB`). اگر سقف سرور پایین آورده شود، آپلود با
  کمترینِ تنظیم سایت و سقف سرور سنجیده می‌شود.
- reverse proxy بیرونی در حالت Transparent سقفی ندارد؛ سقف واقعی همین nginx داخلی است.
- پنل مقدار ثبت‌شده و مقدار واقعی nginx را کنار هم نشان می‌دهد و ناهم‌خوانی را هشدار می‌دهد.
