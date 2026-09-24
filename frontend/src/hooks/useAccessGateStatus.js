/**
 * هوک useAccessGateStatus: وضعیت دروازه‌های دسترسی کاربر جاری را می‌گیرد و خودکار تازه نگه می‌دارد.
 */
import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { fetchMyAccessGateStatus } from "../api/accessGate";

/**
 * هوک وضعیت پیش‌نیازهای دسترسی (Access Gate) کاربر جاری، با به‌روزرسانی خودکار.
 * چون در SPA جابه‌جایی بین صفحات کامپوننت را دوباره mount نمی‌کند، وضعیت در سه حالت تازه می‌شود:
 *   ۱. تغییر مسیر (برگشت به همین صفحه از جای دیگر).
 *   ۲. برگشتن فوکوس به پنجره/تب.
 *   ۳. visibilitychange - برای موبایل، جایی که focus همیشه شلیک نمی‌شود.
 * خروجی: { status, refresh }؛ refresh برای به‌روزرسانی فوری پس از یک عمل مشخص (مثلاً ثبت ارزیابی) است.
 */
export function useAccessGateStatus() {
  const [status, setStatus] = useState(null);
  const location = useLocation();

  // وضعیت را از سرور می‌گیرد و در state می‌گذارد؛ خروجی: داده‌ی وضعیت یا null در صورت خطا
  const refresh = useCallback(async () => {
    try {
      const data = await fetchMyAccessGateStatus();
      setStatus(data);
      return data;
    } catch {
      // در صورت خطا وضعیت قبلی دست‌نخورده می‌ماند؛ خالی کردن آن به معنای «بدون محدودیت» و ممکن است نادرست باشد
      return null;
    }
  }, []);

  // تازه‌سازی هنگام mount و هر تغییر مسیر
  useEffect(() => {
    refresh();
  }, [refresh, location.pathname]);

  // تازه‌سازی با برگشت فوکوس به پنجره یا visible شدن تب؛ listenerها هنگام unmount حذف می‌شوند
  useEffect(() => {
    function onFocus() {
      refresh();
    }
    function onVisible() {
      if (document.visibilityState === "visible") refresh();
    }
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refresh]);

  return { status, refresh };
}
