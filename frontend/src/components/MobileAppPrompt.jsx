/**
 * یادآور اپ اندروید (در Layout برای پرسنل):
 * - اتصال خودکار: اگر اپ کد اتصال فرستاده باشد (utils/androidApp)، بلافاصله بعد از ورود به حساب کاربر وصل می‌شود؛
 *   بخش بومی اپ در پس‌زمینه توکن دستگاه را می‌گیرد. کاربر هیچ دکمه‌ای نمی‌زند.
 * - داخل اپ و گوشی هنوز متصل نیست (مثلاً نسخه‌ی قدیمی اپ بدون اتصال خودکار) ← نوار «اتصال گوشی» (اتصال دستی).
 * - داخل اپ و گوشی متصل ولی دسترسی‌ها کامل نیست ← نوار هشدار با دکمه‌ی «بررسی دسترسی‌ها».
 * - مرورگر گوشی اندروید و اپ لازم است ← نوار «نصب اپ» با لینک دانلود.
 * بعد از برگشت از بخش بومی اپ (رویداد focus/visibility) وضعیت دوباره خوانده می‌شود.
 */
import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Stack } from "@mui/material";
import PhoneAndroidOutlinedIcon from "@mui/icons-material/PhoneAndroidOutlined";
import { useNavigate } from "react-router-dom";
import { createPairingCode, fetchMyMobileStatus, linkDevice, APK_DOWNLOAD_PATH } from "../api/mobile";
import { isAndroidApp, isAndroidBrowser, openNativePairing, openNativeSetup, peekDeviceLink, clearDeviceLink } from "../utils/androidApp";

// بعد از اتصال خودکار، بخش بومی اپ چند ثانیه تا یکی دو دقیقه بعد توکن می‌گیرد؛ در این مدت نوار «اتصال» نمایش داده نمی‌شود
const LINK_GRACE_MS = 3 * 60 * 1000;

const DISMISS_KEY = "faipco_mobile_prompt_dismissed"; // فقط برای همین نشست مرورگر

function sessionGet(key) {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function sessionSet(key, value) {
  try {
    sessionStorage.setItem(key, value);
  } catch {
    /* بدون حافظه */
  }
}

// کد اتصال از قبل گرفته می‌شود تا باز کردن بخش بومی مستقیم در همان لمس کاربر انجام شود؛ Chrome باز کردن
// اپ دیگر را بعد از یک درخواست شبکه (بدون لمس کاربر) ممکن است نپذیرد. اعتبار کد ۱۰ دقیقه است.
let prefetched = null; // { code, at }
const PREFETCH_MAX_AGE_MS = 8 * 60 * 1000;

export function prefetchPairingCode() {
  if (prefetched && Date.now() - prefetched.at < PREFETCH_MAX_AGE_MS) return Promise.resolve();
  return createPairingCode()
    .then(({ code }) => {
      prefetched = { code, at: Date.now() };
    })
    .catch(() => {});
}

export async function startPairing() {
  if (prefetched && Date.now() - prefetched.at < PREFETCH_MAX_AGE_MS) {
    const { code } = prefetched;
    prefetched = null; // یک‌بارمصرف
    openNativePairing(code);
    prefetchPairingCode(); // برای تلاش دوباره
    return;
  }
  const { code } = await createPairingCode();
  openNativePairing(code);
}

export default function MobileAppPrompt({ user }) {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [dismissed, setDismissed] = useState(() => sessionGet(DISMISS_KEY) === "1");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [linkedAt, setLinkedAt] = useState(null); // زمان اتصال خودکار در همین نشست
  const inApp = isAndroidApp();
  const inAndroidBrowser = isAndroidBrowser();

  const featureOn = Boolean(user?.mobile_app_enabled);
  const load = useCallback(() => {
    if (!featureOn || !user?.employee_id || (!inApp && !inAndroidBrowser)) return;
    fetchMyMobileStatus()
      .then(setStatus)
      .catch(() => {});
  }, [featureOn, user?.employee_id, inApp, inAndroidBrowser]);

  // اتصال خودکار: کد اپ (اگر باشد) یک‌بار بعد از ورود فرستاده می‌شود؛ سپس وضعیت چند بار دوباره خوانده می‌شود
  useEffect(() => {
    if (!featureOn || !user?.employee_id) return undefined;
    const link = peekDeviceLink();
    if (!link) return undefined;
    const timers = [];
    linkDevice(link)
      .then(({ linked }) => {
        clearDeviceLink(); // خطای شبکه ← کد می‌ماند و با بارگذاری بعدی دوباره فرستاده می‌شود
        if (!linked) return;
        setLinkedAt(Date.now());
        [15, 45, 90, 180].forEach((sec) => timers.push(setTimeout(load, sec * 1000)));
      })
      .catch(() => {});
    return () => timers.forEach(clearTimeout);
  }, [featureOn, user?.employee_id, load]);

  useEffect(() => {
    load();
    const onVisible = () => document.visibilityState === "visible" && load();
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [load]);

  const needsPairing = inApp && status && !status.exempt && status.devices.length === 0;
  useEffect(() => {
    if (needsPairing) prefetchPairingCode();
  }, [needsPairing]);

  if (!featureOn || !status || status.exempt) return null;

  const dismiss = () => {
    sessionSet(DISMISS_KEY, "1");
    setDismissed(true);
  };

  async function handlePair() {
    setBusy(true);
    setError("");
    try {
      await startPairing();
    } catch (err) {
      setError(err.response?.data?.detail || "ساخت کد اتصال ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  // داخل اپ، گوشی متصل نیست: در چند دقیقه‌ی بعد از اتصال خودکار چیزی نشان داده نمی‌شود؛ بعد از آن (یا اپ قدیمی)
  // نوار اتصال دستی
  if (inApp && status.devices.length === 0) {
    if (dismissed || (linkedAt && Date.now() - linkedAt < LINK_GRACE_MS)) return null;
    return (
      <Alert
        severity="info"
        icon={<PhoneAndroidOutlinedIcon />}
        sx={{ borderRadius: 0 }}
        action={
          <Stack direction="row" spacing={0.5}>
            <Button color="inherit" size="small" onClick={handlePair} disabled={busy}>
              اتصال گوشی
            </Button>
            <Button color="inherit" size="small" onClick={dismiss}>
              بستن
            </Button>
          </Stack>
        }
      >
        {error || "این گوشی هنوز به حساب شما متصل نشده است."}
      </Alert>
    );
  }

  // داخل اپ، دسترسی‌ها کامل نیست
  if (inApp && !status.healthy && !dismissed) {
    const firstIssue = status.devices[0]?.issues?.find((i) => i.blocking);
    return (
      <Alert
        severity="warning"
        sx={{ borderRadius: 0 }}
        action={
          <Stack direction="row" spacing={0.5}>
            <Button color="inherit" size="small" onClick={openNativeSetup}>
              بررسی دسترسی‌ها
            </Button>
            <Button color="inherit" size="small" onClick={dismiss}>
              بستن
            </Button>
          </Stack>
        }
      >
        {firstIssue?.label || "تنظیمات اپ کامل نیست."}
      </Alert>
    );
  }

  // مرورگر اندروید: نصب اپ
  if (inAndroidBrowser && status.required && status.latest_release && !dismissed) {
    return (
      <Alert
        severity="info"
        icon={<PhoneAndroidOutlinedIcon />}
        sx={{ borderRadius: 0 }}
        action={
          <Stack direction="row" spacing={0.5}>
            <Button color="inherit" size="small" href={APK_DOWNLOAD_PATH}>
              دانلود اپ
            </Button>
            <Button color="inherit" size="small" onClick={() => navigate("/mobile-app")}>
              راهنما
            </Button>
            <Button color="inherit" size="small" onClick={dismiss}>
              بستن
            </Button>
          </Stack>
        }
      >
        اپ اندروید FAIPCO را نصب کنید.
      </Alert>
    );
  }
  return null;
}
