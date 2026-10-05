# سرعت بارگذاری داده‌ها

## چه چیزی کند بود

- **جدول گزارش تردد ماهانه و گزارش ورود/خروج دو بار از سرور گرفته می‌شد.** صفحه اول «ماه جاری» را می‌خواست و بعد از پاسخ، با ماه برگشتی سرور دوباره همان را می‌خواست.
- **گزارش ماهانه سه منبع دیتابیس سایت را پشت سر هم می‌خواند.** این سه منبع ترددهای خام، تعطیلات و لایه‌ی کاراوب هستند و هر کدام اتصال تازه‌ی SQL Server باز می‌کنند.
- **داشبورد همان گزارش ماهانه را برای «تردد امروز» می‌گرفت.** جابه‌جایی داشبورد ← گزارش ← داشبورد چندین بار همان کوئری‌ها را اجرا می‌کرد.
- **سمت کلاینت هیچ Cache ای نبود.** با هر ورود به صفحه همه‌چیز از صفر بارگذاری می‌شد: اطلاعیه‌ها، متولدین، عکس‌ها، درخواست‌های مرخصی و گزارش.
- **WebSocket حضور، اتصال دیتابیس را نگه می‌داشت.** وقتی کاربر خارج از محدوده‌ی GPS بود، اتصال تا قطع Socket در حالت idle in transaction از Pool گرفته می‌ماند. با چند ده کاربر، Pool پر می‌شد و بقیه‌ی درخواست‌ها منتظر می‌ماندند.
- **واترمارک عکس تولد حلقه‌ی async را قفل می‌کرد.** این پردازش Pillow داخل همان حلقه اجرا می‌شد.
- **همه‌ی صفحات در یک باندل JS بودند.** Nginx هم JS/CSS/JSON را فشرده نمی‌کرد.

## تغییرات

| بخش | تغییر |
|---|---|
| `MonthlyAttendanceReportPage`، `ClockInOutReportPage` | حذف درخواست تکراری؛ پاسخ درخواست قدیمی (تغییر سریع ماه) نادیده گرفته می‌شود |
| `monthly_attendance_service` | خواندن هم‌زمان سه منبع با `asyncio.gather`؛ Cache داده‌ی خام به مدت ۳۰ ثانیه در هر worker |
| `frontend/src/api/swrCache.js` | Cache حافظه‌ی تب به روش stale-while-revalidate: داده‌ی قبلی فوراً نمایش داده می‌شود و پاسخ تازه جایگزینش می‌شود. با تغییر کاربر (`AuthContext`) کاملاً پاک می‌شود. در localStorage ذخیره نمی‌شود. |
| داشبورد شخصی | اطلاعیه‌ها، متولدین، شمارنده‌ی کارتابل، عکس پرسنلی و تردد امروز از Cache. داشبورد و صفحه‌ی گزارش ماهانه یک کلید مشترک دارند. |
| `EmployeeAvatar` | عکس‌های تولد تا ۱۰ دقیقه از Cache |
| صفحه‌ی مرخصی/ماموریت | انواع، درخواست‌های من، کارتابل و تعداد سوابق از Cache |
| `/employees/{id}/photo-thumbnail` | `Cache-Control: private, max-age=600` |
| `/employees/birthday-photo/{id}` | واترمارک در `asyncio.to_thread` |
| WebSocket حضور | بعد از Heartbeat خارج از محدوده، تراکنش rollback و اتصال به Pool برمی‌گردد |
| `App.jsx` | صفحات تنبل (`React.lazy`) با بازخوانی خودکار یک‌باره در صورت chunk قدیمی (`utils/lazyPage.js`) |
| `install.sh` | gzip برای JS/CSS/JSON/SVG |

## اعمال gzip روی سرور موجود

`install.sh` روی سرور نصب‌شده دوباره اجرا نمی‌شود. این خطوط را داخل بلوک `server { ... }` فایل `/etc/nginx/sites-available/faipco-portal` اضافه کنید، مثلاً زیر `client_max_body_size`:

```
    gzip on;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_vary on;
    gzip_types text/plain text/css application/javascript application/json application/manifest+json image/svg+xml;
```

سپس `sudo nginx -t && sudo systemctl reload nginx` را اجرا کنید. این خطوط را در `conf.d` نگذارید؛ `gzip on` در nginx.conf دبیان هست و تکرارش در همان سطح خطا می‌دهد.

## باقی‌مانده (نیاز به تغییر بیشتر)

- `pending-count` و «تعداد سوابق تصمیم» مرخصی برای شمارش، کل فهرست را از کاراوب می‌سازند. بهتر است با `COUNT(*)` و صفحه‌بندی SQL انجام شوند.
- ایندکس‌های کاراوب روی `DataFile(emp_no, date)`، `WF_Requests(CurEmpNo)` و `daily_work(emp_no, date)` باید روی خود SQL Server بررسی شوند.

## دور بهینه‌سازی زمان پاسخ (۱۴۰۵/۰۷)

هدف: هیچ درخواست ثبت/بارگذاری منتظر کار کند خارجی یا مسدودکننده نماند (uvicorn با ۲ Worker اجرا می‌شود؛ یک فراخوان
همگام در `async def` نیمی از کاربران هم‌زمان را معطل می‌کند).

- **Push همیشه در پس‌زمینه** (`app/services/push_background.py` → `schedule_push`): انتقادات و پیشنهادات (پیام/پاسخ)،
  ری‌اکشن تولد، ثبت ارزیابی، «ارسال دوباره‌ی Push» اطلاعیه، هشدار امنیت ورود. اطلاعیه‌ها از قبل با BackgroundTasks بودند.
  هم‌گام‌سازی وضعیت دوره‌ها بعد از ثبت ارزیابی هم پس‌زمینه شد.
- **کارهای مسدودکننده در Thread** (`asyncio.to_thread`): PDF فیش حقوقی/کارکرد، پارس Excel/XML فیش و کارت، کپچا و آیکون
  PWA (PIL)، همه‌ی خروجی‌های Excel (مرخصی، ارزیابی، بیمه، خانواده)، ورود Excel سابقه بیمه، تست SMB/FTP بکاپ و
  وضعیت‌های subprocess (آپدیت/بازگردانی).
- **ستون‌های Blob با `deferred=True`**: `Employee.photo_thumbnail`، `FamilyDocument.data`، `InsuranceDocument.data`،
  `MobileAppRelease.data` در فهرست‌ها بارگذاری نمی‌شوند؛ فقط endpoint دانلود/نمایش با `undefer` می‌خواند. `has_photo` با
  عبارت SQL `isnot(None)` حساب می‌شود. (در async، خواندن ستون deferredِ بارنشده MissingGreenlet می‌دهد — هر read جدید
  باید undefer داشته باشد.)
- **استخر اتصال کاراوب** (`app/core/kara_pool.py`): مرخصی، گزارش تردد ماهانه و لایه‌ی تردد کاراوب دیگر برای هر فراخوان
  Login جدید به SQL Server نمی‌زنند؛ `close()` اتصال را بعد از rollback به استخر برمی‌گرداند (حداکثر ۴ بی‌کار به‌ازای
  هر مقصد، انقضا ۵ دقیقه، آزمایش `SELECT 1` قبل از تحویل).
- **N+1 ها**: مخاطب‌های اطلاعیه (`_resolve_audience_user_ids`، `get_available_targets`، `notice_reaches_any_site`) با یک
  IN به‌ازای هر نوع؛ `save_answers` ارزیابی با دو IN؛ شمارنده‌ی پاسخ‌های دیده‌نشده‌ی انتقادات با یک COUNT؛ ثبت تردد GPS
  یک بار Geofence را حساب می‌کند و refresh های بعد از commit حذف شدند.
- **`/auth/me`**: Employee یک بار (در Join اصلی) خوانده می‌شود و تنظیمات سیستم با یک کوئری پیش‌بارگذاری می‌شوند.
- **آمار استفاده**: به‌جای یک Session + UPSERT برای هر درخواست، شمارنده‌ی در حافظه‌ی هر Worker و flush هر ۶۰ ثانیه
  (و در خاموش شدن). دو Middleware در یکی ادغام شدند.
- **قفل Job های زمان‌بند** (پیش‌زمینه‌ی مشکل قدیمی): Advisory Lock روی یک اتصال اختصاصی از Engine گرفته و تا unlock نگه
  داشته می‌شود؛ قبلاً روی Session بود و با اولین commit بدنه‌ی Job، قفل روی اتصال رهاشده در Pool می‌ماند و تیک‌های بعدی
  (Sync خودکار، آمار سرور، بکاپ، …) رد می‌شدند.

باقی‌مانده (انجام نشده): `list_all_for_site` مرخصی هنوز کل WF_Requests را می‌خواند و در پایتون فیلتر می‌کند؛
`notice_service.list_all` بدون صفحه‌بندی همه‌ی مخاطب‌ها را بارگذاری می‌کند؛ `family_service.list_profiles` بدون صفحه‌بندی.
