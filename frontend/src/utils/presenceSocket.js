import { useEffect, useRef } from "react";
import { getCurrentPosition } from "./geolocation";

const HEARTBEAT_INTERVAL_MS = 45_000; // باید کمتر از Timeout سمت سرور (۹۰ ثانیه) باشد
const RECONNECT_DELAY_MS = 5_000;
const LOG_PREFIX = "[Presence]";

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
 *
 * تشخیص مشکل: همه مراحل (اتصال، ارسال Heartbeat، پاسخ سرور، قطعی) توی
 * Console (پیشوند "[Presence]") لاگ می‌شن — کافیه DevTools رو باز کنید.
 */
export function usePresenceMonitor(enabled) {
  const socketRef = useRef(null);
  const heartbeatIntervalRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const stoppedRef = useRef(false);

  useEffect(() => {
    if (!enabled) {
      console.info(`${LOG_PREFIX} غیرفعال است (کاربر مجوز attendance.clock_in_out ندارد).`);
      return undefined;
    }
    if (!("geolocation" in navigator)) {
      console.warn(`${LOG_PREFIX} مرورگر از Geolocation پشتیبانی نمی‌کند.`);
      return undefined;
    }
    if (!("WebSocket" in window)) {
      console.warn(`${LOG_PREFIX} مرورگر از WebSocket پشتیبانی نمی‌کند.`);
      return undefined;
    }

    stoppedRef.current = false;

    function sendHeartbeat() {
      const socket = socketRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        console.warn(`${LOG_PREFIX} تلاش برای ارسال Heartbeat ولی اتصال باز نیست.`);
        return;
      }
      // enableHighAccuracy:true عمداً است — چون این قابلیت برای محدوده مجاز
      // فقط ۱۰۰-۳۰۰ متری طراحی شده، دقت پایین (مثل موقعیت‌یابی بر پایه IP/شبکه
      // که خطایش می‌تواند صدها کیلومتر باشد) عملاً این قابلیت را بی‌فایده
      // می‌کند؛ هزینه‌ش کمی باتری بیشتر روی گوشی است، ولی لازم است.
      getCurrentPosition({ enableHighAccuracy: true, timeout: 20000 })
        .then((position) => {
          console.info(
            `${LOG_PREFIX} موقعیت گرفته شد:`,
            position.latitude,
            position.longitude,
            `دقت: ±${Math.round(position.accuracyMeters)}m`
          );
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(
              JSON.stringify({
                latitude: position.latitude,
                longitude: position.longitude,
                accuracy_meters: position.accuracyMeters,
              })
            );
            console.info(`${LOG_PREFIX} Heartbeat ارسال شد.`);
          }
        })
        .catch((err) => {
          console.error(`${LOG_PREFIX} گرفتن موقعیت GPS ناموفق بود — Heartbeat خالی ارسال می‌شود:`, err.message);
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({}));
          }
        });
    }

    function connect() {
      if (stoppedRef.current) return;
      const token = localStorage.getItem("access_token");
      if (!token) {
        console.warn(`${LOG_PREFIX} توکن ورود پیدا نشد — اتصال برقرار نمی‌شود.`);
        return;
      }

      const url = buildPresenceWsUrl(token);
      console.info(`${LOG_PREFIX} در حال اتصال به`, url.replace(/token=[^&]+/, "token=***"));
      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.onopen = () => {
        console.info(`${LOG_PREFIX} اتصال برقرار شد ✅`);
        sendHeartbeat();
        heartbeatIntervalRef.current = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS);
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.status === "logged") {
            console.info(`${LOG_PREFIX} ✅ ثبت شد — سایت: ${data.matched_site_name || "—"}, فاصله: ${data.distance_meters != null ? Math.round(data.distance_meters) + "m" : "—"}`);
          } else if (data.status === "outside_geofence") {
            console.warn(
              `${LOG_PREFIX} ⛔ خارج از محدوده — سایت نزدیک: ${data.matched_site_name || "—"}, فاصله: ${data.distance_meters != null ? Math.round(data.distance_meters) + "m" : "—"}, شعاع مجاز: ${data.allowed_radius_meters != null ? data.allowed_radius_meters + "m" : "—"}`
            );
          } else if (data.status === "no_position") {
            console.warn(`${LOG_PREFIX} موقعیتی برای این Heartbeat ارسال نشد.`);
          } else if (data.status === "low_accuracy") {
            console.warn(`${LOG_PREFIX} ⚠️ دقت موقعیت خیلی پایین بود (±${Math.round(data.accuracy_meters)}m) — نادیده گرفته شد. این معمولاً یعنی GPS واقعی گوشی استفاده نشده (موقعیت‌یابی بر پایه IP/شبکه بوده). روی گوشی واقعی و با GPS روشن تست کنید.`);
          }
        } catch {
          // نادیده گرفته می‌شود
        }
      };

      socket.onclose = (event) => {
        console.warn(`${LOG_PREFIX} اتصال قطع شد (کد ${event.code}) — تلاش مجدد در ${RECONNECT_DELAY_MS / 1000} ثانیه...`);
        clearInterval(heartbeatIntervalRef.current);
        if (!stoppedRef.current) {
          reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      socket.onerror = () => {
        console.error(`${LOG_PREFIX} خطا در اتصال WebSocket.`);
        socket.close();
      };
    }

    connect();

    return () => {
      console.info(`${LOG_PREFIX} در حال بستن (کامپوننت Unmount شد یا enabled=false شد).`);
      stoppedRef.current = true;
      clearInterval(heartbeatIntervalRef.current);
      clearTimeout(reconnectTimeoutRef.current);
      socketRef.current?.close();
    };
  }, [enabled]);
}
