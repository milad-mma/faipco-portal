/*
 * Service Worker پرتال FAIPCO.
 * دو وظیفه دارد: (۱) قابلیت نصب/Add to Home Screen را ممکن می‌کند،
 * (۲) پیام‌های Push دریافتی از سرور را به‌صورت Notification سیستمی نمایش می‌دهد.
 * عمداً بدون Cache پیچیده نوشته شده — این یک اپلیکیشن مدیریتی همیشه‌آنلاین است،
 * نه یک اپ کاملاً Offline-first.
 */

const CACHE_NAME = "faipco-shell-v1";
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

// دریافت پیام Push از سرور و نمایش آن به‌عنوان Notification سیستمی
self.addEventListener("push", (event) => {
  let payload = { title: "FAIPCO Portal", body: "اطلاعیه جدید", url: "/notices" };
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
        icon: "/icons/icon-192.png",
        badge: "/icons/icon-192.png",
        dir: "rtl",
        lang: "fa",
        data: { url: payload.url || "/notices" },
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
