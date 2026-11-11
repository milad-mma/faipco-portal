/**
 * FAIPCO PWA release lifecycle (v7).
 *
 * No 30s version.json polling and no 60s Service Worker polling.
 * The backend notifies authenticated, online clients AFTER a successful
 * deployment. The notification starts registration.update(), but the UI is
 * shown ONLY after Workbox has finished installing the new SW (waiting).
 * When Android resumes after sleep, visibility/focus triggers one recovery
 * check; it cannot publish or activate an unfinished release.
 */
const ACTIVATION_WAIT_MS = 12 * 1000;
const RELOAD_FEEDBACK_MS = 350;
const RELOAD_RECEIPT_KEY = "faipco-pwa-update-receipt-v1";
const RECEIPT_MAX_AGE_MS = 2 * 60 * 1000;
export const UPDATE_ACTIVITY_EVENT = "faipco-update-activity";
const updateActivityReasons = new Set();

/** Update activities include the admin's server deployment and a user's SW activation.
 * A separate event lets the offline banner distinguish planned deployment from loss of connectivity.
 */
export function setPortalUpdateActivity(reason, active) {
  if (active) updateActivityReasons.add(reason);
  else updateActivityReasons.delete(reason);
  window.dispatchEvent(new CustomEvent(UPDATE_ACTIVITY_EVENT, {
    detail: { active: updateActivityReasons.size > 0 },
  }));
}

export function isPortalUpdateActive() {
  return updateActivityReasons.size > 0;
}

/** Show a confirmation on the NEW page, not just a spinner on the page being replaced.
 * sessionStorage is tab-scoped, is removed immediately, and never stores credentials.
 */
export function consumeAppliedUpdateReceipt() {
  try {
    const raw = window.sessionStorage.getItem(RELOAD_RECEIPT_KEY);
    window.sessionStorage.removeItem(RELOAD_RECEIPT_KEY);
    if (!raw) return null;
    const receipt = JSON.parse(raw);
    if (receipt && Number.isFinite(receipt.at) && Date.now() - receipt.at >= 0 &&
        Date.now() - receipt.at < RECEIPT_MAX_AGE_MS &&
        (receipt.kind === "release" || receipt.kind === "cache_refresh")) {
      return receipt.kind;
    }
  } catch { /* storage may be unavailable in Android private modes */ }
  return null;
}

const CURRENT_BUILD = typeof __APP_BUILD__ !== "undefined" ? String(__APP_BUILD__) : null; // eslint-disable-line no-undef
export const UPDATE_READY_EVENT = "faipco-update-ready";

let waitingRegistration = null;
let swRegistration = null;
let announced = false;
let registering = false;
let checking = false;
let pendingKind = "release";
let lastRefreshStamp = null;
const observedRegistrations = new WeakSet();

function notifyUpdateReady(registration) {
  if (!registration?.waiting || !navigator.serviceWorker.controller) return;
  waitingRegistration = registration;
  if (announced) return;
  announced = true;
  window.dispatchEvent(new CustomEvent(UPDATE_READY_EVENT, { detail: { kind: pendingKind } }));
}

function observeRegistration(registration) {
  if (!registration || observedRegistrations.has(registration)) return;
  observedRegistrations.add(registration);
  const onUpdateFound = () => {
    const installing = registration.installing;
    if (!installing) return;
    installing.addEventListener("statechange", () => {
      if (installing.state === "installed") notifyUpdateReady(registration);
    });
    if (installing.state === "installed") notifyUpdateReady(registration);
  };
  registration.addEventListener("updatefound", onUpdateFound);
  onUpdateFound();
}

async function checkForInstalledUpdate(kind = "release") {
  if (checking || announced || !("serviceWorker" in navigator)) return;
  pendingKind = kind;
  checking = true;
  try {
    const registration = swRegistration || (await navigator.serviceWorker.getRegistration());
    if (!registration) return;
    swRegistration = registration;
    observeRegistration(registration);
    if (registration.waiting) {
      notifyUpdateReady(registration);
      return;
    }
    // This fetch is triggered by a deployment event or resume, not a timer.
    await registration.update();
    if (registration.waiting) notifyUpdateReady(registration);
  } catch {
    // Network down / deployment restarting: wait for reconnect/resume.
  } finally {
    checking = false;
  }
}

/** Backend's published version is a hint to CHECK for a new worker, not proof
 * that the new worker has completed downloading its full precache. */
export function onReleasePublished(build) {
  if (typeof build !== "string" || !/^[\w.-]{1,96}$/.test(build)) return;
  if (CURRENT_BUILD && build === CURRENT_BUILD) return;
  void checkForInstalledUpdate("release");
}

/** A manual server-side SW refresh is distinct from publishing a new build.
 * It is allowed even when build === CURRENT_BUILD. */
export function onCacheRefreshPublished(stamp) {
  if (typeof stamp !== "string" || !/^\d{14}(?:\d{6})?$/.test(stamp)) return;
  if (stamp === lastRefreshStamp) return;
  lastRefreshStamp = stamp;
  void checkForInstalledUpdate("cache_refresh");
}

/** Applies only a fully installed waiting worker, on explicit user approval. */
export async function applyPendingUpdate({ onPhase } = {}) {
  if (!("serviceWorker" in navigator)) return { ok: false, reason: "unsupported" };
  let reloading = false;
  try {
    // Check all known registrations: a previous waiting worker may already have
    // changed while a new registration was installed in the background.
    const fresh = await navigator.serviceWorker.getRegistration();
    const candidates = [waitingRegistration, swRegistration, fresh];
    const worker = candidates.find((registration) => registration?.waiting)?.waiting;
    if (!worker) return { ok: false, reason: "not-ready" };

    setPortalUpdateActivity("sw-activation", true);
    onPhase?.("activating");
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
        if (navigator.serviceWorker.controller === worker) finish(true);
      } catch {
        finish(false);
      }
    });
    if (!activated) return { ok: false, reason: "activation-timeout" };

    onPhase?.("reloading");
    // A receipt is written only after a real controller change, immediately
    // before the page reload. No broad cache deletion and no logout.
    try {
      window.sessionStorage.setItem(RELOAD_RECEIPT_KEY, JSON.stringify({
        kind: pendingKind, at: Date.now(),
      }));
    } catch { /* storage blocked: update must still complete */ }
    await new Promise((resolve) => setTimeout(resolve, RELOAD_FEEDBACK_MS));
    window.location.reload();
    reloading = true;
    return { ok: true };
  } catch {
    return { ok: false, reason: "unexpected" };
  } finally {
    if (!reloading) setPortalUpdateActivity("sw-activation", false);
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
      if (registration.waiting) notifyUpdateReady(registration);
      observeRegistration(registration);
    } catch (err) {
      console.error("ثبت Service Worker ناموفق بود:", err);
    } finally {
      registering = false;
    }
  }

  if (document.readyState === "complete") void register();
  else window.addEventListener("load", register, { once: true });

  // Recovery paths: one update check after re-entering the app or reconnecting.
  // Unlike polling, none of these triggers fires every N seconds.
  const checkOnReturn = () => {
    if (!swRegistration) void register();
    else void checkForInstalledUpdate();
  };
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") checkOnReturn();
  });
  window.addEventListener("focus", checkOnReturn);
  window.addEventListener("online", checkOnReturn);
  // Do not reload on an unsolicited controllerchange: unsaved forms must remain intact.
}
