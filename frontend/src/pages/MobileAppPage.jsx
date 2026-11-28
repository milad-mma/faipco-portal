/**
 * صفحه‌ی «اپ اندروید» برای همه‌ی کاربران: وضعیت اپ روی همین دستگاه و راهنمای نصب/فعال‌سازی.
 * - داخل اپ: گوشی‌های متصل با مشکلات، دکمه‌ی فعال‌سازی (اتصال) یا بررسی دسترسی‌ها.
 * - مرورگر اندروید: دانلود APK و مراحل نصب.
 * - آیفون و کامپیوتر: اپ لازم نیست.
 */
import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import { APK_DOWNLOAD_PATH, fetchMyMobileStatus } from "../api/mobile";
import { isAndroidApp, isAndroidBrowser, openPortalInApp, openNativeSetup } from "../utils/androidApp";

const faDateTime = (iso) =>
  iso ? new Date(iso).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "—";

const permissionLabels = {
  notifications: "اعلان‌ها", coarse_location: "موقعیت", fine_location: "موقعیت دقیق",
  battery_unrestricted: "فعالیت بدون محدودیت باتری", keep_permissions: "حفظ مجوزهای برنامه",
};
const INSTALL_STEPS = [
  "روی «دانلود اپ» بزنید و فایل را باز کنید.",
  "اگر گوشی اجازه‌ی نصب از منبع ناشناس خواست، برای مرورگر یا مدیر فایل اجازه دهید. این هشدار برای همه‌ی اپ‌هایی است که از فروشگاه نصب نمی‌شوند.",
  "اپ FAIPCO را باز کنید و دسترسی‌هایی را که می‌خواهد بدهید.",
  "با همان کد پرسنلی و رمز وارد پرتال شوید؛ گوشی خودکار به حساب شما متصل می‌شود.",
];

export default function MobileAppPage() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [showRecovery, setShowRecovery] = useState(false);
  const inApp = isAndroidApp();
  const inAndroidBrowser = isAndroidBrowser();
  // Chrome به اینجا برگشته چون اپ نصب‌شده بخش فعال‌سازی را نداشت (نسخه‌ی قدیمی)
  const appOutdated = new URLSearchParams(window.location.search).get("app_outdated") === "1";

  const load = () =>
    fetchMyMobileStatus()
      .then(setStatus)
      .catch((err) => setError(err.response?.data?.detail || "دریافت وضعیت ناموفق بود."));

  useEffect(() => {
    if (!inApp || !status || status.current_device) return;
    const timer = setTimeout(load, 5000);
    return () => clearTimeout(timer);
  }, [inApp, status]);

  const waiting = inApp && Boolean(status) && !status.current_device;
  useEffect(() => {
    setShowRecovery(false);
    if (!waiting) return;
    const timer = setTimeout(() => setShowRecovery(true), 90000);
    return () => clearTimeout(timer);
  }, [waiting]);

  useEffect(() => {
    load();
    const onVisible = () => document.visibilityState === "visible" && load();
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);

  const latest = status?.latest_release;

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        دسترسی‌های اپلیکیشن
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2, lineHeight: 1.9 }}>
        وضعیت اتصال، مجوزهای همین گوشی و نسخهٔ برنامه را اینجا بررسی کنید.
      </Typography>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {!status ? (
        !error && <CircularProgress />
      ) : (
        <Stack spacing={2}>
          {status.exempt && <Alert severity="info">شما از الزام نصب اپ معاف شده‌اید.</Alert>}

          {appOutdated && (
            <Alert
              severity="warning"
              action={
                latest ? (
                  <Button color="inherit" size="small" href={APK_DOWNLOAD_PATH}>
                    دانلود نسخه‌ی جدید
                  </Button>
                ) : null
              }
            >
              اپ نصب‌شده روی این گوشی بخش فعال‌سازی را ندارد؛ احتمالاً نسخه‌ی قدیمی است. نسخه‌ی جدید را
              نصب کنید.{!latest && " (نسخه‌ی جدید هنوز در پرتال منتشر نشده است.)"}
            </Alert>
          )}

          {inApp && <Card variant="outlined" sx={{ p: 2.5 }}>
            <Stack spacing={1.5}>
              <Typography fontWeight={700}>{status.current_device ? "این گوشی به حساب شما متصل است" : "در انتظار اتصال خودکار این گوشی"}</Typography>
              {showRecovery && waiting && <Button onClick={() => openPortalInApp("/app-permissions")}>تلاش دوباره برای اتصال</Button>}
              {status.current_device && <Typography>آخرین گزارش گوشی: {faDateTime(status.current_device.status_reported_at)}</Typography>}
              {Object.entries(permissionLabels).map(([key, label]) => {
                const grant = status.current_device?.status_reported_at ? status.current_device.grants[key] : null;
                return <Stack direction="row" justifyContent="space-between" key={key}><Typography>{label}</Typography>
                  <Typography>{status.permission_policy?.required[key] ? "الزامی" : "اختیاری"} · {grant == null ? "بررسی در گوشی" : grant ? "تکمیل" : "غیرفعال"}</Typography></Stack>;
              })}
              <Button onClick={openNativeSetup} variant="contained">تنظیم دسترسی‌های همین گوشی</Button>
              {latest && (!status.current_device || status.current_device.app_version_name !== latest.version_name) &&
                <Button href={APK_DOWNLOAD_PATH}>دریافت نسخهٔ {latest.version_name}</Button>}
              {status.devices.filter(d => d.id !== status.current_device?.id).map(d => <Typography variant="body2" key={d.id}>
                {d.model} · آخرین گزارش {faDateTime(d.status_reported_at)}</Typography>)}
            </Stack>
          </Card>}

          {inAndroidBrowser && (
            <Card variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
                نصب اپ
              </Typography>
              {latest ? (
                <>
                  <Button variant="contained" startIcon={<FileDownloadOutlinedIcon />} href={APK_DOWNLOAD_PATH} sx={{ mb: 2 }}>
                    دانلود اپ (نسخه‌ی {latest.version_name}، {(latest.file_size / 1048576).toLocaleString("fa-IR", { maximumFractionDigits: 1 })} مگابایت)
                  </Button>
                  <List dense disablePadding>
                    {INSTALL_STEPS.map((step, i) => (
                      <ListItem key={i} disableGutters alignItems="flex-start">
                        <ListItemIcon sx={{ minWidth: 28, mt: 0.5 }}>
                          <Typography variant="body2" fontWeight={700} color="primary">
                            {(i + 1).toLocaleString("fa-IR")}
                          </Typography>
                        </ListItemIcon>
                        <ListItemText primary={step} />
                      </ListItem>
                    ))}
                  </List>
                </>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  نسخه‌ی اپ هنوز منتشر نشده است.
                </Typography>
              )}
            </Card>
          )}

          {!inApp && !inAndroidBrowser && (
            <Alert severity="info">
              اپ فقط برای گوشی‌های اندروید است. روی آیفون و کامپیوتر پرتال را مثل قبل استفاده کنید؛ نصب اپ لازم نیست.
            </Alert>
          )}
        </Stack>
      )}
    </Box>
  );
}
