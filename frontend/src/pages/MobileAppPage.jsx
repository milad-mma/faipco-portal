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
  Chip,
  CircularProgress,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import WarningAmberOutlinedIcon from "@mui/icons-material/WarningAmberOutlined";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import { APK_DOWNLOAD_PATH, fetchMyMobileStatus } from "../api/mobile";
import { isAndroidApp, isAndroidBrowser, openNativeSetup } from "../utils/androidApp";
import { startPairing } from "../components/MobileAppPrompt";

const faDateTime = (iso) =>
  iso ? new Date(iso).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "—";

const INSTALL_STEPS = [
  "روی «دانلود اپ» بزنید و فایل را باز کنید.",
  "اگر گوشی اجازه‌ی نصب از منبع ناشناس خواست، برای مرورگر یا مدیر فایل اجازه دهید. این هشدار برای همه‌ی اپ‌هایی است که از فروشگاه نصب نمی‌شوند.",
  "اپ FAIPCO را باز کنید و با همان کد پرسنلی وارد شوید.",
  "دکمه‌ی «فعال‌سازی» را بزنید و مراحل دسترسی را کامل کنید (موقعیت «همیشه مجاز»، اعلان و باتری).",
  "اگر نسخه‌ی قبلی پرتال را روی صفحه‌ی اصلی گوشی نصب کرده‌اید، آن را حذف کنید تا اعلان‌ها دو بار نیایند.",
];

export default function MobileAppPage() {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inApp = isAndroidApp();
  const inAndroidBrowser = isAndroidBrowser();

  const load = () =>
    fetchMyMobileStatus()
      .then(setStatus)
      .catch((err) => setError(err.response?.data?.detail || "دریافت وضعیت ناموفق بود."));

  useEffect(() => {
    load();
    const onVisible = () => document.visibilityState === "visible" && load();
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);

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

  const latest = status?.latest_release;

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        اپ اندروید FAIPCO
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2, lineHeight: 1.9 }}>
        با اپ اندروید، ورود و خروج شما هنگام رسیدن به محدوده‌ی کارخانه و ترک آن خودکار ثبت می‌شود و اعلان‌های پرتال به‌نام اپ
        می‌رسند. اپ موقعیت شما را دائم دنبال نمی‌کند؛ فقط لحظه‌ی ورود و خروج از محدوده بیدار می‌شود و مصرف باتری آن ناچیز است.
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

          {inApp && (
            <Card variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
                وضعیت این اپ
              </Typography>
              {status.devices.length === 0 ? (
                <>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    این گوشی هنوز به حساب شما متصل نشده است.
                  </Typography>
                  <Button variant="contained" onClick={handlePair} disabled={busy}>
                    فعال‌سازی
                  </Button>
                </>
              ) : (
                <Stack spacing={2}>
                  {status.devices.map((d) => (
                    <Box key={d.id}>
                      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                        <Typography variant="body2" fontWeight={600}>
                          {d.model}
                        </Typography>
                        <Chip size="small" color={d.healthy ? "success" : "warning"} label={d.healthy ? "فعال" : "نیاز به بررسی"} />
                      </Stack>
                      <List dense disablePadding>
                        {d.issues.length === 0 && (
                          <ListItem disableGutters>
                            <ListItemIcon sx={{ minWidth: 32 }}>
                              <CheckCircleOutlineIcon color="success" fontSize="small" />
                            </ListItemIcon>
                            <ListItemText primary="همه‌ی دسترسی‌ها درست است." />
                          </ListItem>
                        )}
                        {d.issues.map((i) => (
                          <ListItem key={i.code} disableGutters>
                            <ListItemIcon sx={{ minWidth: 32 }}>
                              {i.blocking ? <ErrorOutlineIcon color="error" fontSize="small" /> : <WarningAmberOutlinedIcon color="warning" fontSize="small" />}
                            </ListItemIcon>
                            <ListItemText primary={i.label} />
                          </ListItem>
                        ))}
                      </List>
                      <Typography variant="caption" color="text.secondary">
                        آخرین گزارش گوشی: {faDateTime(d.status_reported_at)}
                        {d.app_version_name ? ` · نسخه‌ی ${d.app_version_name}` : ""}
                      </Typography>
                    </Box>
                  ))}
                  <Divider />
                  <Stack direction="row" spacing={1}>
                    <Button variant="contained" onClick={openNativeSetup}>
                      بررسی دسترسی‌ها
                    </Button>
                    <Button onClick={handlePair} disabled={busy}>
                      اتصال دوباره
                    </Button>
                  </Stack>
                </Stack>
              )}
            </Card>
          )}

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
