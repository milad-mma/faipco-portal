/** Version events only. Separate from GPS/presence WebSocket and all HR modules.
 * A session-authenticated WebSocket can deliver a new build event to this tab;
 * after Android sleep, reconnect replays the live published version.
 */
import { onCacheRefreshPublished, onReleasePublished } from "./serviceWorker";

const RECONNECT_MS = 5_000;
const PROTOCOL = "faipco-release";

function releaseWsUrl() {
  const base = import.meta.env.VITE_API_BASE_URL || "/api/v1";
  const url = new URL(`${base.replace(/\/$/, "")}/system/release-ws`, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

export function connectReleaseNotifications() {
  if (!("WebSocket" in window)) return () => {};
  let stopped = false;
  let socket = null;
  let reconnect = null;

  const connect = () => {
    if (stopped || document.visibilityState === "hidden") return;
    const token = localStorage.getItem("access_token");
    if (!token) return;
    try {
      // JWT is sent in the handshake subprotocol header, never in URL/query.
      socket = new WebSocket(releaseWsUrl(), [PROTOCOL, `auth.${token}`]);
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "portal.release") onReleasePublished(data.build);
          else if (data.type === "portal.cache_refresh") onCacheRefreshPublished(data.stamp);
        } catch { /* malformed or irrelevant messages are ignored */ }
      };
      socket.onclose = (event) => {
        socket = null;
        if (!stopped && document.visibilityState !== "hidden") {
          reconnect = setTimeout(connect, event.code === 4401 ? 60_000 : RECONNECT_MS);
        }
      };
      socket.onerror = () => socket?.close();
    } catch {
      reconnect = setTimeout(connect, RECONNECT_MS);
    }
  };

  const resume = () => {
    if (stopped || document.visibilityState === "hidden") return;
    if (!socket || socket.readyState === WebSocket.CLOSED) {
      clearTimeout(reconnect);
      connect();
    }
  };
  const onVisibility = () => {
    if (document.visibilityState === "hidden") {
      // Prevent background sockets on Android from accumulating stale sessions.
      socket?.close();
      socket = null;
      clearTimeout(reconnect);
    } else {
      resume();
    }
  };
  document.addEventListener("visibilitychange", onVisibility);
  window.addEventListener("online", resume);
  window.addEventListener("focus", resume);
  connect();

  return () => {
    stopped = true;
    clearTimeout(reconnect);
    socket?.close();
    document.removeEventListener("visibilitychange", onVisibility);
    window.removeEventListener("online", resume);
    window.removeEventListener("focus", resume);
  };
}
