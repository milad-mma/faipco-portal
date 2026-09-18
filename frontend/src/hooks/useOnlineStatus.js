import { useCallback, useEffect, useRef, useState } from "react";

const HEALTH_CHECK_URL = "/api/health";
const HEALTH_CHECK_INTERVAL_MS = 20_000; // هر ۲۰ ثانیه، وقتی مرورگر می‌گوید آنلاین است، یک‌بار واقعی تأیید می‌شود
const HEALTH_CHECK_TIMEOUT_MS = 5_000;

// ⚠️ رفع باگ واقعی (گزارش کاربر: «وسط آپدیت سامانه یکدفعه می‌گوید اتصال
// اینترنت قطع شده»): یک شکستِ تکیِ درخواست هرگز نباید بلافاصله به معنای
// «آفلاین» گرفته شود. هنگام آپدیت، install.sh خودِ سرویس بک‌اند را
// Restart می‌کند و /api/health برای چند ثانیه در دسترس نیست - در حالی که
// اینترنت کاربر کاملاً سالم است. حالا فقط بعد از چند شکستِ پشت‌سرهم،
// وضعیت آفلاین اعلام می‌شود.
const FAILURES_BEFORE_OFFLINE = 3;
// ⚠️ وقتی مشکوک به قطعی هستیم، به‌جای صبر ۲۰ ثانیه‌ای، سریع‌تر دوباره
// تلاش می‌کنیم - هم قطعی واقعی زودتر تشخیص داده می‌شود، هم بازگشت سرور
// بعد از Restart سریع‌تر دیده می‌شود.
const RETRY_INTERVAL_MS = 3_000;
// ⚠️ وقتی آفلاین هستیم هم باید مرتب تلاش کنیم - چون رویداد `online`
// مرورگر در بعضی حالت‌ها (مثل بازگشت خودِ سرور، بدون تغییر رابط شبکه)
// اصلاً شلیک نمی‌شود و کاربر تا رفرش دستی در حالت آفلاین گیر می‌کرد.
const OFFLINE_RECHECK_INTERVAL_MS = 5_000;

/**
 * فقط `navigator.onLine` به‌تنهایی کافی نیست — این فقط یعنی «یک رابط شبکه
 * فعال است» (مثلاً وای‌فای وصل است)، نه اینکه واقعاً اینترنت/سرور در دسترس
 * است (مثلاً پشت یک Captive Portal، یا خودِ سرور پرتال از کار افتاده). برای
 * همین، علاوه بر رویدادهای فوری مرورگر (`online`/`offline`)، به‌صورت دوره‌ای
 * هم یک درخواست واقعی و سبک به `/api/health` زده می‌شود.
 *
 * این Endpoint در Service Worker (سطح NetworkOnly برای همه مسیرهای /api/)
 * از قبل هرگز از Cache پاسخ داده نمی‌شود — پس این چک همیشه وضعیت واقعی
 * لحظه را می‌سنجد، نه یک پاسخ قدیمی.
 */
async function checkRealConnectivity() {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), HEALTH_CHECK_TIMEOUT_MS);
  try {
    const response = await fetch(HEALTH_CHECK_URL, {
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeoutId);
  }
}

export function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [isChecking, setIsChecking] = useState(false);
  const isMounted = useRef(true);
  const failureCountRef = useRef(0);
  const timerRef = useRef(null);

  /**
   * چک واقعی وضعیت. `force` برای وقتی است که کاربر خودش دکمه «تلاش
   * دوباره» را می‌زند - در آن حالت نتیجه بلافاصله اعمال می‌شود و منتظر
   * چند شکست پشت‌سرهم نمی‌مانیم.
   */
  const recheck = useCallback(async ({ force = false } = {}) => {
    setIsChecking(true);
    const reallyOnline = await checkRealConnectivity();
    if (!isMounted.current) return reallyOnline;

    if (reallyOnline) {
      failureCountRef.current = 0;
      setIsOnline(true);
    } else {
      failureCountRef.current += 1;
      // ⚠️ فقط بعد از چند شکست پشت‌سرهم (یا وقتی کاربر خودش درخواست کرده)
      // آفلاین اعلام کن - تا یک وقفه کوتاه (مثل Restart بک‌اند هنگام
      // آپدیت) باعث پیام گمراه‌کننده «اینترنت قطع شد» نشود.
      if (force || failureCountRef.current >= FAILURES_BEFORE_OFFLINE) {
        setIsOnline(false);
      }
    }
    setIsChecking(false);
    return reallyOnline;
  }, []);

  useEffect(() => {
    isMounted.current = true;

    function handleBrowserOffline() {
      // سیگنال «آفلاین» خودِ مرورگر فوری و قابل‌اعتماد است — نیازی به تأیید
      // با درخواست شبکه نیست (که خودش هم شکست می‌خورد).
      failureCountRef.current = FAILURES_BEFORE_OFFLINE;
      setIsOnline(false);
    }
    function handleBrowserOnline() {
      // سیگنال «آنلاین» مرورگر به‌تنهایی کافی نیست (فقط یعنی رابط شبکه‌ای
      // فعال شد) — باید با یک درخواست واقعی تأیید شود.
      failureCountRef.current = 0;
      recheck();
    }

    window.addEventListener("offline", handleBrowserOffline);
    window.addEventListener("online", handleBrowserOnline);

    // ⚠️ به‌جای یک setInterval ثابت، زمان‌بندی تطبیقی: در حالت سالم هر ۲۰
    // ثانیه؛ وقتی مشکوک یا آفلاین هستیم، خیلی سریع‌تر - تا بازگشت سرور
    // (که ممکن است هیچ رویداد `online` مرورگری تولید نکند) خودکار و
    // بدون نیاز به رفرش دستی تشخیص داده شود.
    let cancelled = false;
    async function tick() {
      if (cancelled || !isMounted.current) return;
      if (navigator.onLine) await recheck();
      if (cancelled || !isMounted.current) return;

      let nextDelay = HEALTH_CHECK_INTERVAL_MS;
      if (!navigator.onLine) nextDelay = OFFLINE_RECHECK_INTERVAL_MS;
      else if (failureCountRef.current > 0) nextDelay = RETRY_INTERVAL_MS;
      timerRef.current = setTimeout(tick, nextDelay);
    }

    tick(); // چک اولیه، همان لحظه بارگذاری

    return () => {
      cancelled = true;
      isMounted.current = false;
      window.removeEventListener("offline", handleBrowserOffline);
      window.removeEventListener("online", handleBrowserOnline);
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [recheck]);

  return { isOnline, isChecking, recheck };
}
