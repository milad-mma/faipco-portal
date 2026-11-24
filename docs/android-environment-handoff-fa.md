# رفع دائمی نوار آدرس Android TWA و تفکیک محیط تست/اصلی

## مبنا و محدوده
- مبنا: بسته کامل `faipco-portal-bb9174b-push-reliability-full.zip` (نسخه اصلاح‌شده اعلان، Migration 154؛ نسخه پایه Git: bb9174b). هیچ فایل از بسته قبلی حذف نشده است.
- هدف: حل بازگشت نوار آدرس بعد از انتشار/Restart؛ انتخاب صحیح APK برای باز کردن پرتال، بررسی دسترسی‌ها و اتصال دستگاه. این اصلاحیه جدا از تغییرات گسترده یکپارچه‌سازی Android است.
- صف اعلان‌ها، Service Worker، منطق نشست Push، Migration 154، Installer، Reverse Proxy، تنظیمات کلید VAPID و سورس APK تغییر نکرده‌اند. Migration جدید ندارد. این بسته برای Commit از طریق GitHub Desktop است؛ نه جایگزینی فایل‌های عملیاتی روی سرور.

## علت مشکل
APK تست با `ir.faipco.portal.test` امضا/نصب می‌شود و `portal-test.faipco.ir` را باز می‌کند، ولی Backend در هر startup و ذخیره تنظیمات، شناسه ثابت `ir.faipco.portal` را در `assetlinks.json` می‌نوشت. همچنین محافظ خروجی Vite فقط package اصلی را معتبر می‌دانست. Frontend نیز برای referrer و intent از package/scheme اصلی استفاده می‌کرد؛ بررسی startsWith حتی می‌توانست package تست را به اشتباه در محیط اصلی بپذیرد.

## قرارداد دو محیط
| محیط | FRONTEND_URL | Android package | Native scheme |
|---|---|---|---|
| اصلی | https://portal.faipco.ir | ir.faipco.portal | faipco |
| تست | https://portal-test.faipco.ir | ir.faipco.portal.test | faipco-test |

Backend hostname را از `get_settings().FRONTEND_URL` می‌خواند، نه Host درخواست یا نام ماشین. فقط تطابق کامل hostname تست به package تست منتهی می‌شود؛ سایر hostnameها برای حفظ سازگاری با نصب‌های قبلی package اصلی را نگه می‌دارند. Frontend همین قرارداد را با `window.location.hostname` پیاده می‌کند. کلید SHA-256 از تنظیمات `mobile_app` در دیتابیس همان سرور گرفته می‌شود (همان مقدار موجود). هیچ fingerprint واقعی یا کلید خصوصی در سورس درج نشده است. درست بودن مقدار FRONTEND_URL و fingerprint دو پیش‌شرط هستند؛ در صورت نبود fingerprint، برنامه association ساختگی ایجاد نمی‌کند.

## فایل‌های تغییرکرده و علت
| فایل | تغییر |
|---|---|
| `backend/app/core/android_assetlinks.py` (جدید) | انتخاب package با parsing دقیق URL و تولید JSON؛ نوشتن اتمیک، مجوز 0644 و امکان استفاده از dist symlink؛ بدون وابستگی DB |
| `backend/app/services/mobile_app_service.py` | استفاده از تنظیمات همان محیط، حفظ اثر انگشت موجود، استفاده از helper مشترک در تولید فایل و ذخیره تنظیمات |
| `backend/app/main.py` | جدا کردن همگام‌سازی assetlinks از موفقیت برندینگ HTML، در startup و hook موجود انتشار |
| `frontend/src/utils/androidEnvironment.js` (جدید) | mapping هماهنگ hostname، package و scheme؛ تطابق کامل referrer به‌جای prefix |
| `frontend/src/utils/androidApp.js` | استفاده از mapping در تشخیص TWA، native pairing/setup و بازکردن پرتال داخل اپ؛ محدودیت sessionStorage و کنترل کد اتصال حفظ شده است |
| `frontend/scripts/preserveAssetLinks.mjs` | پذیرش association معتبر یک محیط (اصلی یا تست) و حفظ آن در Build مستقیم؛ رد fingerprint نمونه و association ترکیبی؛ فایل جدید معتبر را بازنویسی نمی‌کند |
| `frontend/public/.well-known/assetlinks.json` | تبدیل placeholder ثابت package اصلی به `[]` (بدون اعتماد به اپ یا fingerprint ساختگی) |
| `backend/tests/test_android_assetlinks.py` (جدید) | تست mapping، خواندن واقعی .env، تولید بدون fingerprint، تکرارپذیری، اصلاح association قدیمی، و انتشار دو نسخه با اسکریپت واقعی activation؛ تست اتصال helper به سرویس |
| `frontend/tests/androidEnvironment.test.mjs` (جدید) | تست mapping، referrer متقاطع و intentهای setup/pair/open در هر محیط |
| `frontend/tests/assetlinksPreservation.test.mjs` | تست حفظ association تست بعد از Build و رد association ترکیبی |
| `docs/android-app.md` | مستند اصلاح قرارداد و عیب‌یابی |
| `docs/android-app-twa.md` | مستند placeholder خالی و نام package تست |
| `docs/android-environment-handoff-fa.md` (جدید) | این سند برای تحویل به Claude |

## انتشار استاندارد
۱. Commit/Push سورس کامل در GitHub Desktop. از `git add .` روی سرور و کپی `.env` یا `dist` به Git خودداری شود. ابتدا تست، سپس Tag انتشار برای اصلی. اگر main تغییرات دیگری دارد ابتدا ادغام/بررسی شوند؛ نسخه قدیمی جایگزین main جدید نشود.
۲. روی سرور موجود، بررسی بدون افشای اسرار:

```bash
grep -E '^(FRONTEND_URL|UPDATE_CHANNEL)=' /var/www/html/backend/.env
```

۳. Installer کانال انتشار را از UPDATE_CHANNEL می‌خواند (branch=main، tag=آخرین تگ؛ این کانال مستقل از package است). تنظیمات موجود FRONTEND_URL و کلیدها را نگه می‌دارد. برای پرهیز از مسیر استفاده از سورس محلی در Installer فعلی، فرمان از خارج پوشه مخزن اجرا شود:

```bash
cd /root
curl -fsSL https://raw.githubusercontent.com/milad-mma/faipco-portal/main/install.sh | sudo bash
```

۴. Installer فعلی سورس مقصد را می‌گیرد، dependency/Migration را اجرا می‌کند، Frontend را در staging می‌سازد و Backend را Restart می‌کند. در startup، فایل association در dist فعال براساس FRONTEND_URL و fingerprint DB تولید/اصلاح می‌شود. اسکریپت `activate_frontend_release.py` فایل‌های .well-known نسخه جاری را به نسخه staged منتقل می‌کند و dist را عوض می‌کند. hook موجود `sync_index_html_branding` مجدداً association را در dist جدید همگام می‌کند، مستقل از خطای احتمالی branding. سپس رویداد انتشار منتشر می‌شود. هیچ منطق تشخیص جدیدی در install.sh لازم نیست.
۵. Nginx همین مسیر را با Content-Type مناسب و no-cache سرو می‌کند. پس از تأیید Digital Asset Links توسط Chrome، TWA می‌تواند بدون نوار آدرس باز شود. در صورت cache شدن شکست اعتبارسنجی ممکن است بستن و باز کردن اپ یا تجدید اعتبارسنجی Chrome لازم شود. این اصلاحیه مجوزهای اپ را تغییر نمی‌دهد.

در نصب تازه (بدون .env موجود)، دامنه باید با `--domain` یا `FAIPCO_DOMAIN` مشخص شود و SHA-256 صحیح در پنل ثبت شود. Installer نمی‌تواند از IP یا hostname سیستم دامنه عمومی را با قطعیت استنتاج کند. روی نصب موجود --domain برای تغییر FRONTEND_URL به‌طور خودکار استفاده نمی‌شود.

## آزمون‌ها و محدودیت‌ها
- اجرای `npm run test:unit`: 73 passed, 0 failed (شامل 65 تست نسخه Push قبلی و 8 تست جدید).
- اجرای `PYTHONPATH="$PWD" python -m pytest -q tests/test_android_assetlinks.py tests/test_release_activation.py` در backend: 14 passed, 1 skipped (asyncpg در محیط توسعه حاضر نصب نیست). در سرور با dependencyهای نصب‌شده، تست سرویس هم باید اجرا شود. از دیتابیس واقعی استفاده نشده؛ برای تست import فقط تنظیمات ساختگی استفاده می‌شوند.
- `bash -n install.sh`: موفق. Installer تغییر نکرده است.
- Build کامل Vite، اجرای واقعی Installer، بررسی HTTPS از اینترنت و آزمون واقعی گوشی پس از این اصلاحیه هنوز انجام نشده‌اند. آزمون انتشار دو نسخه با اسکریپت واقعی activation در پوشه موقت انجام شده است؛ نباید با آزمون کامل deployment اشتباه گرفته شود.

## معیار پذیرش روی سرور تست (پس از Push)

```bash
curl -fsS https://portal-test.faipco.ir/.well-known/assetlinks.json
```

باید فقط `ir.faipco.portal.test` و fingerprint صحیح APK تست در JSON وجود داشته باشد. یک Restart Backend و یک بروزرسانی استاندارد دیگر انجام شود؛ JSON نباید به package اصلی برگردد. در APK تست، باز کردن بدون آدرس‌بار، بخش بررسی دسترسی‌ها (باز کردن اپ تست نه اصلی) و دریافت اعلان جدید را تست کنید. سپس در نسخه اصلی همین معیار با `https://portal.faipco.ir/.well-known/assetlinks.json` و `ir.faipco.portal` برقرار باشد. قبل از انتشار اصلی، آزمایش نسخه و Migration از دیتابیس پیش از 154 در محیط ایزوله همچنان لازم است. اگر آدرس‌بار ماند، پاسخ HTTPS، تطابق SHA-256 APK نصب‌شده، دامنه، Cache و وضعیت DAL مرورگر بررسی شوند؛ از ویرایش دستی یا قرار دادن هر دو package در assetlinks خودداری شود.
