import { fetchVapidPublicKey, subscribePush, unsubscribePush } from "../api/push";

/** ثبت Service Worker — یک‌بار در ابتدای بارگذاری اپلیکیشن فراخوانی می‌شود. */
export function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch((err) => {
        console.error("ثبت Service Worker ناموفق بود:", err);
      });
    });
  }
}

/** تبدیل کلید عمومی VAPID (Base64URL) به Uint8Array مورد نیاز pushManager.subscribe */
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  return Uint8Array.from([...rawData].map((char) => char.charCodeAt(0)));
}

export function isPushSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function getNotificationPermission() {
  return isPushSupported() ? Notification.permission : "unsupported";
}

/** درخواست اجازه اعلان از کاربر و ثبت اشتراک Push در سرور. */
export async function enablePushNotifications() {
  if (!isPushSupported()) {
    throw new Error("این مرورگر از اعلان Push پشتیبانی نمی‌کند.");
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("اجازه نمایش اعلان داده نشد.");
  }

  const registration = await navigator.serviceWorker.ready;

  let subscription = await registration.pushManager.getSubscription();
  if (!subscription) {
    const vapidPublicKey = await fetchVapidPublicKey();
    if (!vapidPublicKey) {
      throw new Error("سرور هنوز برای ارسال اعلان پیکربندی نشده است.");
    }
    subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
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
