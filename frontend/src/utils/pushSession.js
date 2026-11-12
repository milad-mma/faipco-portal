/** Persist whether THIS browser has a session-linked Push registration.
 * IndexedDB is shared by the page and service worker (unlike localStorage).
 * A missing value is DENY: after upgrading, inactive legacy endpoints cannot
 * display delayed notifications until authenticated re-registration succeeds.
 */
const DB_NAME = "faipco-push-security-v1";
let localUpdateVersion = 0;

function openStore() {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") return reject(new Error("IndexedDB unavailable"));
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("meta")) db.createObjectStore("meta");
      if (!db.objectStoreNames.contains("seen")) db.createObjectStore("seen");
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function setDevicePushEnabled(enabled, sessionMarker = null) {
  const updateVersion = ++localUpdateVersion;
  // Update the worker immediately as well: if the page is navigating away,
  // the worker can finish writing the flag using event.waitUntil().
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.controller?.postMessage({ type: "FAIPCO_PUSH_SESSION", enabled: Boolean(enabled), sessionMarker });
  }
  const db = await openStore();
  try {
    if (updateVersion !== localUpdateVersion) return;
    await new Promise((resolve, reject) => {
      const tx = db.transaction("meta", "readwrite");
      const store = tx.objectStore("meta");
      store.put(Boolean(enabled), "enabled");
      store.put(enabled ? sessionMarker : null, "sessionMarker");
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}
