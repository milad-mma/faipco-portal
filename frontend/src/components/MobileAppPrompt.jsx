/** Register the verified native launch with the active personnel session. */
import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Stack } from "@mui/material";
import PhoneAndroidOutlinedIcon from "@mui/icons-material/PhoneAndroidOutlined";
import { useNavigate } from "react-router-dom";
import { fetchMyMobileStatus, linkDevice, APK_DOWNLOAD_PATH } from "../api/mobile";
import { isAndroidApp, isAndroidBrowser, peekDeviceLink, clearDeviceLink } from "../utils/androidApp";

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

export default function MobileAppPrompt({ user }) {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [dismissed, setDismissed] = useState(() => sessionGet(DISMISS_KEY) === "1");
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
    let cancelled = false;
    let running = false;
    let attempts = 0;
    const timers = [];
    async function claim() {
      if (running || cancelled || peekDeviceLink() !== link) return;
      running = true;
      try {
        const { linked } = await linkDevice(link);
        if (cancelled || peekDeviceLink() !== link) return;
        clearDeviceLink();
        if (linked) {
          [3, 15, 45, 90, 180].forEach(sec => timers.push(setTimeout(load, sec * 1000)));
        }
      } catch {
        if (!cancelled) timers.push(setTimeout(claim, Math.min(60000, 2000 * 2 ** Math.min(attempts++, 5))));
      } finally { running = false; }
    }
    const resume = () => { if (document.visibilityState === "visible") claim(); };
    claim();
    window.addEventListener("online", claim);
    document.addEventListener("visibilitychange", resume);
    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
      window.removeEventListener("online", claim);
      document.removeEventListener("visibilitychange", resume);
    };
  }, [featureOn, user?.employee_id, load]);

  useEffect(() => {
    load();
    const onVisible = () => document.visibilityState === "visible" && load();
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [load]);

  if (!featureOn || !status || status.exempt) return null;

  const dismiss = () => {
    sessionSet(DISMISS_KEY, "1");
    setDismissed(true);
  };

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
