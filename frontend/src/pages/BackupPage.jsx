import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  Divider,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import CloudDownloadOutlinedIcon from "@mui/icons-material/CloudDownloadOutlined";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import WarningAmberOutlinedIcon from "@mui/icons-material/WarningAmberOutlined";
import DeleteSweepOutlinedIcon from "@mui/icons-material/DeleteSweepOutlined";
import { downloadBackupArchive, fetchRestoreStatus, restoreBackupArchive } from "../api/backup";
import { bustAppCache } from "../api/system";
import { monoFontSx } from "../theme";

const CONFIRM_PHRASE = "RESTORE";
const POLL_INTERVAL_MS = 3000;
const MAX_POLL_ATTEMPTS = 60; // ۳ ثانیه × ۶۰ = تا ۳ دقیقه صبر می‌کنیم

export default function BackupPage() {
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  const [restoreFile, setRestoreFile] = useState(null);
  const [confirmText, setConfirmText] = useState("");
  const [isRestoring, setIsRestoring] = useState(false);
  const [restoreResult, setRestoreResult] = useState(null); // { success, message } | null
  const [restoreLog, setRestoreLog] = useState(""); // خروجی زنده اسکریپت Restore

  const [isBustingCache, setIsBustingCache] = useState(false);
  const [cacheBustResult, setCacheBustResult] = useState(null); // { success, message } | null

  async function handleDownload() {
    setDownloadError("");
    setIsDownloading(true);
    try {
      const blob = await downloadBackupArchive();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, "");
      a.href = url;
      a.download = `faipco-backup-${stamp}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      setDownloadError(err.response?.data?.detail || "ساخت بکاپ ناموفق بود.");
    } finally {
      setIsDownloading(false);
    }
  }

  async function pollRestoreStatus(attemptsLeft) {
    if (attemptsLeft <= 0) {
      setRestoreResult({
        success: false,
        message: "بعد از ۳ دقیقه هنوز نتیجه مشخص نشد — لطفاً دستی از سرور چک کنید: sudo cat /tmp/faipco-restore.log",
      });
      setIsRestoring(false);
      return;
    }
    try {
      const status = await fetchRestoreStatus();
      setRestoreLog(status.log || "");
      if (status.is_finished) {
        setRestoreResult({ success: true, message: "بازیابی با موفقیت انجام شد." });
        setIsRestoring(false);
        setTimeout(() => window.location.reload(), 2000);
        return;
      }
      if (status.is_failed) {
        setRestoreResult({ success: false, message: "بازیابی ناموفق بود — جزئیات کامل در لاگ زیر است." });
        setIsRestoring(false);
        return;
      }
      // هنوز در حال اجراست — دوباره امتحان کن
      setTimeout(() => pollRestoreStatus(attemptsLeft - 1), POLL_INTERVAL_MS);
    } catch {
      // طبیعی است: دقیقاً همان چند ثانیه‌ای که سرویس Stop/Start می‌شود، این
      // درخواست هم موقتاً جواب نمی‌دهد — فقط دوباره امتحان می‌کنیم، خطا نشان نمی‌دهیم
      setTimeout(() => pollRestoreStatus(attemptsLeft - 1), POLL_INTERVAL_MS);
    }
  }

  async function handleRestore() {
    setRestoreResult(null);
    setRestoreLog("");
    if (!restoreFile) {
      setRestoreResult({ success: false, message: "فایل بکاپ را انتخاب کنید." });
      return;
    }
    if (confirmText !== CONFIRM_PHRASE) {
      setRestoreResult({ success: false, message: `برای تأیید، دقیقاً «${CONFIRM_PHRASE}» را تایپ کنید.` });
      return;
    }
    setIsRestoring(true);
    try {
      await restoreBackupArchive(restoreFile, confirmText);
      // این پاسخ فقط یعنی «بازیابی شروع شد» — چون سرویس باید قبل از تماس با
      // pg_restore کامل متوقف بشه، کار واقعی در پس‌زمینه ادامه داره. از همین
      // لحظه، وضعیت واقعی رو هر چند ثانیه یک‌بار می‌پرسیم و همون‌جا نشون
      // می‌دیم — نه یه شمارش‌معکوس کور.
      pollRestoreStatus(MAX_POLL_ATTEMPTS);
    } catch (err) {
      setRestoreResult({ success: false, message: err.response?.data?.detail || "بازیابی ناموفق بود." });
      setIsRestoring(false);
    }
  }

  async function handleBustCache() {
    setCacheBustResult(null);
    setIsBustingCache(true);
    try {
      const data = await bustAppCache();
      setCacheBustResult({ success: true, message: data.message });
    } catch (err) {
      setCacheBustResult({
        success: false,
        message: err.response?.data?.detail || "پاک‌کردن کش ناموفق بود.",
      });
    } finally {
      setIsBustingCache(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 720, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        پشتیبان‌گیری
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        یک بکاپ کامل (Schema و داده) از کل پرتال بسازید — قابل بازیابی روی همین سرور، از همین صفحه.
      </Typography>

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
        {downloadError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {downloadError}
          </Alert>
        )}
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
          چه چیزی داخل بکاپ است؟
        </Typography>
        <Typography variant="body2" color="text.secondary" component="ul" sx={{ pl: 2.5, m: 0 }}>
          <li>همه پرسنل، سایت‌ها، واحدهای سازمانی، سمت‌ها</li>
          <li>همه اطلاعیه‌ها (متنی، فیش حقوقی، فیش کارکرد) و آمار بازدید آن‌ها</li>
          <li>همه کاربران، نقش‌ها و مجوزهای دسترسی</li>
          <li>تنظیمات Sync هر سایت و تاریخچه Sync</li>
          <li>ساختار کامل دیتابیس (Schema) — نه فقط داده</li>
        </Typography>

        <Divider sx={{ my: 2.5 }} />

        <Button
          variant="contained"
          size="large"
          startIcon={isDownloading ? <CircularProgress size={18} color="inherit" /> : <CloudDownloadOutlinedIcon />}
          onClick={handleDownload}
          disabled={isDownloading}
        >
          {isDownloading ? "در حال آماده‌سازی بکاپ..." : "دانلود بکاپ کامل"}
        </Button>
      </Card>

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3, borderColor: "error.main" }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
          <WarningAmberOutlinedIcon color="error" fontSize="small" />
          <Typography variant="subtitle2" fontWeight={700} color="error.main">
            بازیابی از همین پنل (روی همین سرور)
          </Typography>
        </Stack>

        {restoreResult && (
          <Alert severity={restoreResult.success ? "success" : "error"} sx={{ mb: 2 }}>
            {restoreResult.message}
            {restoreResult.success && " — الان صفحه Refresh می‌شود."}
          </Alert>
        )}

        {isRestoring && !restoreResult && (
          <Alert severity="info" icon={<CircularProgress size={18} />} sx={{ mb: 2 }}>
            در حال بازیابی — این بخش هر چند ثانیه یک‌بار به‌صورت خودکار به‌روزرسانی می‌شود.
          </Alert>
        )}

        {restoreLog && (
          <Box
            sx={{
              mb: 2,
              p: 2,
              borderRadius: 2,
              backgroundColor: "rgba(22, 50, 79, 0.06)",
              ...monoFontSx,
              fontSize: 12,
              direction: "ltr",
              textAlign: "left",
              whiteSpace: "pre-wrap",
              maxHeight: 260,
              overflowY: "auto",
            }}
          >
            {restoreLog}
          </Box>
        )}

        {!restoreResult?.success && (
          <>
            <Alert severity="warning" sx={{ mb: 2 }}>
              این کار همهٔ داده‌های فعلی روی همین سرور (پرسنل، اطلاعیه‌ها، کاربران، سایت‌ها و...)
              را کاملاً پاک و با محتوای فایل بکاپ جایگزین می‌کند. برگشت‌ناپذیر است. سرویس چند
              ثانیه Restart می‌شود، ولی نیازی به ورود دوباره نیست.
            </Alert>

            <Stack spacing={2}>
              <Button
                component="label"
                variant="outlined"
                startIcon={<CloudUploadOutlinedIcon />}
                disabled={isRestoring}
              >
                {restoreFile ? restoreFile.name : "انتخاب فایل بکاپ (zip)"}
                <input
                  type="file"
                  accept=".zip,application/zip"
                  hidden
                  onChange={(e) => setRestoreFile(e.target.files?.[0] || null)}
                />
              </Button>

              <TextField
                label={`برای تأیید، دقیقاً «${CONFIRM_PHRASE}» را تایپ کنید`}
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                disabled={isRestoring}
                sx={{ direction: "ltr" }}
                inputProps={{ style: { textAlign: "center", fontFamily: "monospace", letterSpacing: 2 } }}
              />

              <Box>
                <Button
                  variant="contained"
                  color="error"
                  startIcon={isRestoring ? <CircularProgress size={18} color="inherit" /> : <WarningAmberOutlinedIcon />}
                  onClick={handleRestore}
                  disabled={isRestoring || confirmText !== CONFIRM_PHRASE || !restoreFile}
                >
                  {isRestoring ? "در حال بازیابی..." : "بازیابی و جایگزینی کامل داده"}
                </Button>
              </Box>
            </Stack>
          </>
        )}
      </Card>

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mt: 3 }}>
        <Typography variant="h6" fontWeight={700} sx={{ mb: 0.5 }}>
          نگهداری اپلیکیشن
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          ابزارهای عمومی نگهداری اپ — مستقل از بکاپ/بازیابی.
        </Typography>

        <Divider sx={{ mb: 2 }} />

        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
          پاک‌کردن کش اپلیکیشن برای همه کاربران
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          دفعه بعدی که هر کاربر سایت را باز کند (یا صفحه را Refresh کند)، اپ کاملاً تازه دریافت
          می‌کند — انگار اولین‌بار است. اگه گوشی نصب‌شده‌ای رفتار عجیب دارد (مثلاً آیکون یا صفحه
          قدیمی می‌ماند)، معمولاً همین کافی است. نیازی به هماهنگی خاصی نیست و برای کاربران فعلی
          هیچ داده‌ای پاک نمی‌شود — فقط فایل‌های ذخیره‌شده اپ (نه اطلاعات ورود یا داده‌های سرور).
        </Typography>

        {cacheBustResult && (
          <Alert severity={cacheBustResult.success ? "success" : "error"} sx={{ mb: 2 }}>
            {cacheBustResult.message}
          </Alert>
        )}

        <Button
          variant="outlined"
          startIcon={isBustingCache ? <CircularProgress size={18} /> : <DeleteSweepOutlinedIcon />}
          onClick={handleBustCache}
          disabled={isBustingCache}
        >
          {isBustingCache ? "در حال اعمال..." : "پاک‌کردن کش برای همه کاربران"}
        </Button>
      </Card>
    </Box>
  );
}
