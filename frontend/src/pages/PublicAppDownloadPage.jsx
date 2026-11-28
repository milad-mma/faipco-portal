import { useEffect, useState } from "react";
import { Alert, Box, Button, CircularProgress, Stack, Typography } from "@mui/material";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import AuthPageShell from "../components/AuthPageShell";
import { APK_DOWNLOAD_PATH, fetchLatestRelease } from "../api/mobile";

/**
 * صفحه‌ی عمومی دانلود اپ اندروید (مسیر /app، بدون نیاز به ورود) — برای QR کد، پیامک و اطلاعیه.
 * آخرین نسخه را از GET /mobile/app/latest می‌خواند؛ اگر قابلیت اپ خاموش باشد (404) یا نسخه‌ای آپلود نشده باشد،
 * پیام «فعلاً در دسترس نیست» نمایش داده می‌شود.
 */
const INSTALL_STEPS = [
  "فایل دانلودشده را باز کنید.",
  "اگر گوشی اجازهٔ نصب خواست، آن را برای مرورگر یا برنامه‌ای که فایل را با آن باز کرده‌اید فعال کنید.",
  "بعد از نصب، اپلیکیشن فایپکو را باز کنید. اگر صفحهٔ ورود را دیدید، با حساب پرسنلی خود وارد شوید.",
];

const isAndroid = () => /android/i.test(navigator.userAgent || "");
const isIos = () => /iphone|ipad|ipod/i.test(navigator.userAgent || "");

export default function PublicAppDownloadPage() {
  const [release, setRelease] = useState(undefined); // undefined = در حال بارگذاری، null = در دسترس نیست

  useEffect(() => {
    fetchLatestRelease()
      .then((r) => setRelease(r || null))
      .catch(() => setRelease(null));
  }, []);

  const sizeMb = release?.file_size ? (release.file_size / (1024 * 1024)).toLocaleString("fa-IR", { maximumFractionDigits: 1 }) : null;

  return (
    <AuthPageShell title="دانلود اپلیکیشن اندروید فایپکو" subtitle="فایل نصب را دریافت کنید و پس از پایان دانلود، آن را باز کنید.">
      {release === undefined && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress />
        </Box>
      )}
      {release === null && <Alert severity="info">اپ اندروید فعلاً در دسترس نیست.</Alert>}
      {release && (
        <Stack spacing={2}>
          {isIos() && <Alert severity="info">اپ فقط برای گوشی‌های اندروید است. روی آیفون، پرتال را مثل قبل در مرورگر استفاده کنید.</Alert>}
          {!isAndroid() && !isIos() && (
            <Alert severity="info">این صفحه را روی گوشی اندروید باز کنید (مثلاً با اسکن QR کد یا فرستادن همین آدرس به گوشی).</Alert>
          )}
          <Button
            variant="contained"
            size="large"
            startIcon={<FileDownloadOutlinedIcon />}
            href={APK_DOWNLOAD_PATH}
            fullWidth
          >
            دانلود فایل نصب (APK)
          </Button>
          <Typography variant="caption" color="text.secondary" textAlign="center">
            نسخه‌ی {release.version_name}
            {sizeMb ? ` — ${sizeMb} مگابایت` : ""}
          </Typography>
          <Box>
            <Typography fontWeight={800} sx={{ mb: 1 }}>
              مراحل نصب
            </Typography>
            <Stack component="ol" spacing={0.75} sx={{ m: 0, pr: 2.5, pl: 0 }}>
              {INSTALL_STEPS.map((step) => (
                <li key={step}>
                  <Typography variant="body2">{step}</Typography>
                </li>
              ))}
            </Stack>
          </Box>
          {release.notes && (
            <Alert severity="success" icon={false}>
              <Typography variant="body2" sx={{ whiteSpace: "pre-line" }}>
                {release.notes}
              </Typography>
            </Alert>
          )}
        </Stack>
      )}
    </AuthPageShell>
  );
}
