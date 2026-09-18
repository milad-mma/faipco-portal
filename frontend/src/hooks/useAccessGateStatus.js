import { useCallback, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { fetchMyAccessGateStatus } from "../api/accessGate";

/**
 * وضعیت پیش‌نیازهای دسترسی، با به‌روزرسانی خودکار.
 *
 * ⚠️ رفع باگ واقعی (گزارش کاربر): قبلاً وضعیت فقط یک‌بار هنگام mount
 * گرفته می‌شد. چون در SPA رفتن به صفحه اطلاعیه‌ها و برگشتن، کامپوننت را
 * دوباره mount نمی‌کند، کاربر بعد از خواندن اطلاعیه‌هایش همچنان همان
 * هشدار قدیمی را می‌دید تا وقتی صفحه را دستی رفرش کند.
 *
 * حالا سه محرک برای تازه‌سازی وجود دارد:
 *   ۱. تغییر مسیر (برگشت به همین صفحه از جای دیگر).
 *   ۲. برگشتن فوکوس به پنجره/تب.
 *   ۳. visibilitychange - برای موبایل، جایی که focus همیشه شلیک نمی‌شود.
 *
 * `refresh` هم برگردانده می‌شود تا صفحه بتواند بعد از یک عمل مشخص
 * (مثلاً ثبت ارزیابی) فوراً وضعیت را به‌روز کند.
 */
export function useAccessGateStatus() {
  const [status, setStatus] = useState(null);
  const location = useLocation();

  const refresh = useCallback(async () => {
    try {
      const data = await fetchMyAccessGateStatus();
      setStatus(data);
      return data;
    } catch {
      // ⚠️ در صورت خطا وضعیت قبلی دست‌نخورده می‌ماند - صفر کردنش یعنی
      // ادعای «هیچ محدودیتی نیست» که ممکن است غلط باشد.
      return null;
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, location.pathname]);

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
