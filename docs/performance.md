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
