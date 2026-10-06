/**
 * قفل‌های اپ اندروید (در Layout، فقط وقتی قابلیت اپ اندروید روشن است؛ docs/android-app.md):
 *
 * ۱. قفل مرورگر: پرسنل غیرمعاف روی گوشی اندروید (status.required از GET /mobile/me) که پرتال را در مرورگر باز کرده
 *    (نه داخل اپ) ← صفحه‌ی تمام‌صفحه با «باز کردن در اپ» (همین صفحه داخل اپ) و «دانلود اپ». سوپریوزر، معاف‌ها،
 *    آیفون و کامپیوتر قفل نمی‌شوند. صفحه‌ی ورود و صفحه‌ی عمومی دانلود (/app) بیرون از Layout‌اند و باز می‌مانند.
 *
 * ۲. قفل دسترسی‌ها داخل اپ: بخش بومی اپ هنگام ورود دسترسی‌ها را چک می‌کند؛ اگر کاربر وسط کار دسترسی موقعیت/اعلان را
 *    بگیرد یا GPS را خاموش کند، همان لحظه‌ی برگشت به اپ (visibilitychange) این بررسی‌ها انجام می‌شود:
 *    - GPS: (فقط اگر اجازه‌ی موقعیت سایت در Chrome داده شده) موقعیت گرفتن دو بار پشت سر هم «در دسترس نیست» (خطای ۲)
 *      بدهد ← GPS خاموش. روی بعضی گوشی‌ها Chrome برای GPS خاموش خطای دیگری می‌دهد؛ آن وقت گزارش اپ (سرور) قفل می‌کند.
 *    - اعلان: Notification.permission = denied (TWA اجازه‌ی اعلان را از اپ می‌گیرد).
 *    - سرور: permission_issues آخرین گزارش اپ (اپ هر ۱۵ دقیقه و با هر تغییر گزارش می‌دهد) — پشتیبان، چون همه‌ی
 *      گوشی‌ها تغییر دسترسی را همان لحظه به Chrome نمی‌دهند.
 *    دکمه‌ی «تکمیل دسترسی‌ها» صفحه‌ی دسترسی‌های بخش بومی را باز می‌کند (باید با لمس کاربر باشد). تا کامل نشدن، قفل
 *    هر ۱۵ ثانیه و با هر برگشت به اپ دوباره بررسی می‌شود.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Box, Button, CircularProgress, Stack, Typography } from "@mui/material";
import PhoneAndroidOutlinedIcon from "@mui/icons-material/PhoneAndroidOutlined";
import LocationOffOutlinedIcon from "@mui/icons-material/LocationOffOutlined";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import OpenInNewOutlinedIcon from "@mui/icons-material/OpenInNewOutlined";
import { fetchMyMobileStatus, APK_DOWNLOAD_PATH } from "../api/mobile";
import { useAuth } from "../context/AuthContext";
import { isAndroidApp, isAndroidBrowser, openNativeSetup, openPortalInApp } from "../utils/androidApp";

const RECHECK_LOCKED_MS = 15_000;

// یک‌بار موقعیت؛ خروجی: "ok" | "unavailable" (GPS خاموش) | "other" (رد اجازه‌ی سایت، timeout، بدون API)
// سقف ۱۲ ثانیه: timeout خود مرورگر تا جواب پنجره‌ی اجازه شروع نمی‌شود و بدون این سقف بررسی برای همیشه منتظر می‌ماند
function probeLocation() {
  return new Promise((resolve) => {
    if (!("geolocation" in navigator)) return resolve("other");
    const guard = setTimeout(() => resolve("other"), 12_000);
    navigator.geolocation.getCurrentPosition(
      () => {
        clearTimeout(guard);
        resolve("ok");
      },
      (err) => {
        clearTimeout(guard);
        resolve(err?.code === 2 ? "unavailable" : "other");
      },
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 0 },
    );
  });
}

// اجازه‌ی موقعیت سایت در Chrome از قبل داده شده؟ (فقط آن وقت موقعیت گرفته می‌شود تا پنجره‌ی اجازه تکرار نشود)
async function locationPermissionGranted() {
  try {
    const state = await navigator.permissions?.query({ name: "geolocation" });
    return state?.state === "granted";
  } catch {
    return false;
  }
}

// GPS خاموش فقط وقتی دو بار پشت سر هم «در دسترس نیست» باشد (یک خطای گذرا داخل ساختمان قفل نکند)
async function gpsLooksOff() {
  if (!(await locationPermissionGranted())) return false;
  if ((await probeLocation()) !== "unavailable") return false;
  await new Promise((r) => setTimeout(r, 1500));
  return (await probeLocation()) === "unavailable";
}

function notificationsDenied() {
  try {
    return typeof Notification !== "undefined" && Notification.permission === "denied";
  } catch {
    return false;
  }
}

function FullScreen({ children }) {
  return (
    <Box
      role="alertdialog"
      sx={{
        position: "fixed",
        inset: 0,
        zIndex: (t) => t.zIndex.modal + 10,
        bgcolor: "background.default",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        p: 3,
        pt: "calc(24px + env(safe-area-inset-top, 0px))",
        overflowY: "auto",
      }}
    >
      <Stack spacing={2} alignItems="center" sx={{ maxWidth: 420, width: "100%", textAlign: "center" }}>
        {children}
      </Stack>
    </Box>
  );
}

export default function MobileAppGate({ user }) {
  const { logout } = useAuth();
  const featureOn = Boolean(user?.mobile_app_enabled);
  const isEmployee = Boolean(user?.employee_id) && !user?.is_superuser;
  const inApp = isAndroidApp();
  const inAndroidBrowser = isAndroidBrowser();
  const active = featureOn && isEmployee && (inApp || inAndroidBrowser);

  const [status, setStatus] = useState(null);
  const [localIssues, setLocalIssues] = useState([]); // بررسی‌های همین لحظه در خود صفحه (GPS، اعلان)
  const [checking, setChecking] = useState(false);
  const checkingRef = useRef(false);

  const check = useCallback(async () => {
    if (!active || checkingRef.current) return;
    checkingRef.current = true;
    setChecking(true);
    try {
      const statusPromise = fetchMyMobileStatus().catch(() => null);
      const issues = [];
      if (inApp) {
        if (notificationsDenied()) issues.push("اجازه‌ی اعلان به اپ داده نشده است");
        if (await gpsLooksOff()) issues.push("موقعیت‌یاب (GPS) گوشی خاموش است");
      }
      const s = await statusPromise;
      if (s) setStatus(s);
      setLocalIssues(issues);
    } finally {
      checkingRef.current = false;
      setChecking(false);
    }
  }, [active, inApp]);

  useEffect(() => {
    check();
    const onVisible = () => document.visibilityState === "visible" && check();
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [check]);

  const required = Boolean(status?.required) && !status?.exempt;
  const serverIssues = inApp && required ? (status?.permission_issues || []).map((i) => i.label) : [];
  const appIssues = required || !status ? [...new Set([...localIssues, ...serverIssues])] : [];
  // معاف/غیرلازم بودن را فقط سرور می‌داند؛ تا جواب سرور نرسیده، بررسی‌های محلی هم قفل نمی‌کنند
  const appLocked = inApp && Boolean(status) && required && appIssues.length > 0;
  const browserLocked = inAndroidBrowser && required;

  // تا وقتی قفل است، هر چند ثانیه دوباره (کاربر ممکن است بدون ترک صفحه، از نوار اعلان GPS را روشن کند)
  useEffect(() => {
    if (!appLocked) return undefined;
    const timer = setInterval(check, RECHECK_LOCKED_MS);
    return () => clearInterval(timer);
  }, [appLocked, check]);

  if (!active) return null;

  if (browserLocked) {
    return (
      <FullScreen>
        <PhoneAndroidOutlinedIcon color="primary" sx={{ fontSize: 64 }} />
        <Typography variant="h6" fontWeight={800}>
          لطفاً از اپ اندروید FAIPCO استفاده کنید
        </Typography>
        <Typography variant="body2" color="text.secondary">
          روی گوشی اندروید، پرتال فقط داخل اپ FAIPCO باز می‌شود. اگر اپ نصب است «باز کردن در اپ» را بزنید؛ همین صفحه
          داخل اپ باز می‌شود. اگر نصب نیست، اول اپ را دانلود و نصب کنید.
        </Typography>
        <Button fullWidth size="large" variant="contained" startIcon={<OpenInNewOutlinedIcon />} onClick={() => openPortalInApp()}>
          باز کردن در اپ
        </Button>
        <Button fullWidth variant="outlined" startIcon={<FileDownloadOutlinedIcon />} href={APK_DOWNLOAD_PATH}>
          دانلود اپ
        </Button>
        <Stack direction="row" spacing={1}>
          <Button size="small" href="/app">
            راهنمای نصب
          </Button>
          <Button size="small" color="inherit" onClick={logout}>
            خروج از حساب
          </Button>
        </Stack>
      </FullScreen>
    );
  }

  if (appLocked) {
    return (
      <FullScreen>
        <LocationOffOutlinedIcon color="warning" sx={{ fontSize: 64 }} />
        <Typography variant="h6" fontWeight={800}>
          دسترسی‌های اپ کامل نیست
        </Typography>
        <Box component="ul" sx={{ m: 0, pl: 0, listStyle: "none" }}>
          {appIssues.map((issue) => (
            <Typography component="li" key={issue} variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
              • {issue}
            </Typography>
          ))}
        </Box>
        <Typography variant="body2" color="text.secondary">
          برای استفاده از پرتال، دسترسی موقعیت (همیشه مجاز) و اعلان را به اپ بدهید و GPS گوشی را روشن کنید.
        </Typography>
        <Button fullWidth size="large" variant="contained" onClick={openNativeSetup}>
          تکمیل دسترسی‌ها
        </Button>
        <Stack direction="row" spacing={1}>
          <Button size="small" onClick={check} disabled={checking} startIcon={checking ? <CircularProgress size={14} /> : null}>
            بررسی دوباره
          </Button>
          <Button size="small" color="inherit" onClick={logout}>
            خروج از حساب
          </Button>
        </Stack>
      </FullScreen>
    );
  }

  return null;
}
