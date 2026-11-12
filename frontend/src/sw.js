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
// فایل‌های واقعی (assetlinks) نباید با index.html جواب داده شوند
// Recovery path for clients upgrading FROM the old release: it deleted every
// Cache Storage entry before sending SKIP_WAITING. If the new worker's precache
// was also erased, fetch the shell from the network instead of showing a blank
// page. Normal updates still use the precached shell.
registerRoute(new NavigationRoute(async (context) => {
  try {
    return await navigationHandler(context);
  } catch {
    return fetch("/index.html", { cache: "no-store" });
  }
}, { denylist: [/^\/\.well-known\//] }));

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

// Device-local Push gate and per-event deduplication survive browser restarts.
// The endpoint is also restricted server-side to an unrevoked user_session.
function pushSecurityDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("faipco-push-security-v1", 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("meta")) db.createObjectStore("meta");
      if (!db.objectStoreNames.contains("seen")) db.createObjectStore("seen");
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function activePushSessionMarker() {
  try {
    const db = await pushSecurityDb();
    try {
      return await new Promise((resolve, reject) => {
        const tx = db.transaction("meta", "readonly");
        const store = tx.objectStore("meta");
        const enabled = store.get("enabled");
        const marker = store.get("sessionMarker");
        tx.oncomplete = () => resolve(enabled.result === true ? marker.result : null);
        get.onerror = () => reject(get.error);
      });
    } finally { db.close(); }
  } catch { return null; } // fail closed: never show an unverified Push
}

async function storePushEnabled(enabled, sessionMarker = null) {
  const db = await pushSecurityDb();
  try {
    await new Promise((resolve, reject) => {
      const tx = db.transaction("meta", "readwrite");
      const store = tx.objectStore("meta");
      store.put(Boolean(enabled), "enabled");
      store.put(enabled ? sessionMarker : null, "sessionMarker");
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally { db.close(); }
}

async function claimOaNotification(key) {
  // Atomic read/write: two concurrent Push deliveries for the same event can
  // only show one notification, even if the original was already dismissed.
  const db = await pushSecurityDb();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction("seen", "readwrite");
      const seen = tx.objectStore("seen");
      const request = seen.get(key);
      let accepted = false;
      request.onsuccess = () => {
        if (!request.result) {
          accepted = true;
          seen.put(Date.now(), key);
        }
      };
      tx.oncomplete = () => resolve(accepted);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally { db.close(); }
}

// رویداد نصب نسخه‌ی جدید Service Worker
self.addEventListener("install", (event) => {
  // دانلود آیکون‌های اختیاری نباید نصب SW و آپدیت TWA را روی اینترنت کند معطل کند.
  // اگر بارگیری بیش از ۱.۵ ثانیه طول کشید، نصب ادامه می‌یابد؛ خود Push بعداً تصاویر را دریافت می‌کند.
  event.waitUntil(Promise.race([
    cacheNotificationIcons(),
    new Promise((resolve) => setTimeout(resolve, 1500)),
  ]));
  // skipWaiting خودکار صدا زده نمی‌شود: نسخه‌ی جدید در حالت waiting می‌ماند تا کاربر با دکمه‌ی «بارگذاری»
  // تأیید کند، تا Reload ناخواسته وسط پر کردن یک فرم (مثل نوشتن اطلاعیه) رخ ندهد
});

// دریافت پیام SKIP_WAITING از utils/serviceWorker.js (وقتی کاربر دکمه‌ی «بارگذاری نسخه جدید» را می‌زند)
// و فعال کردن فوری نسخه‌ی در انتظار
self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
  if (event.data?.type === "FAIPCO_PUSH_SESSION") {
    event.waitUntil((async () => {
      await storePushEnabled(event.data.enabled, event.data.sessionMarker);
      if (!event.data.enabled) {
        const shown = await self.registration.getNotifications();
        shown.forEach((notice) => notice.close());
      }
    })().catch(() => {}));
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
      const marker = await activePushSessionMarker();
      if (!marker || !payload.session_marker || marker !== payload.session_marker) return;
      const oaKey = typeof payload.notification_key === "string" ? payload.notification_key : null;
      if (oaKey) {
        // A storage failure must not display possibly duplicated OA notifications.
        try { if (!(await claimOaNotification(oaKey))) return; } catch { return; }
      }
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
        tag: oaKey ? `faipco-oa-${oaKey}` : `faipco-notice-${Date.now()}`,
        renotify: false,
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
