/**
 * FAIPCO PWA update lifecycle.
 *
 * Detection and activation are separate: version.json can announce a newer
 * deployment before Workbox has finished precaching its files. Never delete
 * the active worker's caches or unregister a worker while an update installs.
 * The active shell stays intact until the NEW worker controls this page.
 */
const UPDATE_CHECK_INTERVAL_MS = 60 * 1000;
const VERSION_CHECK_INTERVAL_MS = 30 * 1000;
const INSTALL_WAIT_MS = 12 * 1000;
const ACTIVATION_WAIT_MS = 12 * 1000;
const VERSION_REQUEST_TIMEOUT_MS = 6 * 1000;
const CURRENT_BUILD = typeof __APP_BUILD__ !== "undefined" ? __APP_BUILD__ : null; // eslint-disable-line no-undef

export const UPDATE_READY_EVENT = "faipco-update-ready";

let waitingRegistration = null;
let swRegistration = null;
let announced = false;
let checkingVersion = false;
let registering = false;

function notifyUpdateReady(registration) {
  if (registration) waitingRegistration = registration;
  if (announced) return;
  announced = true;
  window.dispatchEvent(new CustomEvent(UPDATE_READY_EVENT));
}

async function checkDeployedVersion() {
  if (!CURRENT_BUILD || announced || checkingVersion) return;
  checkingVersion = true;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), VERSION_REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`/version.json?t=${Date.now()}`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) return;
    const data = await response.json();
    if (data?.build && String(data.build) !== CURRENT_BUILD) {
      // This is detection only. The new worker may still be downloading.
      notifyUpdateReady(null);
      swRegistration?.update().catch(() => {});
    }
  } catch {
    // Connection is offline/slow; a later check will try again.
  } finally {
    clearTimeout(timer);
    checkingVersion = false;
  }
}

/** Wait for an *actually waiting* worker, without cancelling a pending install. */
function waitForWaiting(registration, timeoutMs) {
  return new Promise((resolve) => {
    if (!registration) return resolve(null);
    if (registration.waiting) return resolve(registration.waiting);

    let finished = false;
    const observedWorkers = new Map();
    let timer;
    function finish(worker) {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      registration.removeEventListener("updatefound", onUpdateFound);
      for (const [item, handler] of observedWorkers) {
        item.removeEventListener("statechange", handler);
      }
      resolve(worker);
    }
    function checkWaiting() {
      if (registration.waiting) finish(registration.waiting);
    }
    function watch(worker) {
      if (!worker || observedWorkers.has(worker)) return;
      const onStateChange = () => checkWaiting();
      observedWorkers.set(worker, onStateChange);
      worker.addEventListener("statechange", onStateChange);
      checkWaiting();
    }
    function onUpdateFound() {
      watch(registration.installing);
      checkWaiting();
    }

    registration.addEventListener("updatefound", onUpdateFound);
    watch(registration.installing);
    timer = setTimeout(() => finish(registration.waiting || null), timeoutMs);
    // update() can take a long time on Android; do not await it here.
    registration.update().then(checkWaiting).catch(() => {});
    checkWaiting();
  });
}

/**
 * Activated only after an explicit click. Returns {ok:false} on timeouts so
 * the UI can offer a retry instead of showing an endless progress indicator.
 */
export async function applyPendingUpdate() {
  if (!("serviceWorker" in navigator)) return { ok: false, reason: "unsupported" };
  try {
    const registration = waitingRegistration || swRegistration ||
      (await navigator.serviceWorker.getRegistration());
    if (!registration) return { ok: false, reason: "unavailable" };

    const worker = registration.waiting || (await waitForWaiting(registration, INSTALL_WAIT_MS));
    if (!worker) return { ok: false, reason: "install-timeout" };

    // Register listener BEFORE messaging worker, so fast transitions are not lost.
    const activated = await new Promise((resolve) => {
      let done = false;
      const finish = (ok) => {
        if (done) return;
        done = true;
        clearTimeout(timer);
        navigator.serviceWorker.removeEventListener("controllerchange", onChange);
        resolve(ok);
      };
      const onChange = () => finish(true);
      navigator.serviceWorker.addEventListener("controllerchange", onChange);
      const timer = setTimeout(() => finish(false), ACTIVATION_WAIT_MS);
      try {
        worker.postMessage({ type: "SKIP_WAITING" });
        // Rare case: the new worker was already controlling the page.
        if (navigator.serviceWorker.controller === worker) finish(true);
      } catch {
        finish(false);
      }
    });

    if (!activated) return { ok: false, reason: "activation-timeout" };
    // The new worker owns the page; its complete precache is ready. Old caches
    // are cleaned up by Workbox on activation, not deleted while in use.
    window.location.reload();
    return { ok: true };
  } catch {
    return { ok: false, reason: "unexpected" };
  }
}

export function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;

  async function register() {
    if (registering || swRegistration) return;
    registering = true;
    try {
      const registration = await navigator.serviceWorker.register("/sw.js");
      swRegistration = registration;
      if (registration.waiting && navigator.serviceWorker.controller) {
        notifyUpdateReady(registration);
      }
      registration.addEventListener("updatefound", () => {
        const newWorker = registration.installing;
        if (!newWorker) return;
        newWorker.addEventListener("statechange", () => {
          if (newWorker.state === "installed" && navigator.serviceWorker.controller) {
            notifyUpdateReady(registration);
          }
        });
      });
      // First check is immediate. Periodic polling continues while app is open.
      checkDeployedVersion();
    } catch (err) {
      console.error("ثبت Service Worker ناموفق بود:", err);
      // Keep retrying when online; important when Android starts without network.
    } finally {
      registering = false;
    }
  }

  if (document.readyState === "complete") register();
  else window.addEventListener("load", register, { once: true });

  setInterval(() => swRegistration?.update().catch(() => {}), UPDATE_CHECK_INTERVAL_MS);
  setInterval(checkDeployedVersion, VERSION_CHECK_INTERVAL_MS);

  const checkNow = () => {
    if (!swRegistration) register();
    else swRegistration.update().catch(() => {});
    checkDeployedVersion();
  };
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") checkNow();
  });
  window.addEventListener("focus", checkNow);
  window.addEventListener("online", checkNow);

  // Do not reload on spontaneous controller changes. Refreshing an open form
  // without consent could destroy unsaved work. applyPendingUpdate handles the
  // explicit, user-approved controller transition instead.
}
