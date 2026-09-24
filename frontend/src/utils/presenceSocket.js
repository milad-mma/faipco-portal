/**
 * هوک usePresenceMonitor: اتصال WebSocket حضور آنلاین پرسنل.
 * تا وقتی برنامه باز است اتصال را نگه می‌دارد، به صورت دوره‌ای Heartbeat همراه موقعیت GPS می‌فرستد،
 * پس از قطع اتصال دوباره وصل می‌شود و همه‌ی مراحل را با پیشوند [Presence] در Console لاگ می‌کند.
 */
import { useEffect, useRef } from "react";
import { getCurrentPosition } from "./geolocation";

const HEARTBEAT_INTERVAL_MS = 45_000; // باید کمتر از Timeout سمت سرور (۹۰ ثانیه) باشد
const RECONNECT_DELAY_MS = 5_000; // فاصله‌ی تلاش مجدد برای اتصال پس از قطع
const LOG_PREFIX = "[Presence]"; // پیشوند لاگ‌های Console

/**
 * ساخت آدرس WebSocket حضور از آدرس پایه‌ی API (تبدیل http به ws، یا ساخت از Origin صفحه برای مسیر نسبی).
 * ورودی: توکن دسترسی؛ خروجی: آدرس کامل presence-ws با توکن در query string.
 */
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
 * مانند نشانگر آنلاین در سیستم‌های چت، تا وقتی کامپوننت mount است یک اتصال WebSocket باز نگه می‌دارد؛
 * سرور لحظه‌ی وصل شدن را شروع Session و لحظه‌ی قطع شدن (بستن تب یا قطعی شبکه) را پایان Session ثبت می‌کند.
 * ورودی: enabled (فقط برای پرسنل دارای مجوز ثبت ورود/خروج GPS، تا از بقیه دسترسی مکان خواسته نشود). خروجی ندارد.
 * همه‌ی مراحل (اتصال، Heartbeat، پاسخ سرور، قطعی) با پیشوند "[Presence]" در Console لاگ می‌شوند.
 */
export function usePresenceMonitor(enabled) {
  const socketRef = useRef(null); // اتصال WebSocket فعلی
  const heartbeatIntervalRef = useRef(null); // شناسه‌ی setInterval ارسال Heartbeat
  const reconnectTimeoutRef = useRef(null); // شناسه‌ی setTimeout اتصال مجدد
  const stoppedRef = useRef(false); // پس از unmount، true می‌شود تا اتصال مجدد انجام نشود

  // با فعال شدن، پس از بررسی پشتیبانی مرورگر اتصال برقرار می‌شود؛ هنگام unmount یا غیرفعال شدن همه‌چیز بسته می‌شود
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

    // موقعیت GPS را می‌گیرد و روی اتصال باز می‌فرستد؛ در صورت خطای GPS یک Heartbeat خالی ارسال می‌شود
    function sendHeartbeat() {
      const socket = socketRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        console.warn(`${LOG_PREFIX} تلاش برای ارسال Heartbeat ولی اتصال باز نیست.`);
        return;
      }
      // enableHighAccuracy برای استفاده از GPS واقعی لازم است چون محدوده‌ی مجاز سایت‌ها ۱۰۰ تا ۳۰۰ متر است
      // و موقعیت‌یابی بر پایه‌ی IP/شبکه خطای بسیار بزرگ‌تری دارد
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

    // اتصال WebSocket را با توکن ذخیره‌شده برقرار می‌کند و handlerهای باز شدن، پیام، قطع و خطا را تنظیم می‌کند
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

      // پس از اتصال: ارسال فوری یک Heartbeat و شروع ارسال دوره‌ای
      socket.onopen = () => {
        console.info(`${LOG_PREFIX} اتصال برقرار شد ✅`);
        sendHeartbeat();
        heartbeatIntervalRef.current = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS);
      };

      // پاسخ سرور به هر Heartbeat (ثبت‌شده، خارج از محدوده، بدون موقعیت، دقت پایین) فقط در Console لاگ می‌شود
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
          // پیام غیر JSON نادیده گرفته می‌شود
        }
      };

      // پس از قطع اتصال، ارسال Heartbeat متوقف و در صورت عدم توقف هوک، اتصال مجدد زمان‌بندی می‌شود
      socket.onclose = (event) => {
        console.warn(`${LOG_PREFIX} اتصال قطع شد (کد ${event.code}) — تلاش مجدد در ${RECONNECT_DELAY_MS / 1000} ثانیه...`);
        clearInterval(heartbeatIntervalRef.current);
        if (!stoppedRef.current) {
          reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      // در خطا اتصال بسته می‌شود تا onclose اتصال مجدد را انجام دهد
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
