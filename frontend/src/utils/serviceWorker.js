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
const CURRENT_BUILD = typeof __APP_BUILD__ !== "undefined" ? String(__APP_BUILD__) : null; // eslint-disable-line no-undef
export const UPDATE_READY_EVENT = "faipco-update-ready";

let waitingRegistration = null;
let swRegistration = null;
let announced = false;
let registering = false;
let checking = false;
const observedRegistrations = new WeakSet();

function notifyUpdateReady(registration) {
  if (!registration?.waiting || !navigator.serviceWorker.controller) return;
  waitingRegistration = registration;
  if (announced) return;
  announced = true;
  window.dispatchEvent(new CustomEvent(UPDATE_READY_EVENT));
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

async function checkForInstalledUpdate() {
  if (checking || announced || !("serviceWorker" in navigator)) return;
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
  void checkForInstalledUpdate();
}

/** Applies only a fully installed waiting worker, on explicit user approval. */
export async function applyPendingUpdate() {
  if (!("serviceWorker" in navigator)) return { ok: false, reason: "unsupported" };
  try {
    const registration = waitingRegistration || swRegistration ||
      (await navigator.serviceWorker.getRegistration());
    const worker = registration?.waiting;
    if (!worker) return { ok: false, reason: "not-ready" };

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
