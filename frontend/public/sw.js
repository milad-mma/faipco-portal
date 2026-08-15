/*
 * Service Worker پرتال FAIPCO.
 * دو وظیفه دارد: (۱) قابلیت نصب/Add to Home Screen را ممکن می‌کند،
 * (۲) پیام‌های Push دریافتی از سرور را به‌صورت Notification سیستمی نمایش می‌دهد.
 * عمداً بدون Cache پیچیده نوشته شده — این یک اپلیکیشن مدیریتی همیشه‌آنلاین است،
 * نه یک اپ کاملاً Offline-first.
 */

const CACHE_NAME = "faipco-shell-v4";
const SHELL_FILES = ["/", "/manifest.json"];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES).catch(() => {}))
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // هر Cache قدیمی که با نسخه فعلی (CACHE_NAME) مطابقت ندارد پاک می‌شود —
      // این‌طوری با هر Deploy جدید، باقی‌مانده نسخه‌های قبلی جمع نمی‌شود.
      const cacheNames = await caches.keys();
      await Promise.all(
        cacheNames.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name))
      );
      await self.clients.claim();
    })()
  );
});

// درخواست‌های ناوبری (بارگذاری صفحه) را در صورت آفلاین بودن، از Cache برمی‌گرداند
self.addEventListener("fetch", (event) => {
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() => caches.match("/"))
    );
  }
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
