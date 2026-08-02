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
  event.waitUntil(self.clients.claim());
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
    self.registration.showNotification(payload.title, {
      body: payload.body,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      dir: "rtl",
      lang: "fa",
      data: { url: payload.url || "/notices" },
    })
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
