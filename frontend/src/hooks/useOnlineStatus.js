/**
 * هوک useOnlineStatus: تشخیص وضعیت واقعی اتصال به سرور.
 * علاوه بر رویدادهای online/offline مرورگر، به صورت دوره‌ای با زمان‌بندی تطبیقی /api/health را بررسی می‌کند
 * و فقط پس از چند شکست پشت‌سرهم وضعیت آفلاین اعلام می‌شود.
 */
import { useCallback, useEffect, useRef, useState } from "react";

const HEALTH_CHECK_URL = "/api/health"; // مسیر سبک سلامت سرور برای سنجش اتصال واقعی
const HEALTH_CHECK_INTERVAL_MS = 20_000; // فاصله‌ی بررسی در حالت سالم (وقتی مرورگر آنلاین است)
const HEALTH_CHECK_TIMEOUT_MS = 5_000; // حداکثر زمان انتظار هر درخواست سلامت

// تعداد شکست پشت‌سرهم لازم برای اعلام آفلاین؛ یک شکست تکی (مثلاً هنگام Restart بک‌اند در به‌روزرسانی
// که /api/health چند ثانیه در دسترس نیست) آفلاین حساب نمی‌شود
const FAILURES_BEFORE_OFFLINE = 3;
// فاصله‌ی تلاش مجدد پس از یک شکست (مشکوک به قطعی) تا قطعی واقعی یا بازگشت سرور زودتر دیده شود
const RETRY_INTERVAL_MS = 3_000;
// فاصله‌ی بررسی در حالت آفلاین مرورگر؛ چون رویداد `online` در برخی حالت‌ها (مثل بازگشت سرور بدون
// تغییر رابط شبکه) شلیک نمی‌شود، بررسی دوره‌ای ادامه پیدا می‌کند
const OFFLINE_RECHECK_INTERVAL_MS = 5_000;

/**
 * یک درخواست GET واقعی به /api/health با Timeout می‌زند؛ خروجی: true اگر پاسخ موفق باشد.
 * navigator.onLine فقط فعال بودن رابط شبکه را نشان می‌دهد (نه دسترسی واقعی به سرور، مثلاً پشت Captive Portal).
 * Service Worker مسیرهای /api/ را NetworkOnly می‌کند، پس این پاسخ هرگز از Cache نمی‌آید.
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

/**
 * هوک وضعیت اتصال؛ ورودی ندارد. خروجی: { isOnline, isChecking, recheck }.
 */
export function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [isChecking, setIsChecking] = useState(false);
  const isMounted = useRef(true); // برای جلوگیری از setState پس از unmount
  const failureCountRef = useRef(0); // تعداد شکست‌های پشت‌سرهم بررسی سلامت
  const timerRef = useRef(null); // شناسه‌ی تایمر بررسی بعدی

  /**
   * بررسی واقعی اتصال و به‌روزرسانی وضعیت؛ خروجی: نتیجه‌ی بررسی (boolean).
   * با `force` (دکمه‌ی «تلاش دوباره» کاربر) نتیجه‌ی منفی بلافاصله اعمال می‌شود و منتظر چند شکست نمی‌ماند.
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
      // آفلاین فقط پس از چند شکست پشت‌سرهم یا درخواست صریح کاربر اعلام می‌شود
      // تا یک وقفه‌ی کوتاه (مثل Restart بک‌اند) پیام گمراه‌کننده‌ی قطع اینترنت نشان ندهد
      if (force || failureCountRef.current >= FAILURES_BEFORE_OFFLINE) {
        setIsOnline(false);
      }
    }
    setIsChecking(false);
    return reallyOnline;
  }, []);

  // ثبت listenerهای online/offline مرورگر و شروع حلقه‌ی بررسی دوره‌ای؛ پاک‌سازی هنگام unmount
  useEffect(() => {
    isMounted.current = true;

    function handleBrowserOffline() {
      // سیگنال «آفلاین» مرورگر قابل اعتماد است و بدون تأیید شبکه فوراً اعمال می‌شود
      failureCountRef.current = FAILURES_BEFORE_OFFLINE;
      setIsOnline(false);
    }
    function handleBrowserOnline() {
      // سیگنال «آنلاین» فقط یعنی رابط شبکه فعال شده و با یک درخواست واقعی تأیید می‌شود
      failureCountRef.current = 0;
      recheck();
    }

    window.addEventListener("offline", handleBrowserOffline);
    window.addEventListener("online", handleBrowserOnline);

    // زمان‌بندی تطبیقی با setTimeout زنجیره‌ای: در حالت سالم هر ۲۰ ثانیه، پس از شکست هر ۳ ثانیه
    // و در حالت آفلاین مرورگر هر ۵ ثانیه، تا بازگشت سرور بدون رفرش دستی تشخیص داده شود
    let cancelled = false;
    // یک دور بررسی (فقط وقتی مرورگر آنلاین است) و زمان‌بندی دور بعد بر اساس وضعیت فعلی
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
