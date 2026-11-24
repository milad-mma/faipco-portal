# تحویل فنی اصلاحات اعلان FAIPCO به Claude

## ۱. مبنا و دامنه

- سورس مبنا: فایل `faipco-portal-main.zip`، کامیت GitHub ثبت‌شده در comment آرشیو: `bb9174bab9735187711999c8afbc166beed9aad8` (Bind push notifications to active sessions). سرور تست به گزارش کاربر: `v1.0.0-beta.29.3-11-gbb9174b`.
- مرجع مقایسه قدیمی: `faipco-portal-updated_274.zip`؛ در آن کنترل جدید `activePushSessionMarker` وجود ندارد. Tag دقیق این آرشیو از خود فایل قابل اثبات نیست. نسخه سالم اعلام‌شده سرور اصلی `v1.0.0-beta.29.3` است.
- این بسته یک پیشنهاد اصلاحی برای تست است؛ هیچ سرور، مخزن GitHub، Reverse Proxy، APK یا دیتابیس واقعی توسط ChatGPT تغییر داده نشده است. ۱۶ تغییر قبلی یکپارچه‌سازی Android/Portal خارج از دامنه هستند. تولید assetlinks و مسیرهای deep link اپ اصلی/تست هم تغییر نکرده‌اند.
- هدف: حفظ امنیت نشست نسخه جدید، رفع قطعی نمایش اعلان، کاهش احتمال گم‌شدن ارسال بر اثر restart/خطای موقت، گزارش قابل پیگیری. تضمین مطلق نمایش یا خواندن Web Push ممکن نیست.

## ۲. شواهد و علت‌های تغییر

1. روی سرور تست در `frontend/src/sw.js:102`، `get.onerror = () => reject(get.error)` به متغیر تعریف‌نشده اشاره می‌کند. Promise رد و `activePushSessionMarker` همیشه null می‌شود. شرط ابتدایی handler، Push را بدون نمایش رد می‌کند. `git blame` این خط را به bb9174b نسبت داده است. جایگزین: `tx.onerror` و `tx.onabort`. سیاست fail-closed باقی است.
2. کاربر ثبت اشتراک HTTP 204، VAPID عمومی و خصوصی موجود و مطابق، دسترسی به ریشه FCM با HTTP 404، و حذف نوار آدرس TWA پس از اصلاح assetlinks را گزارش کرد. اینها ثبت و اتصال را نشان می‌دهند، نه تحویل واقعی Push. مشکل SW مستقل از APK است.
3. در کد bb9174b، بعد از بررسی SID ممکن است نشست حین دریافت آیکون تغییر کند؛ بررسی دوباره پیش از claim و نمایش، و بستن اعلان قدیمی پس از اتمام showNotification اضافه شد. race با سیستم‌عامل را نمی‌توان کاملاً اتمیک کرد.
4. claim نامه قبل از showNotification ثبت می‌شد؛ خطای نمایش، retry همان کلید را برای همیشه سرکوب می‌کرد. اکنون claim بعد از آماده‌شدن آیکون ثبت و در صورت شکست نمایش آزاد می‌شود. موفقیت قبلی حفظ می‌شود. برای صف جدید کلید dispatch با SID ترکیب شده، تا retry یک نشست تکرار نشود و نشست دیگری که تازه ثبت شده ناخواسته حذف نشود. کلید قدیمی OA حفظ شده است. دریافت آیکون بیش از ۱.۵ ثانیه نمایش را معطل نمی‌کند.
5. ثبت اشتراک قدیمی در Layout فقط هنگام mount و عمدتاً با تکیه بر مجوز مرورگر بود. اکنون وضعیت ثبت واقعی برای نشست جاری نگهداری، اشتراک هم‌زمان single-flight و در صورت تفاوت قابل تشخیص VAPID بازسازی می‌شود. انتظار SW ready حداکثر ۱۵ ثانیه؛ بررسی هنگام reconnect/resume/controllerchange و هر ۱۵ دقیقه در صفحه visible. retry خطا: ۱۰،۳۰،۶۰،۳۰۰ ثانیه. هیچ prompt خودکار پس‌زمینه‌ای اضافه نشده است. API subscribe، SID مورد انتظار اختیاری را با نشست احرازشده مقایسه و در تعارض 409 می‌دهد (کلاینت قدیمی بدون این فیلد پذیرفته می‌شود).
6. انتشار اطلاعیه/فیش معمولاً در تراکنش اصلی ثبت می‌شد، اما ارسال Push بعد از پاسخ در BackgroundTask بود. با توقف process در فاصله commit و اجرای task، ارسال از دست می‌رفت. برای این مسیرها Outbox در همان تراکنش ثبت شده و I/O شبکه به scheduler واگذار شده است. OA از قبل outbox مستقل داشته؛ آن را جایگزین نکردیم.
7. خطای شبکه و اشتراک نامعتبر باید تفکیک شوند؛ برای 404/410 فقط ثبت دقیق ردشده حذف می‌شود (subscription id/session/user/keys؛ نه اشتراک تازه بازثبت‌شده). لاگ‌ها فاقد URL کامل endpoint و auth/p256dh هستند. کلید خصوصی VAPID چاپ نمی‌شود.

## ۳. قرارداد صف جدید

Migration `154_push_dispatch_outbox.py` بعد از `153`، فقط دو جدول و ایندکس اضافه می‌کند:
- `push_dispatch_jobs`: key یکتا، origin (`FRONTEND_URL`)، شناسه اطلاعیه یا رویداد عمومی، گیرندگان، زمان تلاش بعدی، deadline، وضعیت خلاصه، تعداد هدف و کاربران بدون پوشش، خطا. برای اطلاعیه‌ها متن و محتوای فیش ذخیره نمی‌شود؛ متن عمومی سفارشی فقط تا وضعیت نهایی نگهداری می‌شود. هیچ endpoint/key خصوصی در جدول صف ذخیره نمی‌شود. تاریخچه ممکن است حاوی شناسه افراد باشد و فقط باید در دسترس مدیر فنی مجاز باشد.
- `push_dispatch_deliveries`: هر job و جفت subscription/session یکتا، user_id، تعداد تلاش، وضعیت، next_attempt_at، accepted_at، error. FK تاریخچه به اشتراک/نشست ندارد تا حذف ثبت قدیمی تاریخچه را پاک نکند؛ حذف فیزیکی notice موجب cascade job/delivery می‌شود.
- انتشار اولیه کلید ثابت `dispatch:notice:<id>:publish` و INSERT ON CONFLICT DO NOTHING دارد. ارسال مجدد صریح مدیر، event جدید با UUID می‌سازد؛ تعداد پاسخ API تعداد کاربران هدف صف است، نه تحویل موفق. موعد انتشار آینده رعایت می‌شود. در اولین پردازش فهرست گیرندگان تعیین/ثبت می‌شود (نه snapshot قطعی لحظه ایجاد). در retry اطلاعیه دوباره اعتبار، خوانده‌نشدن و مخاطب بودن بررسی می‌شوند. نشست باطل/منقضی یا پرسنل غیرفعال ارسال نمی‌گیرند.
- `FOR UPDATE SKIP LOCKED` از پردازش هم‌زمان یک job در چند worker جلوگیری می‌کند. Scheduler هر ۵ ثانیه، حداکثر ۱۲ job/batch در هر اجرا، هر batch حداکثر ۲۰ دستگاه. I/O شبکه در thread و با timeout قبلی ۱۵ ثانیه انجام می‌شود. نتیجه پذیرفته‌شده به صورت accepted ذخیره می‌شود؛ accepted به طور عادی دوباره ارسال نمی‌شود. خطای موقت از ۳۰ ثانیه با backoff نمایی تا ۶ ساعت، حداکثر ۳۲ تلاش و پنجره حداکثر ۷ روز. خطای داخلی job با تاخیر ۶۰ ثانیه مجدداً پردازش می‌شود. بدون دستگاه واجد شرایط برای اطلاعیه خوانده‌نشده جدید، هر ۵ دقیقه تا پایان پنجره بررسی می‌شود. فقط کاربرانی که دستگاه pending/accepted ندارند می‌توانند با ثبت نشست جدید بازیابی شوند. پذیرفته شدن یک دستگاه به معنی نیاز نداشتن به ارسال مجدد خودکار روی دستگاه جدید دیگر در همان event است. رویداد عمومی بدون دستگاه به وضعیت no_devices می‌رود. OA همچنان retry و outbox قبلی خودش را دارد.
- وضعیت delivery: pending / accepted / stale / ineligible / failed / expired. وضعیت job: pending / no_devices / no_targets / accepted / partial / not_accepted / cancelled / expired. `no_device_count` در اطلاعیه‌ها تعداد کاربران هنوز بدون دستگاه pending/accepted است؛ در job عمومی شمارش اولیه بدون دستگاه. `accepted` یعنی provider درخواست را قبول کرده، نه اینکه گوشی اعلان را نمایش داده یا کاربر خوانده باشد. وضعیت نهایی ممکن است بعضی دستگاه‌های accepted داشته باشد؛ برای گزارش دقیق ردیف‌های delivery را نیز ببینید.
- صف از origin متفاوت پردازش نمی‌شود. این شرط فقط job را جدا می‌کند، نه اشتراک‌های کپی‌شده دیتابیس. اگر DB تست از Production Restore شده، ممکن است اشتراک/نشست قدیمی به گوشی حقیقی متصل باشد. قبل از تست، محیط تست باید واقعاً ایزوله باشد (جلسه/اشتراک‌های واقعی و مخاطب‌های عمومی را به‌کار نبرید). هیچ backfill یا ارسال خودکار اطلاعیه‌های تاریخی در Migration وجود ندارد.
- در شرایط crash پس از قبول provider و پیش از commit، امکان ارسال مجدد وجود دارد؛ کلید ثابت event و کنترل SW برای dedup است، ولی exactly-once سراسری نیست. اگر Worker مرورگر قبل از تکمیل نمایش از بین برود، claim ممکن است باقی بماند. عدم دسترسی IndexedDB همچنان fail-closed است. پیام ممکن است در provider پس از پذیرفته شدن تا TTL قبلی ۲۴ ساعت نگهداری شود؛ این با پنجره retry هفت روزه سمت سرور یکی نیست. پس از accepted به علت نبود ACK نمایش، resend خودکار نداریم.

## ۴. ثبت دقیق تغییرات فایل‌ها

فایل `PUSH-RELIABILITY-CHANGES.tsv` در بسته تحویل، فهرست ماشینی همه فایل‌های جدید/تغییریافته و تعداد خطوط را دارد. Patch همراه، مرجع دقیق تمام خطوط تغییر است. این بخش چرایی هر فایل را توضیح می‌دهد:

| فایل | تغییر/علت |
|---|---|
| `frontend/src/sw.js` | اصلاح ReferenceError، کنترل SID قبل/بعد نمایش، محدودکردن انتظار آیکون، آزادکردن claim نمایش ناموفق، dedup کلید dispatch بر مبنای SID |
| `frontend/src/utils/push.js` | single-flight، تشخیص تغییر نشست، VAPID rotation، timeout ready، بررسی دوره‌ای/بازگشت آنلاین و وضعیت ثبت واقعی |
| `frontend/src/components/Layout.jsx` | راه‌اندازی/پاک‌سازی maintenance در پنل کاربری؛ نمایش وضعیت ثبت واقعی و امکان تلاش مجدد |
| `frontend/src/pages/ProfilePage.jsx` | همسان‌سازی وضعیت و متن ثبت اعلان با Layout؛ بازطراحی صفحه دسترسی‌ها خارج از دامنه |
| `frontend/tests/pushServiceWorker.test.mjs` | اجرای کد واقعی SW در VM با IndexedDB/OS/Cache mock و تست‌های نشست، خطا و dedup |
| `frontend/tests/pushRegistration.test.mjs` | تست کد واقعی ثبت اشتراک با mock، single-flight، تغییر VAPID و SID، خطا و مجوز |
| `backend/app/schemas/push.py` | فیلد اختیاری session_marker برای هماهنگی کلاینت جدید با نشست واقعی |
| `backend/app/api/v1/endpoints/push.py` | جلوگیری از ثبت اشتراک برای SID اشتباه پس از تغییر حساب/refresh |
| `backend/app/services/push_service.py` | جداسازی transport از enqueue عمومی، اشتراک‌های واجد شرایط، محدودسازی به subscription/session، حذف مشروط stale، لاگ بدون اسرار و گزارش provider |
| `backend/app/models/push_dispatch.py` | مدل job و delivery و شاخص‌های صف |
| `backend/app/models/__init__.py` | ثبت مدل‌های جدید در metadata |
| `database/migrations/versions/154_push_dispatch_outbox.py` | ساخت جداول افزایشی؛ بدون تغییر داده قدیمی و backfill |
| `backend/app/services/push_dispatch.py` | ثبت پایدار، revalidation، پردازش و retry جداگانه، بازیابی اطلاعیه جدید بدون دستگاه، آمار/حالت نهایی |
| `backend/app/core/scheduler.py` | راه‌اندازی drain صف با interval و max_instances، حفظ schedulerهای دیگر |
| `backend/app/services/notice_service.py` | enqueue اتمیک هنگام publish با lock، resend ثبت‌شده فقط برای خوانده‌نشده و اطلاعیه معتبر؛ تابع legacy idempotent |
| `backend/app/services/payroll_service.py` | ثبت job در تراکنش ارسال فیش، بدون تغییر محتوای PDF |
| `backend/app/services/attendance_card_service.py` | ثبت job در تراکنش فیش کارکرد، بدون تغییر منطق PDF |
| `backend/app/services/birthday_greetings_service.py` | ثبت job در تراکنش اطلاعیه تبریک |
| `backend/app/services/family_service.py` | enqueue در تراکنش ایجاد اطلاعیه نتیجه پرونده |
| `backend/app/services/insurance_service.py` | enqueue در تراکنش اطلاعیه رد مدرک، بدون تغییر قواعد بیمه |
| `backend/app/api/v1/endpoints/notices.py` | حذف BackgroundTask ارسال تکراری پس از ثبت job، حفظ API و rate limit |
| `backend/app/api/v1/endpoints/family.py` | حذف BackgroundTask تکراری |
| `backend/app/api/v1/endpoints/insurance.py` | حذف BackgroundTask تکراری |
| `backend/app/services/push_background.py` | تبدیل schedule_push به async enqueue با commit مستقل و گزارش خطای ثبت، بدون I/O شبکه |
| `backend/app/services/birthday_reaction_service.py` | await ثبت job عمومی |
| `backend/app/services/evaluation_process_service.py` | await ثبت job عمومی |
| `backend/app/services/feedback_service.py` | await ثبت job عمومی |
| `backend/app/services/login_security_service.py` | await ثبت job عمومی |
| `backend/app/services/oa_notification_outbox.py` | لاگ/خطای ذخیره‌شده بدون اسرار؛ حفظ منطق فعلی outbox نامه |
| `backend/requirements.txt` | افزودن pytest-asyncio برای اجرای تست‌های async که پیش‌تر اجرا نمی‌شدند |
| `backend/tests/test_push_session_and_oa_retry_v933.py` | افزایش پوشش تست‌های transport، عدم افشای کلید/endpoint، صف و retry، expiry و idempotency |
| `scripts/check.sh` | افزودن اجرای تست‌های واحد Frontend به check.sh |
| `docs/PUSH-RELIABILITY-HANDOFF-FA.md` | همین سند تحویل |

## ۵. آزمایش‌های انجام‌شده و محدودیت‌ها

محیط آفلاین، بدون اتصال به دیتابیس شرکت، بدون ارسال به گوشی کارکنان:
- `npm run test:unit`: 65/65 موفق؛ نسخه مبنا قبل از تغییرات 43/43. 16 تست SW و 6 تست ثبت اشتراک اضافه شده‌اند. Mock به جای Workbox، IndexedDB واقعی، OS و سرویس Push است. تست با کد واقعی انجام شده نه کپی تابع اصلاح‌شده.
- `python -m pytest -q tests/test_push_session_and_oa_retry_v933.py`: 12/12 موفق؛ مبنا 5/5. شامل 5 تست صف جدید، 2 تست جدید transport/عدم افشا و 5 تست قبلی. تنظیمات تست و mock محلی؛ محیط فاقد asyncpg/pywebpush واقعی است. این تست‌ها اثبات PostgreSQL concurrency یا ارسال واقعی نیستند.
- `python -m compileall -q backend/app database/migrations`، `node --check frontend/src/sw.js`، `node --check frontend/src/utils/push.js`، `bash -n scripts/check.sh` و `git diff --check` موفق.
- مجموعه کامل Backend در این محیط در collection به دلیل فقدان asyncpg، pymssql و jdatetime متوقف شد (۶ خطا). نصب آفلاین npm به دلیل ENOTCACHED برای @emotion/cache شکست خورد؛ Build نهایی Vite و Migration واقعی PostgreSQL اجرا نشده‌اند. این بسته به همین دلیل **آماده آزمایش است، نه تایید انتشار Production**. گزارش‌های تست در ZIP اصلاحیه هستند. از خطای محیط نتیجه موفقیت آزمون استنباط نشود.

## ۶. روش اعمال و راه‌اندازی در محیط تست

1. از DB تست و کد جاری و فایل assetlinks اصلاح‌شده پشتیبان تهیه کنید. از اجرای عمومی Push روی DB کپی‌شده Production خودداری کنید؛ تنها یک حساب آزمایشی واقعی هدف باشد. مطمئن شوید `FRONTEND_URL=https://portal-test.faipco.ir` و دیتابیس/کلیدهای درست محیط تست استفاده می‌شوند. هیچ تغییر Reverse Proxy لازم نیست. فایل‌های `.env`، تنظیمات SMB، داده و فونت‌های محیط نصب را با نمونه‌های سورس جایگزین نکنید.
2. روی شاخه آزمایشی مبتنی بر bb9174b با working tree پاک (از تغییرات دستی بکاپ بگیرید) Patch را اعمال کنید. مسیر root `/var/www/html`:

```bash
cd /var/www/html
git status --short
git rev-parse HEAD
git apply --check /root/faipco-portal-bb9174b-push-reliability.patch
git apply /root/faipco-portal-bb9174b-push-reliability.patch
```

3. وابستگی‌های Backend/Frontend را در همان محیط پروژه نصب و تست کنید. این بسته Migration 154 جدید دارد؛ از `install.sh`/روال استاندارد نصب و انتشار پروژه استفاده شود تا dependencies، `alembic upgrade head`، build و فعال‌سازی release به ترتیب صحیح انجام شوند. قبل از اعمال Migration از backup/ایزوله بودن محیط اطمینان حاصل کنید. برای بررسی دستی:

```bash
cd /var/www/html/backend
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q tests/test_push_session_and_oa_retry_v933.py
.venv/bin/alembic heads
# بعد از بکاپ و قبل از شروع backend جدید:
.venv/bin/alembic upgrade head
.venv/bin/alembic current
cd /var/www/html/frontend
npm ci
npm run test:unit
npm run build
```

`heads/current` باید تنها revision 154 را برای همین مبنا نشان دهند؛ اگر محیط از سورس دیگری Migration جدید دارد، این Patch را کورکورانه اعمال نکنید. Build دستی به‌تنهایی معادل انتشار رویدادمحور فعلی پروژه نیست؛ فعال‌سازی با روال release موجود انجام شود. Restart Backend جدید لازم است تا scheduler اضافه شود؛ DB Migration قبل از backend جدید الزامی است. پس از انتشار، `assetlinks.json` تست را دوباره بررسی کنید تا package `ir.faipco.portal.test` از بین نرود. در UI بروزرسانی SW را بپذیرید؛ permission داده‌شده باید خودکار دوباره ثبت شود. نیازی به APK جدید یا پاک کردن همه داده مرورگر نیست. اشتراک قدیمی unbound تا بازثبت با نشست معتبر ارسال نمی‌گیرد؛ این یک تصمیم امنیتی نسخه bb9174b است.

4. تست‌های پذیرش قبل از هر انتقال به سرور اصلی:
   - Chrome، PWA و TWA با نشست فعال: ارسال اطلاعیه فقط به کاربر آزمایشی، دریافت و کلیک، فیش حقوق/کارکرد، اعلان OA و سایر ماژول‌ها؛ وضعیت واقعی دستگاه و خوانده‌شدن در پرتال بررسی شود.
   - قطع اینترنت سرور/خطای موقت FCM و restore، restart backend بعد از انتشار/در حال ارسال، همزمانی workerهای Uvicorn و ارسال چند گیرنده؛ فقط دستگاه شکست‌خورده retry شود. از آزمایش کنترل‌شده و حساب‌های ساختگی استفاده شود.
   - خاموشی/اینترنت قطع دستگاه و بازگشت، حالت Doze، اعلان مسدود، بازثبت device/تغییر VAPID در محیط جدا، ارتقای کلاینت از beta.29.3، بازکردن برنامه بدون logout/login، تغییر حساب و خروج محلی/remote، تعویض endpoint و stale response، اعلان تکراری و اعلان فیش قبلاً خوانده‌شده. بررسی کنید کاربر فاقد مجوز هیچ داده‌ای نگیرد.
   - Migration روی کپی DB سالم و DB خالی، `scripts/check.sh`، API snapshot، تست بار با 1000 مخاطب ساختگی و اندازه‌گیری latency/DB pool/thread/scheduler backlog. هنوز ظرفیت 1000 و SLA اندازه‌گیری نشده است.
   - توقف سرویس در صورت نیاز rollback کد؛ جدول جدید را برای تاریخچه و jobهای pending حذف نکنید. downgrade 154 جداول صف را حذف می‌کند و موجب از دست رفتن jobها می‌شود؛ فقط با تصمیم و بکاپ مشخص. بازگشت به SW معیوب bb9174b نمایش را مجدداً خراب می‌کند.

## ۷. عیب‌یابی فقط خواندنی

```sql
SELECT id, notice_id, status, target_count, no_device_count,
       created_at, next_attempt_at, finished_at, last_error
FROM push_dispatch_jobs
ORDER BY id DESC LIMIT 30;

SELECT job_id, status, count(*) AS devices, max(attempts) AS max_attempts
FROM push_dispatch_deliveries
GROUP BY job_id, status
ORDER BY job_id DESC, status LIMIT 80;

SELECT count(*) AS overdue_jobs
FROM push_dispatch_jobs
WHERE status = 'pending' AND next_attempt_at < now() - interval '5 minutes';
```

```bash
journalctl -u faipco-backend --since '30 minutes ago' --no-pager | grep -Ei 'push job|push dispatch|durably queued|Push skipped|ارسال Push'
```

لاگ/دیتابیس را با کلیدهای محرمانه، endpoint کامل و داده پرسنلی به اشتراک نگذارید. accepted با delivery/display/read اشتباه نشود. شناسه خوانده‌شدن و کارتابل منابع اصلی وضعیت خواندن هستند.

## ۸. محدودیت‌های واقعی و نقشه تکمیل قابلیت «هیچ اعلان از دست نرود»

Web Push بدون ACK دستگاه نمی‌تواند تحویل نهایی را تضمین کند؛ مجوز خاموش، force-stop مرورگر، انقضای TTL، دستگاه آفلاین طولانی، Doze، محدودیت سازنده، پاک‌شدن داده یا اختلال provider خارج از کنترل پرتال است. پذیرش پیام توسط FCM/Apple/Mozilla و موفقیت showNotification حتی الزاماً دیده‌شدن توسط انسان نیست. کنترل امنیتی بر تلاش مجدد ارجح است؛ اعلان نشست قدیمی نباید به زور نمایش داده شود.

این نسخه اطلاعیه‌های ثبت‌شده و فیش‌ها را همچنان در صندوق دریافتی خود پرتال نگه می‌دارد؛ کارتابل‌های اصلی نیز منبع داده مستقل از Push هستند. **صندوق رویداد یکپارچه جدید و ACK نمایش، UI مانیتورینگ صف، اعلان جایگزین SMS/Email و replay بعد از accepted هنوز پیاده نشده‌اند.** برخی producerهای عمومی از جمله wrapperهای مرخصی/وام/مساعده/عکس/خانواده/بیمه و استخدام همچنان پیش از enqueue در فرآیند یا task موقت اجرا می‌شوند، و enqueue عمومی در تراکنش مستقل است. crash قبل از enqueue در این مسیرها ممکن است موجب عدم ثبت job شود. enqueue ناموفق عمومی log می‌شود؛ هیچ تضمین تراکنش اتمیک سراسری وجود ندارد. generic و OA بازیابی خودکار بدون دستگاه مانند notice ندارند؛ OA صف فعلی خود را حفظ کرده است. خطای مجوز/دستگاه و کلید dedup نیمه‌کاره نیازمند برنامه ACK و recovery هستند. جدول‌ها retention خودکار ندارند و رشد حجم/مانیتورینگ باید پیش از انتشار وسیع تعیین شود. در PWA قدیمی و کلاینت جدید/قدیمی، سازگاری release باید تست شود. چند تب و logout حین عملیات شبکه همچنان نیازمند آزمون end-to-end هستند.

فاز پیشنهادی مستقل، پس از موفقیت فاز حاضر:
- Inbox رویدادهای پایدار برای همه ماژول‌ها، ثبت اتمیک domain event + outbox برای همه مسیرها، کلید idempotency رویداد و گیرنده، بازبینی دسترسی بر اساس منبع رویداد پیش از هر ارسال. برای رویدادهایی که کاربر نباید پس از تغییر مجوز ببیند، فقط نشست کافی نیست.
- ACK امن Service Worker برای receipt/نمایش (توکن کوتاه‌عمر محدود به event/device/session؛ بدون دسترسی JWT مرورگر در SW) و read/seen مستقل، heartbeat/capability کلاینت، deadline/TTL و بازپخش محدود فقط بر اساس ACK و منطق اهمیت رویداد. ACK نیز رسید واقعی مشاهده انسان نیست.
- سازگاری rollout بین SW و backend، اصلاح atomic session marker میان تب‌ها، جداسازی origin اشتراک‌ها (مخصوصاً دیتابیس restore شده)، retention/lease برای claim، صف dead-letter و replay کنترل‌شده، jitter/Retry-After، سنجه P95 زمان تا پذیرش/نمایش و alert backlog، آزمایش بار واقعی و خرابی عمدی.
- به‌روزرسانی صندوق/شمارنده‌ها مستقل از Push هنگام resume/reconnect، یادآوری کنترل‌شده اعلان مهم خوانده‌نشده و در صورت سیاست شرکت، کانال جایگزین با حداقل اطلاعات شخصی. بدون ارسال تکراری کورکورانه و بدون پیام محرمانه روی گوشی فاقد نشست معتبر.

از Claude خواسته می‌شود قبل از ادامه تغییرات، diff دقیق و این محدودیت‌ها را بررسی کند؛ باگ line 102 به عنوان رگرسیون قطعی حفظ شود و کنترل امنیتی جدید حذف نشود. هر تغییر جدید، Migration و آزمون با علت و نتیجه ثبت شود. هیچ یک از تغییرات مربوط به اپ اندروید و صفحه یکپارچه دسترسی‌ها در این بسته اعمال نشده است.
