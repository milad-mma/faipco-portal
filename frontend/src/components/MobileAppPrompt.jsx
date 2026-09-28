/**
 * یادآور اپ اندروید (در Layout برای پرسنل):
 * - داخل اپ و گوشی هنوز متصل نیست ← دیالوگ «فعال‌سازی اپ» (اتصال با کد یک‌بارمصرف و راهنمای دسترسی‌ها در بخش بومی).
 * - داخل اپ و گوشی متصل ولی دسترسی‌ها کامل نیست ← نوار هشدار با دکمه‌ی «بررسی دسترسی‌ها».
 * - مرورگر گوشی اندروید و اپ لازم است ← نوار «نصب اپ» با لینک دانلود.
 * بعد از برگشت از بخش بومی اپ (رویداد focus/visibility) وضعیت دوباره خوانده می‌شود.
 */
import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from "@mui/material";
import PhoneAndroidOutlinedIcon from "@mui/icons-material/PhoneAndroidOutlined";
import { useNavigate } from "react-router-dom";
import { createPairingCode, fetchMyMobileStatus, APK_DOWNLOAD_PATH } from "../api/mobile";
import { isAndroidApp, isAndroidBrowser, openNativePairing, openNativeSetup } from "../utils/androidApp";

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
  const inApp = isAndroidApp();
  const inAndroidBrowser = isAndroidBrowser();

  const load = useCallback(() => {
    if (!user?.employee_id || (!inApp && !inAndroidBrowser)) return;
    fetchMyMobileStatus()
      .then(setStatus)
      .catch(() => {});
  }, [user?.employee_id, inApp, inAndroidBrowser]);

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

  if (!status || status.exempt) return null;

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

  // داخل اپ، گوشی متصل نیست
  if (inApp && status.devices.length === 0) {
    return (
      <Dialog open={!dismissed} onClose={dismiss} fullWidth maxWidth="xs">
        <DialogTitle>
          <Stack direction="row" spacing={1} alignItems="center">
            <PhoneAndroidOutlinedIcon color="primary" />
            <Typography fontWeight={700}>فعال‌سازی اپ</Typography>
          </Stack>
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ lineHeight: 2 }}>
            برای ثبت خودکار ورود و خروج و دسترسی به همه‌ی بخش‌ها، این گوشی را به حساب خود متصل کنید و دسترسی موقعیت را
            روی «همیشه مجاز» بگذارید. اپ فقط لحظه‌ی ورود و خروج از محدوده‌ی کارخانه را ثبت می‌کند و موقعیت شما را دائم
            دنبال نمی‌کند.
          </Typography>
          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={dismiss}>بعداً</Button>
          <Button variant="contained" onClick={handlePair} disabled={busy}>
            فعال‌سازی
          </Button>
        </DialogActions>
      </Dialog>
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
