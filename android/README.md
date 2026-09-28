# اپ اندروید FAIPCO

پرتال داخل Chrome تمام‌صفحه (TWA) + بخش بومی Geofencing برای ثبت خودکار ورود و خروج. توضیح کامل طراحی در
`docs/android-app.md` مخزن پرتال است.

## راه‌اندازی یک‌باره (بدون نصب هیچ برنامه‌ای روی کامپیوتر)

### ۱. ساخت مخزن خصوصی
1. در GitHub روی **New repository** بزنید، نام مثلاً `faipco-android`، حتماً **Private**.
2. محتوای همین پوشه (`android/`) را در ریشه‌ی مخزن بارگذاری کنید: در صفحه‌ی مخزن **Add file ← Upload files**، همه‌ی فایل‌ها و پوشه‌ها را بکشید و **Commit** کنید.
   پوشه‌ی `.github` مخفی است؛ در ویندوز از «View ← Hidden items» نمایشش دهید تا جا نماند.

### ۲. ساخت کلید امضا (فقط یک‌بار)
1. تب **Actions** ← workflow به نام **Create signing key** ← **Run workflow**.
2. بعد از اتمام (حدود ۱ دقیقه)، روی همان اجرا بزنید و از بخش **Artifacts** فایل `signing-key-DELETE-AFTER-USE` را دانلود کنید.
3. داخلش `README-SECRETS.txt` هست. در **Settings ← Secrets and variables ← Actions ← New repository secret** این چهار Secret را بسازید:
   - `KEYSTORE_BASE64`: کل متن فایل `KEYSTORE_BASE64.txt`
   - `KEYSTORE_PASSWORD`: رمز داخل README
   - `KEY_ALIAS`: `faipco`
   - `KEY_PASSWORD`: همان رمز
4. **اثر انگشت SHA-256** را در پرتال وارد کنید: «حضور و غیاب ← گوشی‌ها و اپ اندروید ← تنظیمات و نسخه‌ها». بدون این، اپ با نوار آدرس مرورگر باز می‌شود.
5. فایل `faipco-release.jks` و رمز را **جای امن بیرون از GitHub** نگه دارید (مثلاً فلش یا Password Manager). بعد Artifact را از صفحه‌ی اجرا حذف کنید.
   ⚠️ اگر این کلید گم شود، نسخه‌های بعدی روی نسخه‌ی نصب‌شده نصب نمی‌شوند و همه باید اپ را حذف و دوباره نصب کنند.

### ۳. ساخت APK
- با هر تغییر در شاخه‌ی `main` خودکار ساخته می‌شود؛ یا دستی: **Actions ← Build APK ← Run workflow**.
- در صفحه‌ی اجرا، versionCode و versionName نوشته شده و فایل APK در **Artifacts** است (داخل یک zip).

### ۴. انتشار برای پرسنل
در پرتال: «گوشی‌ها و اپ اندروید ← تنظیمات و نسخه‌ها ← انتشار نسخه‌ی جدید» فایل APK را با همان versionCode و versionName
بارگذاری کنید. از آن لحظه:
- کاربران اندروید در پرتال نوار «نصب اپ» می‌بینند و از خود پرتال دانلود می‌کنند.
- صفحه‌ی «اپ اندروید» (منوی کاربر) مراحل نصب را توضیح می‌دهد.

## تغییر دامنه
اگر آدرس پرتال `portal.faipco.ir` نیست، در `gradle.properties` مقدار `portalHost` را عوض کنید و دوباره بسازید.

## ساختار کد
| فایل | کار |
|---|---|
| `MainLauncherActivity.kt` | باز کردن پرتال در TWA با `?source=android-app` |
| `DelegationService.kt` | اعلان‌های پرتال با نام اپ |
| `SetupActivity.kt` | اتصال گوشی به حساب (`faipco://pair`) و راهنمای دسترسی‌ها (`faipco://setup`) |
| `GeofenceController.kt` | ثبت محدوده‌ها: Geofencing گوگل، یا موتور داخلی اندروید در گوشی‌های بدون سرویس گوگل |
| `GeofenceReceiver.kt` | لحظه‌ی ورود/خروج: ذخیره در صف |
| `Work.kt` | ارسال صف، همگام‌سازی محدوده‌ها و گزارش روزانه (WorkManager) |
| `BootReceiver.kt` | ثبت دوباره‌ی محدوده‌ها بعد از ری‌استارت گوشی |
| `Api.kt` / `Prefs.kt` / `DeviceState.kt` | ارتباط با سرور، حافظه‌ی رمزشده، وضعیت دسترسی‌ها |
