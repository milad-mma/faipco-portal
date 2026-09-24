/**
 * کمک‌تابع‌های اعلان Push مرورگر: بررسی پشتیبانی و وضعیت اجازه،
 * فعال‌سازی (درخواست اجازه، ساخت اشتراک با کلید VAPID و ثبت در سرور) و لغو اشتراک.
 */
import { fetchVapidPublicKey, subscribePush, unsubscribePush } from "../api/push";

/** تبدیل کلید عمومی VAPID (Base64URL) به Uint8Array مورد نیاز pushManager.subscribe */
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  return Uint8Array.from([...rawData].map((char) => char.charCodeAt(0)));
}

// خروجی: true اگر مرورگر Service Worker، PushManager و Notification را پشتیبانی کند
export function isPushSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

// خروجی: وضعیت اجازه‌ی اعلان ("granted" / "denied" / "default") یا "unsupported"
export function getNotificationPermission() {
  return isPushSupported() ? Notification.permission : "unsupported";
}

/** درخواست اجازه‌ی اعلان از کاربر، گرفتن یا ساخت اشتراک Push و ثبت آن در سرور؛ خروجی: شیء اشتراک. در خطا پیام فارسی throw می‌کند. */
export async function enablePushNotifications() {
  if (!isPushSupported()) {
    throw new Error("این مرورگر از اعلان Push پشتیبانی نمی‌کند.");
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("اجازه نمایش اعلان داده نشد.");
  }

  const registration = await navigator.serviceWorker.ready;

  // استفاده از اشتراک موجود؛ در نبود آن ساخت اشتراک جدید با کلید عمومی VAPID سرور
  let subscription = await registration.pushManager.getSubscription();
  if (!subscription) {
    const vapidPublicKey = await fetchVapidPublicKey();
    if (!vapidPublicKey) {
      throw new Error("سرور هنوز برای ارسال اعلان پیکربندی نشده است.");
    }
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true, // الزام مرورگر: هر Push باید اعلان قابل مشاهده نمایش دهد
      applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
    });
  }

  await subscribePush(subscription.toJSON());
  return subscription;
}

/** لغو اشتراک Push (هم در مرورگر، هم در سرور). */
export async function disablePushNotifications() {
  if (!isPushSupported()) return;
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (subscription) {
    await unsubscribePush(subscription.endpoint);
    await subscription.unsubscribe();
  }
}
