# بازبینی امنیتی — ۱۴۰۵/۰۷/۱۳ (۵ اکتبر ۲۰۲۶)

بازبینی ایستا (بدون اجرا) با سه بازبین مستقل: (۱) احراز هویت و توکن، (۲) مجوزها و IDOR، (۳) تزریق و زیرساخت.
قید طراحی: رفع‌ها نباید تجربه‌ی کاربر عادی را سخت کنند.

## وضعیت رفع (همان روز)
همه‌ی موارد بحرانی، بالا و متوسط (به‌جز M11) و L1، L3، L5، L7، L9، L10 رفع شدند. Migration 101 (`users.password_changed_at`) و
102 (`password_reset_tokens.attempts`، hash شدن کد، حذف unique). بازبینی مستقل بعد از رفع، سه رگرسیون پیدا کرد که اصلاح شد:
- IP کلاینت پشت پراکسی خارجی: `get_client_ip` زنجیره‌ی XFF را از راست به چپ می‌پیماید و پراکسی‌های معتبر
  (`REVERSE_PROXY_IP` در `.env` + loopback) را رد می‌کند؛ بدون آن، همه‌ی کاربران پشت SSL Terminator یک IP می‌شدند.
- Sync: پرسنلی که دوباره فعال می‌شود حساب User اش هم فعال می‌شود (`_reactivate_linked_users`؛ مگر Admin دستی غیرفعال کرده باشد).
- Geofence اپ: رویداد «خروج» طبق تعریف بیرون حصار است و می‌تواند بدون مختصات باشد → فقط زمان بررسی می‌شود؛ سقف قدمت
  رویداد ۴۸ ساعت (صف آفلاین WorkManager) به‌جای ۱۵ دقیقه.
تنها اثر محسوس روی کاربر: هنگام تغییر موبایل/ایمیل، رمز فعلی (یا کد ملی برای ورود پیش‌فرض) پرسیده می‌شود.
نکته‌ی گذار: توکن‌های صادرشده‌ی قبل از این نسخه `iat` ندارند و تا انقضای طبیعی (حداکثر ۳۰ روز Refresh) با تغییر رمز باطل نمی‌شوند؛
اولین Refresh بعد از نصب توکن جدید با `iat` می‌دهد.
انجام‌نشده: M11 (lockfile فرانت‌اند — نیاز به `npm install` روی ماشین Build)، L2، L4، L6 (کد hash شد ولی توکن ایمیل هم hash شد ✓)، L8، L11.

## بحرانی
| # | یافته | محل | رفع (بدون اثر روی کاربر) |
|---|---|---|---|
| C1 | هر پرسنل واردشده با `GET /employees` کد ملی و `has_custom_password` همکاران سایت خودش را می‌بیند؛ ورود پیش‌فرض = کد پرسنلی + کد ملی ⇒ ورود به حساب HR/سرپرست‌ها | `endpoints/employees.py:68-196`، `schemas/employee.py` | حذف `national_code`، `mobile`، `has_custom_password` از خروجی برای کسی که `employees.view` ندارد؛ حذف کد ملی از `search` برای او |
| C2 | IP کلاینت از اولین مقدار `X-Forwarded-For` خوانده می‌شود و nginx نصب‌شده با `$proxy_add_x_forwarded_for` مقدار کلاینت را حفظ می‌کند ⇒ همه‌ی کنترل‌های IP (قفل ورود، کپچا، محدودیت بازیابی رمز، IP مجاز، IP معاف) با یک هدر دور می‌خورد | `core/ip_allowlist.py:27-34`، `install.sh:606,645,709` | `X-Real-IP` (که nginx با `$remote_addr` جایگزین می‌کند) مقدم؛ وگرنه آخرین عضو XFF؛ `request.client.host` در نبود پراکسی |
| C3 | کد پیامکی بازیابی رمز ۶ رقمی، جست‌وجو فقط با کد (بدون کاربر)، بدون شمارنده‌ی تلاش روی کد؛ تنها محدودیت per-IP است (C2) ⇒ brute-force و تصاحب حساب | `password_reset_service.py:175,253,269`، `endpoints/auth.py:216-281` | کد به کاربر بسته شود (identifier از همان صفحه‌ی فعلی فرستاده می‌شود)، ۵ تلاش ناموفق = ابطال کد، ذخیره‌ی hash کد |

## بالا
| # | یافته | محل | رفع |
|---|---|---|---|
| H1 | `must_change_password` فقط در فرانت‌اند اعمال می‌شود؛ با API مستقیم (مثلاً admin/admin اولیه یا ورود پیش‌فرض) بدون تغییر رمز کار می‌شود | `core/deps.py`، `MandatoryPasswordChangeGuard.jsx` | در `get_current_user` به‌جز `/auth/me`، `/auth/me/password`، `/auth/refresh` خطای 403 |
| H2 | توکن‌ها باطل نمی‌شوند: تغییر رمز، ریست ادمین، غیرفعال شدن، خروج ⇒ Refresh ۳۰روزه و لغزنده همیشه معتبر | `security.py:94-110`، `auth_service.py:182-235` | `password_changed_at` روی User + `iat` در توکن؛ رد توکن قدیمی‌تر از آن در `get_current_user`/`refresh` (بدون کوئری اضافه) |
| H3 | پرسنلِ غیرفعال‌شده با Sync کاراوب (ترک‌کار) اگر رمز شخصی داشته باشد هنوز وارد می‌شود؛ `Employee.is_active` در `get_current_user` چک نمی‌شود | `sync_service.py`، `deps.py:60`، `auth_service.py:91-109` | چک `Employee.is_active/is_enabled` در همان کوئری کاربر؛ Sync هم `User.is_active` را خاموش کند |
| H4 | `users.manage` ⇒ ادمین کامل: ساخت نقش با مجوزهای `system.*`، انتصاب به خودِ خود؛ ست کردن رمز برای حساب‌های بالاتر (حتی superuser) | `endpoints/users.py:137-317`، `employees.py:759-814`، `user_management_service.py:417-470` | رد `system.*` و مجوزهایی که خود ندارد؛ ممنوعیت انتصاب به خود؛ ممنوعیت ست رمز برای هدفِ با مجوز بیشتر/superuser |
| H5 | نام جدول/ستون نگاشت‌ها (پرسنل/تردد/مرخصی) اعتبارسنجی نمی‌شوند؛ `]` یا backtick از `_quote` خارج می‌شود ⇒ SQL Injection روی کاراوب با مجوز `sites.manage` سایتی | `schemas/site.py`، `schemas/leave_request.py`، `_quote` ها | همان `_SAFE_NAME` که `kara_schema` دارد روی همه‌ی فیلدهای نام + escape جداکننده در `_quote` |

## متوسط
| # | یافته | محل | رفع |
|---|---|---|---|
| M1 | رویدادهای Geofence اپ اندروید سمت سرور با شعاع سایت مقایسه نمی‌شوند؛ `occurred_at` تا ۳ روز عقب پذیرفته می‌شود ⇒ جعل ورود/خروج | `mobile_app_service.py:394-475` | رد اگر مختصات نیست یا فاصله > شعاع+دقت؛ سقف عقب‌تاریخ ۱۵ دقیقه |
| M2 | تنظیمات سراسری بیمه و خانواده با مجوز سایتی قابل تغییر است | `family.py:177`، `insurance.py:165` | گارد «مجوز برای همه‌ی سایت‌ها» مثل `hr.py` |
| M3 | تغییر موبایل/ایمیل (کانال بازیابی رمز) بدون رمز فعلی | `auth.py:147-162` | رمز فعلی فقط وقتی موبایل/ایمیل عوض می‌شود |
| M4 | شمارش کاربر از `/forgot-password` (زمان باقی‌مانده‌ی متفاوت، تأخیر ارسال پیامک، 503 در خطای SMS) و زمان ورود (bcrypt فقط برای نام موجود) | `password_reset_service.py:150-206`، `auth_service.py:102` | TTL کامل همیشه؛ ارسال SMS/ایمیل در پس‌زمینه؛ bcrypt ساختگی برای نام ناموجود |
| M5 | `/forgot-password` بدون سقف per-IP ⇒ SMS bombing به همه‌ی پرسنل هر ۵ دقیقه | `auth.py:174-193` | شمارنده‌ی per-IP (بعد از C2 معنادار) |
| M6 | کد لینک اپ (`POST /mobile/link`) اگر از قبل به کاربری وصل باشد به کاربر جدید منتقل می‌شود ⇒ گوشی قربانی برای مهاجم تردد می‌زند | `mobile_app_service.py:196-217` | عدم تغییر `user_id` اگر قبلاً ست شده |
| M7 | لوگوی SVG بدون پاک‌سازی و با Content-Type کلاینت در همان Origin سرو می‌شود (CSP فعلی اسکریپت را می‌بندد) | `system.py:398,504-540` | هدر `CSP: sandbox` + `nosniff` روی `/logo/*` یا حذف `<script>`/`on*` |
| M8 | اسکریپت بازگردانی بکاپ با رمز Postgres در `/tmp`؛ رمز smbclient در argv؛ `"` در مسیر SMB تزریق دستور | `backup_service.py:245-310`، `remote_backup_service.py:89-167` | `PGPASSWORD`، فایل زیر مسیر نصب با 0700، `--authentication-file`، اعتبارسنجی مسیر |
| M9 | Excel فیش/کارت بدون `read_only=True` ⇒ zip-bomb حافظه | `payroll_xlsx.py:182`، `attendance_card_xlsx.py:169` | `read_only=True` |
| M10 | `python-jose 3.3.0` (CVE-2024-33663/33664؛ اینجا با HS256 پین‌شده عملاً خنثی) | `requirements.txt` | مهاجرت به PyJWT |
| M11 | بدون `package-lock.json`؛ `npm install` در نصب ⇒ Build غیرقابل‌تکرار | `install.sh:446` | commit lockfile + `npm ci` |

## کم
L1 `POST /notices/{id}/read` بدون چک مخاطب (و 500 برای id ناموجود) · L2 توکن WebSocket در query string (لاگ nginx) · L3 `/sync/status-summary` همه‌ی سایت‌ها برای مجوز سایتی · L4 متن خطای خام کاراوب در گزارش مرخصی · L5 `extractall` بکاپ بدون سقف حجم · L6 کد/توکن بازیابی به‌صورت متن ساده در DB · L7 `SECRET_KEY` بدون اعتبارسنجی مقدار placeholder · L8 قفل identifier با ۳ تلاش = DoS ساده‌ی حساب دیگران · L9 مقایسه‌ی کد ملی غیر constant-time · L10 `ElementTree` به‌جای `defusedxml` · L11 `TrustedHostMiddleware` ندارد.

## تأییدشده‌ها (مشکلی نداشتند)
JWT با الگوریتم پین‌شده و تفکیک access/refresh؛ bcrypt (cost 12) و رمز تصادفی برای پرسنل Sync‌شده؛ سیاست رمز سمت سرور؛ کپچای یک‌بارمصرف با HMAC؛ CORS بدون credentials؛ Swagger خاموش در Production؛ هیچ رمز/توکنی لاگ نمی‌شود؛ همه‌ی مقادیر SQL کاراوب پارامتری (اعداد `_build_report_where` با `int()`)؛ هیچ `text()` تزریق‌پذیر در Postgres؛ هیچ `dangerouslySetInnerHTML`؛ Service Worker پاسخ API را کش نمی‌کند؛ رمز اتصال سایت‌ها Fernet؛ CSP/HSTS/X-Frame-Options در nginx؛ APK با امضا و سقف حجم؛ sanitizer مدارک با محافظت decompression-bomb؛ مجوزدهی سایت‌محور در notices/insurance/family/employees/users/attendance/leave/evaluation/vehicles/mobile/feedback/sites/departments/hr/turnover درست.
