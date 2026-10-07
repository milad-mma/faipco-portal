/*
 * Service Worker پرتال FAIPCO؛ با vite-plugin-pwa (استراتژی injectManifest) ساخته می‌شود.
 *
 * وظایف:
 *   ۱. Precache دارایی‌های اصلی برنامه (App Shell: JS/CSS/HTML خروجی Vite)
 *      تا با قطعی لحظه‌ای اینترنت، بارگذاری مجدد صفحه با ChunkLoadError/صفحه‌ی سفید مواجه نشود.
 *   ۲. Fallback ناوبری به index.html (برنامه SPA است و مسیرهایی مثل /notices روی سرور وجود ندارند).
 *   ۳. دریافت و نمایش پیام‌های Push از سرور و باز کردن مقصد با کلیک روی اعلان.
 *   ۴. به‌روزرسانی کنترل‌شده: نسخه‌ی جدید تا تأیید کاربر (پیام SKIP_WAITING) در حالت waiting می‌ماند.
 *
 * برنامه Offline-first نیست: فقط پوسته‌ی برنامه Precache می‌شود و داده‌های API همیشه از شبکه خوانده می‌شوند.
 */
import { precacheAndRoute, createHandlerBoundToURL } from "workbox-precaching";
import { registerRoute, NavigationRoute } from "workbox-routing";
import { NetworkOnly } from "workbox-strategies";

// Precache پوسته‌ی برنامه: vite-plugin-pwa هنگام Build به‌جای self.__WB_MANIFEST فهرست فایل‌های خروجی
// (با Hash نسخه) را قرار می‌دهد؛ با هر Build نام فایل‌ها عوض می‌شود و فایل‌های قدیمی از کش خارج می‌شوند
precacheAndRoute(self.__WB_MANIFEST);

// درخواست‌های API (/api/) با NetworkOnly همیشه مستقیم از سرور پاسخ داده می‌شوند و هرگز از Cache نمی‌آیند
// تا داده‌ی قدیمی (مثل لیست اطلاعیه‌ها یا وضعیت پرسنل) نمایش داده نشود
registerRoute(({ url }) => url.pathname.startsWith("/api/"), new NetworkOnly());

// درخواست‌های ناوبری (باز کردن مستقیم یا Refresh یک مسیر مثل /notices) با index.html پیش‌کش‌شده پاسخ داده می‌شوند
const navigationHandler = createHandlerBoundToURL("/index.html");
registerRoute(new NavigationRoute(navigationHandler));

// آیکون‌های اعلان: Chrome تصویر icon/badge را هنگام نمایش اعلان از شبکه می‌گیرد؛ اگر گوشی در آن لحظه در خواب
// (Doze) باشد یا اینترنتش ضعیف، گرفتن تصویر شکست می‌خورد و Chrome زنگوله‌ی پیش‌فرض خودش را نشان می‌دهد («گاهی با
// لوگو، گاهی زنگوله»). برای همین هر دو تصویر در Cache نگه داشته و به‌صورت data: URL به اعلان داده می‌شوند.
const NOTIFICATION_ICON_CACHE = "faipco-notification-icons-v1";
const NOTIFICATION_ICON = "/icons/icon-192.png";
const NOTIFICATION_BADGE = "/icons/badge-96.png";

async function cacheNotificationIcons() {
  try {
    const cache = await caches.open(NOTIFICATION_ICON_CACHE);
    await cache.addAll([NOTIFICATION_ICON, NOTIFICATION_BADGE]);
  } catch {
    // بدون اینترنت هنگام نصب: در اولین Push دوباره تلاش می‌شود
  }
}

// تصویر را از Cache (یا در نبودش از شبکه و ذخیره در Cache) به data: URL تبدیل می‌کند؛ شکست ← همان آدرس معمولی
async function notificationImage(path) {
  try {
    const cache = await caches.open(NOTIFICATION_ICON_CACHE);
    let response = await cache.match(path);
    if (!response) {
      response = await fetch(path);
      if (response.ok) await cache.put(path, response.clone());
    }
    const type = response?.headers.get("content-type") || "";
    // نبود فایل آیکون ← index.html با کد 200 (fallback صفحه‌ها)؛ نباید به‌جای تصویر استفاده شود
    if (!response || !response.ok || !type.startsWith("image/")) return path;
    const bytes = new Uint8Array(await response.arrayBuffer());
    let binary = "";
    for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return `data:${type};base64,${btoa(binary)}`;
  } catch {
    return path;
  }
}

// رویداد نصب نسخه‌ی جدید Service Worker
self.addEventListener("install", (event) => {
  // آیکون‌های اعلان همین حالا در Cache گذاشته می‌شوند (نصب منتظر آن نمی‌ماند اگر شبکه نباشد)
  event.waitUntil(cacheNotificationIcons());
  // skipWaiting خودکار صدا زده نمی‌شود: نسخه‌ی جدید در حالت waiting می‌ماند تا کاربر با دکمه‌ی «بارگذاری»
  // تأیید کند، تا Reload ناخواسته وسط پر کردن یک فرم (مثل نوشتن اطلاعیه) رخ ندهد
});

// دریافت پیام SKIP_WAITING از utils/serviceWorker.js (وقتی کاربر دکمه‌ی «بارگذاری نسخه جدید» را می‌زند)
// و فعال کردن فوری نسخه‌ی در انتظار
self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

// پس از فعال شدن، کنترل همه‌ی تب‌های باز فوراً به همین نسخه سپرده می‌شود
self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

// دریافت پیام Push از سرور و نمایش آن به صورت Notification سیستمی؛ برای هر اولویتی با صدا و ویبره نمایش داده می‌شود.
// سپس به تب‌های باز برنامه پیام می‌دهد تا لیست اطلاعیه‌ها را بدون Reload تازه کنند.
// عنوان پیش‌فرض کلی و بدون نام شرکت است چون Service Worker به BrandingContext دسترسی ندارد؛
// فقط وقتی استفاده می‌شود که Payload سرور عنوانی نداشته باشد.
self.addEventListener("push", (event) => {
  let payload = { title: "اطلاعیه جدید", body: "یک اطلاعیه جدید دریافت شد", url: "/notices", priority: "normal" };
  try {
    if (event.data) {
      payload = { ...payload, ...event.data.json() };
    }
  } catch (e) {
    // اگر بدنه پیام JSON نبود، از مقادیر پیش‌فرض بالا استفاده می‌شود
  }

  event.waitUntil(
    (async () => {
      const [icon, badge] = await Promise.all([
        notificationImage(NOTIFICATION_ICON),
        notificationImage(NOTIFICATION_BADGE),
      ]);
      await self.registration.showNotification(payload.title, {
        body: payload.body,
        // icon: تصویر رنگی بزرگ لوگو — داخل بدنه اعلان (وقتی باز می‌شود) دیده می‌شود
        icon,
        // badge: نسخه‌ی تک‌رنگ (سفید روی شفاف) لوگو برای نوار وضعیت اندروید؛
        // اندروید badge را همیشه تک‌رنگ (Silhouette) رندر می‌کند و آیکون رنگی به لکه‌ای نامفهوم تبدیل می‌شود
        badge,
        dir: "rtl", // جهت متن اعلان راست‌به‌چپ
        lang: "fa", // زبان متن اعلان
        data: { url: payload.url || "/notices" }, // مسیر مقصد برای استفاده در رویداد notificationclick
        requireInteraction: true, // اعلان خودش بسته نمی‌شود، تا کاربر حتماً ببیندش
        silent: false, // صدای پیش‌فرض اعلان سیستم پخش شود (هیچ‌وقت بی‌صدا نباشد)
        vibrate: [400, 150, 400, 150, 400], // الگوی ویبره قوی و واضح، برای هر اولویتی یکسان
        tag: `faipco-notice-${Date.now()}`, // هر Push جدا نمایش داده شود، نه جایگزین قبلی
      });

      // ارسال پیام faipco-notice-push به همه‌ی تب‌های باز برنامه تا لیست اطلاعیه‌ها را بدون Reload دوباره بخوانند
      const clientsList = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      clientsList.forEach((client) => client.postMessage({ type: "faipco-notice-push", ...payload }));
    })()
  );
});

// کلیک روی Notification: اعلان بسته می‌شود؛ اولین تب باز برنامه به مسیر مقصد می‌رود و فوکوس می‌گیرد، وگرنه تب جدید باز می‌شود
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
