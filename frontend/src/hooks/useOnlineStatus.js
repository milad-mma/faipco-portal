import { useCallback, useEffect, useRef, useState } from "react";

const HEALTH_CHECK_URL = "/api/health";
const HEALTH_CHECK_INTERVAL_MS = 20_000; // هر ۲۰ ثانیه، وقتی مرورگر می‌گوید آنلاین است، یک‌بار واقعی تأیید می‌شود
const HEALTH_CHECK_TIMEOUT_MS = 5_000;

/**
 * فقط `navigator.onLine` به‌تنهایی کافی نیست — این فقط یعنی «یک رابط شبکه
 * فعال است» (مثلاً وای‌فای وصل است)، نه اینکه واقعاً اینترنت/سرور در دسترس
 * است (مثلاً پشت یک Captive Portal، یا خودِ سرور پرتال از کار افتاده). برای
 * همین، علاوه بر رویدادهای فوری مرورگر (`online`/`offline`)، هر ۲۰ ثانیه هم
 * یک درخواست واقعی و سبک به `/api/health` زده می‌شود.
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

  const recheck = useCallback(async () => {
    setIsChecking(true);
    const reallyOnline = await checkRealConnectivity();
    if (isMounted.current) {
      setIsOnline(reallyOnline);
      setIsChecking(false);
    }
    return reallyOnline;
  }, []);

  useEffect(() => {
    isMounted.current = true;

    function handleBrowserOffline() {
      // سیگنال «آفلاین» خودِ مرورگر فوری و قابل‌اعتماد است — نیازی به تأیید
      // با درخواست شبکه نیست (که خودش هم شکست می‌خورد).
      setIsOnline(false);
    }
    function handleBrowserOnline() {
      // سیگنال «آنلاین» مرورگر به‌تنهایی کافی نیست (فقط یعنی رابط شبکه‌ای
      // فعال شد) — باید با یک درخواست واقعی تأیید شود.
      recheck();
    }

    window.addEventListener("offline", handleBrowserOffline);
    window.addEventListener("online", handleBrowserOnline);

    recheck(); // چک اولیه، همان لحظه بارگذاری

    const intervalId = setInterval(() => {
      if (navigator.onLine) recheck();
    }, HEALTH_CHECK_INTERVAL_MS);

    return () => {
      isMounted.current = false;
      window.removeEventListener("offline", handleBrowserOffline);
      window.removeEventListener("online", handleBrowserOnline);
      clearInterval(intervalId);
    };
  }, [recheck]);

  return { isOnline, isChecking, recheck };
}
