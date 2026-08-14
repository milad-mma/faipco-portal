import { useEffect, useRef } from "react";
import { getCurrentPosition } from "./geolocation";

const HEARTBEAT_INTERVAL_MS = 45_000; // باید کمتر از Timeout سمت سرور (۹۰ ثانیه) باشد
const RECONNECT_DELAY_MS = 5_000;

function buildPresenceWsUrl(token) {
  const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";
  let wsBase;
  if (apiBase.startsWith("http")) {
    wsBase = apiBase.replace(/^http/, "ws");
  } else {
    // مسیر نسبی (مثلاً "/api/v1") — بر اساس Origin فعلی صفحه ساخته می‌شود
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    wsBase = `${wsProtocol}//${window.location.host}${apiBase}`;
  }
  return `${wsBase}/attendance/presence-ws?token=${encodeURIComponent(token)}`;
}

/**
 * دقیقاً مثل نشانگر آنلاین یک سیستم چت: تا وقتی این کامپوننت زنده است (اپ باز
 * است)، یک اتصال WebSocket به سرور باز نگه می‌دارد. سرور خودش، لحظه‌ی
 * وصل‌شدن را «شروع Session» و لحظه‌ی قطع‌شدن (چه با بستن تب، چه قطعی شبکه) را
 * «پایان Session» ثبت می‌کند — مدت‌زمان دقیق، نه تخمینی.
 *
 * فقط برای پرسنلی که وارد آزمایش «ثبت ورود/خروج GPS» شده‌اند فعال می‌شود
 * (enabled=false برای بقیه) — تا مرورگر بقیه پرسنل مجبور به نمایش درخواست
 * دسترسی مکان نشود.
 */
export function usePresenceMonitor(enabled) {
  const socketRef = useRef(null);
  const heartbeatIntervalRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const stoppedRef = useRef(false);

  useEffect(() => {
    if (!enabled) return undefined;
    if (!("geolocation" in navigator) || !("WebSocket" in window)) return undefined;

    stoppedRef.current = false;

    function sendHeartbeat() {
      const socket = socketRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      getCurrentPosition({ enableHighAccuracy: false, timeout: 20000 })
        .then((position) => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(
              JSON.stringify({
                latitude: position.latitude,
                longitude: position.longitude,
                accuracy_meters: position.accuracyMeters,
              })
            );
          }
        })
        .catch(() => {
          // موقعیت نگرفتیم — همچنان یک Heartbeat خالی می‌فرستیم تا لااقل
          // اتصال «زنده» شمرده شود (Session باز بماند)، فقط بدون موقعیت جدید
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({}));
          }
        });
    }

    function connect() {
      if (stoppedRef.current) return;
      const token = localStorage.getItem("access_token");
      if (!token) return;

      const socket = new WebSocket(buildPresenceWsUrl(token));
      socketRef.current = socket;

      socket.onopen = () => {
        sendHeartbeat();
        heartbeatIntervalRef.current = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS);
      };

      socket.onclose = () => {
        clearInterval(heartbeatIntervalRef.current);
        if (!stoppedRef.current) {
          reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      socket.onerror = () => {
        socket.close();
      };
    }

    connect();

    return () => {
      stoppedRef.current = true;
      clearInterval(heartbeatIntervalRef.current);
      clearTimeout(reconnectTimeoutRef.current);
      socketRef.current?.close();
    };
  }, [enabled]);
}
