/*
 * Service Worker پرتال FAIPCO — با vite-plugin-pwa (استراتژی injectManifest)
 * ساخته و به‌روزرسانی می‌شود.
 *
 * سه وظیفه دارد:
 *   ۱. Precache دارایی‌های اصلی برنامه (App Shell: JS/CSS/HTML خروجی Vite)
 *      — تا در صورت قطعی لحظه‌ای اینترنت، بارگذاری مجدد صفحه با
 *      ChunkLoadError/صفحه سفید مواجه نشود.
 *   ۲. Fallback ناوبری به‌سمت index.html وقتی آفلاین هستید (چون این یک SPA
 *      با مسیریابی سمت کلاینت است — مسیرهایی مثل /notices در واقعیت روی
 *      سرور وجود ندارند، همیشه باید همان index.html برگردد).
 *   ۳. دریافت و نمایش پیام‌های Push از سرور.
 *
 * عمداً یک اپلیکیشن کاملاً Offline-first نیست (این یک پرتال مدیریتی است که
 * برای کارکردن واقعی به اتصال زنده به API نیاز دارد) — فقط App Shell (پوسته
 * برنامه) Precache می‌شود تا لااقل خودِ برنامه بدون خطای سفید بالا بیاید،
 * نه اینکه داده‌های API هم آفلاین در دسترس باشند.
 */
import { precacheAndRoute, createHandlerBoundToURL } from "workbox-precaching";
import { registerRoute, NavigationRoute } from "workbox-routing";

// self.__WB_MANIFEST نقطه‌ای است که vite-plugin-pwa موقع Build، فهرست
// واقعی فایل‌های خروجی (با Hash نسخه، برای رفع باگ Cache شدید Chrome روی
// اندروید) را جایگزینش می‌کند — دستی نگه‌داشتن این فهرست ممکن نیست چون نام
// فایل‌های Vite با هر Build عوض می‌شود.
precacheAndRoute(self.__WB_MANIFEST);

// درخواست‌های ناوبری (مثلاً کاربر مستقیم /notices را در نوار آدرس بزند یا
// Refresh کند) به همان index.html پیش‌کش‌شده هدایت می‌شوند — استاندارد
// Workbox برای پشتیبانی SPA.
const navigationHandler = createHandlerBoundToURL("/index.html");
registerRoute(new NavigationRoute(navigationHandler));

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// دریافت پیام Push از سرور و نمایش آن به‌عنوان Notification سیستمی — طبق
// درخواست، صرف‌نظر از اولویت اطلاعیه، همیشه با صدا + ویبره محسوس (مثل
// یک آلارم واقعی) نمایش داده می‌شود، نه فقط برای اولویت‌های بالا.
self.addEventListener("push", (event) => {
  let payload = { title: "FAIPCO Portal", body: "اطلاعیه جدید", url: "/notices", priority: "normal" };
  try {
    if (event.data) {
      payload = { ...payload, ...event.data.json() };
    }
  } catch (e) {
    // اگر بدنه پیام JSON نبود، از مقادیر پیش‌فرض بالا استفاده می‌شود
  }

  event.waitUntil(
    (async () => {
      await self.registration.showNotification(payload.title, {
        body: payload.body,
        // icon: تصویر رنگی بزرگ لوگو — داخل بدنه اعلان (وقتی باز می‌شود) دیده می‌شود
        icon: "/icons/icon-192.png",
        // badge: نسخه تک‌رنگ (سفید روی شفاف) لوگو — مخصوص نوار وضعیت اندروید؛
        // اگر همان آیکون رنگی اینجا داده شود، اندروید آن را به یک لکه نامفهوم
        // تبدیل می‌کند، چون badge را همیشه یک‌رنگ/Silhouette رندر می‌کند.
        badge: "/icons/badge-96.png",
        dir: "rtl",
        lang: "fa",
        data: { url: payload.url || "/notices" },
        requireInteraction: true, // اعلان خودش بسته نمی‌شود، تا کاربر حتماً ببیندش
        silent: false, // صدای پیش‌فرض اعلان سیستم پخش شود (هیچ‌وقت بی‌صدا نباشد)
        vibrate: [400, 150, 400, 150, 400], // الگوی ویبره قوی و واضح، برای هر اولویتی یکسان
        tag: `faipco-notice-${Date.now()}`, // هر Push جدا نمایش داده شود، نه جایگزین قبلی
      });

      // به هر تب بازِ اپلیکیشن پیام می‌دهیم تا لیست اطلاعیه‌ها را خودش
      // (بدون Reload صفحه) دوباره از سرور بخواند — تجربه Real-time.
      const clientsList = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      clientsList.forEach((client) => client.postMessage({ type: "faipco-notice-push", ...payload }));
    })()
  );
});

// کلیک روی Notification: تب باز موجود را فوکوس کن، وگرنه یک تب جدید باز کن
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || "/notices";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientsList) => {
      for (const client of clientsList) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      return self.clients.openWindow(targetUrl);
    })
  );
});
