# PWA و Service Worker

## معماری Service Worker

از `vite-plugin-pwa` با استراتژی **injectManifest** استفاده می‌شود — نه
`generateSW` پیش‌فرض. تفاوت مهم: با `injectManifest`، Service Worker کاملاً
دستی خودمان (`frontend/src/sw.js`) نوشته و کنترل می‌شود (منطق کامل
Push/Notification)، فقط **فهرست Precache** (لیست فایل‌های واقعی خروجی هر
Build، با نام‌های Hash‌دار Vite) توسط Workbox خودکار داخلش تزریق می‌شود —
چون نگه‌داشتن دستی این فهرست با تغییر نام فایل در هر Build ممکن نیست.

```js
// frontend/vite.config.js
VitePWA({
  strategies: "injectManifest",
  srcDir: "src",
  filename: "sw.js",
  injectRegister: null,  // ثبت را خودمان دستی مدیریت می‌کنیم
  manifest: false,        // manifest.json را خودمان دستی نگه می‌داریم
  injectManifest: {
    globPatterns: ["**/*.{js,css,html,svg,woff,woff2}"],
  },
})
```

خروجی Build، `dist/sw.js` است — دقیقاً همان مسیری که
`frontend/src/utils/serviceWorker.js` با `register("/sw.js")` ثبتش می‌کند؛
هیچ تغییری در منطق ثبت لازم نبود.

## چرا Offline-first کامل نیست

فقط App Shell (فایل‌های JS/CSS/HTML خروجی Build) Precache می‌شوند — نه
داده‌های API. این یک پرتال مدیریتی است که برای کارکردن واقعی به اتصال زنده
نیاز دارد؛ هدف فقط جلوگیری از صفحه سفید/`ChunkLoadError` در یک قطعی
لحظه‌ای اینترنت است، نه یک تجربه کاملاً آفلاین.

## مسیریابی SPA در حالت آفلاین

چون این یک برنامه تک‌صفحه‌ای با مسیریابی سمت کلاینت است (مثلاً `/notices`
واقعاً روی سرور وجود ندارد)، از `NavigationRoute` خودِ Workbox استفاده
می‌شود تا هر درخواست ناوبری آفلاین به همان `index.html` پیش‌کش‌شده هدایت
شود.

## مقابله با Cache شدید Android روی Manifest/آیکون‌ها

Chrome روی اندروید `manifest.json` و آیکون‌هایش را به‌شدت Cache می‌کند —
کوچک‌ترین تغییر بدون Cache Busting ممکن است اصلاً دیده نشود. برای همین، لینک
Manifest در `index.html` و آدرس هر آیکون داخل خودِ `manifest.json` یک
Query String نسخه دارند (`?v=2`):

⚠️ **این عدد را دستی بالا ببرید** هر بار که خودِ `manifest.json` یا هر
کدام از آیکون‌های داخلش عوض می‌شود (نه برای هر Deploy معمولی) — باید در هر
دو جا (`index.html` و همه `src` های داخل `manifest.json`) هم‌زمان و یکسان
تغییر کند.

## CSP و PWA

هدر Content-Security-Policy (نگاه کنید `install.sh`) صریحاً `manifest-src
'self'` و `worker-src 'self'` دارد — نه فقط تکیه بر Fallback خودکارشان به
`default-src`/`script-src` — تا ثبت Service Worker و بارگذاری Manifest در
هیچ نسخه/رفتار مرورگری بلاک نشوند.

## چک‌لیست تشخیص مشکل نصب PWA روی اندروید

اگر با اینکه همه موارد بالا درست است، اپ همچنان به‌جای نصب واقعی
(WebAPK)، فقط یک میان‌بر با آیکون Chrome می‌سازد:

1. از Chrome DevTools (روی دسکتاپ، با اتصال به گوشی از `chrome://inspect`،
   یا مستقیم در `chrome://apps` روی گوشی) بخش **Application → Manifest**
   را چک کنید — هر خطای «Installability» دقیقاً آنجا با پیام مشخص نشان
   داده می‌شود؛ حدس‌زدن لازم نیست.
2. اگر هیچ خطای فنی نشان نداد، احتمالاً **معیارهای رفتاری Chrome**
   (Engagement Heuristics) است — Chrome عمداً پیشنهاد نصب واقعی را تا
   دیدن بازدیدهای متعدد کاربر در چند روز مختلف به تعویق می‌اندازد، مستقل
   از درستی فنی کد.
