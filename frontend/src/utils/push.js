/** Web Push registration and repair. Permission alone is not a registration. */
import { fetchVapidPublicKey, subscribePush, unsubscribePush } from "../api/push";
import { setDevicePushEnabled } from "./pushSession";

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  return Uint8Array.from([...window.atob(base64)].map(char => char.charCodeAt(0)));
}

function currentSessionMarker() {
  try {
    const token = localStorage.getItem("access_token");
    if (!token) return null;
    const data = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(window.atob(data + "=".repeat((4 - data.length % 4) % 4))).sid || null;
  } catch { return null; }
}

export function isPushSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function getNotificationPermission() {
  return isPushSupported() ? Notification.permission : "unsupported";
}

let registeredMarker = null;
let lastSuccess = 0;
let inFlight = null;
const listeners = new Set();

export function getPushRegistrationStatus() {
  const permission = getNotificationPermission();
  const marker = currentSessionMarker();
  if (permission !== "granted" || registeredMarker !== marker) {
    registeredMarker = null;
    lastSuccess = 0;
  }
  return {
    permission,
    registered: permission === "granted" && !!marker && registeredMarker === marker,
    checking: !!marker && inFlight?.marker === marker,
  };
}
function emit() {
  const status = getPushRegistrationStatus();
  for (const listener of listeners) listener(status);
}
export function observePushRegistration(listener) {
  listeners.add(listener);
  listener(getPushRegistrationStatus());
  return () => listeners.delete(listener);
}

function assertSession(marker) {
  if (!marker || marker !== currentSessionMarker()) throw new Error("نشست هنگام ثبت اعلان تغییر کرده است.");
}
function bounded(promise, ms) {
  let timer;
  return Promise.race([promise, new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error("آماده‌سازی سرویس اعلان بیش از حد طول کشید.")), ms);
  })]).finally(() => clearTimeout(timer));
}
function sameKey(existing, expected) {
  if (!existing) return true; // older browser: cannot inspect; preserve the valid subscription
  const bytes = new Uint8Array(existing);
  return bytes.length === expected.length && bytes.every((value, i) => value === expected[i]);
}

async function register(marker, prompt) {
  assertSession(marker);
  const permission = getNotificationPermission();
  if (permission !== "granted") {
    if (!prompt || permission !== "default" || await Notification.requestPermission() !== "granted") {
      throw new Error("اجازه نمایش اعلان داده نشده است.");
    }
  }
  const registration = await bounded(navigator.serviceWorker.ready, 15000);
  assertSession(marker);
  const vapidPublicKey = await fetchVapidPublicKey();
  if (!vapidPublicKey) throw new Error("سرور هنوز برای ارسال اعلان پیکربندی نشده است.");
  const key = urlBase64ToUint8Array(vapidPublicKey);
  let subscription = await registration.pushManager.getSubscription();
  assertSession(marker);
  if (subscription && !sameKey(subscription.options?.applicationServerKey, key)) {
    // A copied database or rotated VAPID key cannot authorize an old subscription.
    // The obsolete endpoint will be cleaned up server-side on 404/410.
    await subscription.unsubscribe();
    assertSession(marker);
    subscription = await registration.pushManager.getSubscription();
    if (subscription && !sameKey(subscription.options?.applicationServerKey, key)) {
      throw new Error("اشتراک قدیمی اعلان هنوز حذف نشده است.");
    }
  }
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: key});
  }
  assertSession(marker);
  // Also bind the expected marker at the server, so an interceptor refreshing
  // after an account switch cannot accidentally attach this request to a new SID.
  const binding = {...subscription.toJSON(), session_marker: marker};
  await subscribePush({...binding, client_ready: false});
  assertSession(marker);
  const gateReady = await setDevicePushEnabled(true, marker);
  assertSession(marker);
  if (gateReady === false) throw new Error("ثبت اعلان با تغییر وضعیت دستگاه متوقف شد.");
  // Only release deferred sends after the IndexedDB transaction completed.
  // The ACK cannot bind a different account or revive a revoked session.
  await subscribePush({...binding, client_ready: true});
  assertSession(marker);
  registeredMarker = marker;
  lastSuccess = Date.now();
  return subscription;
}

/** Single flight per page, including simultaneous Login/Layout/Profile requests. */
export async function enablePushNotifications({prompt = true} = {}) {
  if (!isPushSupported()) throw new Error("این مرورگر از اعلان Push پشتیبانی نمی‌کند.");
  const marker = currentSessionMarker();
  if (!marker) throw new Error("نشست معتبر برای اعلان‌ها پیدا نشد.");
  if (inFlight) {
    if (inFlight.marker === marker) return inFlight.promise;
    try { await inFlight.promise; } catch { /* new session can recover */ }
    assertSession(marker);
    return enablePushNotifications({prompt});
  }
  const flight = {marker, promise: null};
  flight.promise = Promise.resolve().then(() => register(marker, prompt)).catch(error => {
    if (registeredMarker === marker) registeredMarker = null;
    throw error;
  }).finally(() => {
    if (inFlight === flight) inFlight = null;
    emit();
  });
  inFlight = flight;
  emit();
  return flight.promise;
}

/** Recover on reconnect, resume, worker update, and bounded periodic checks.
 * Never request a new permission from a background callback. No polling while hidden.
 */
export function startPushMaintenance() {
  if (!isPushSupported()) return () => {};
  let stopped = false, timer = null, busy = false, failures = 0;
  const delays = [10000, 30000, 60000, 300000];
  const clear = () => { clearTimeout(timer); timer = null; };
  const schedule = ms => { clear(); if (!stopped) timer = setTimeout(() => void check(), ms); };
  async function check(force = false) {
    if (stopped || busy) return;
    emit();
    if (document.visibilityState === "hidden" || navigator.onLine === false ||
        getNotificationPermission() !== "granted" || !currentSessionMarker()) {
      schedule(60000);
      return;
    }
    if (!force && registeredMarker === currentSessionMarker() && Date.now() - lastSuccess < 15 * 60000) {
      schedule(15 * 60000 - (Date.now() - lastSuccess));
      return;
    }
    busy = true;
    try {
      await enablePushNotifications({prompt: false});
      failures = 0;
      schedule(15 * 60000);
    } catch {
      schedule(delays[Math.min(failures++, delays.length - 1)]);
    } finally { busy = false; }
  }
  const wake = () => { if (!stopped) void check(true); };
  const visible = () => { if (document.visibilityState !== "hidden") void check(); };
  window.addEventListener("online", wake);
  window.addEventListener("focus", visible);
  document.addEventListener("visibilitychange", visible);
  navigator.serviceWorker.addEventListener("controllerchange", wake);
  void check();
  return () => {
    stopped = true; clear();
    window.removeEventListener("online", wake);
    window.removeEventListener("focus", visible);
    document.removeEventListener("visibilitychange", visible);
    navigator.serviceWorker.removeEventListener("controllerchange", wake);
  };
}

export async function disablePushNotifications() {
  registeredMarker = null; lastSuccess = 0; emit();
  await setDevicePushEnabled(false);
  if (!isPushSupported()) return;
  const registration = await bounded(navigator.serviceWorker.ready, 15000);
  const subscription = await registration.pushManager.getSubscription();
  if (subscription) {
    await unsubscribePush(subscription.endpoint);
    await subscription.unsubscribe();
  }
}
