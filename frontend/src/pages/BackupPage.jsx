// صفحه‌ی پشتیبان‌گیری و نگهداری پرتال (docs/backup.md):
// دانلود بکاپ کامل (ZIP: دیتابیس + فایل‌های آپلودی؛ با «رمز فایل بکاپ» اگر در تنظیمات تعیین شده)، بازیابی همان ZIP روی همین
// سرور با پیگیری زنده و تنظیم زمان‌بندی/مقصدها/رمز.
import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  Divider,
  LinearProgress,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import CloudDownloadOutlinedIcon from "@mui/icons-material/CloudDownloadOutlined";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import WarningAmberOutlinedIcon from "@mui/icons-material/WarningAmberOutlined";
import { downloadBackupArchive, fetchRestoreStatus, restoreBackupArchive } from "../api/backup";
import { monoFontSx } from "../theme";
import BackupScheduleSettings from "../components/BackupScheduleSettings";
import { useAuth } from "../context/AuthContext";
import { toPersianDigits } from "../utils/searchText";

const CONFIRM_PHRASE = "RESTORE";
const POLL_INTERVAL_MS = 3000;
const MAX_POLL_ATTEMPTS = 600; // بررسی و بازیابی فایل بزرگ چند دقیقه طول می‌کشد

async function blobErrorText(err, fallback) {
  try {
    return JSON.parse(await err.response.data.text()).detail || fallback;
  } catch {
    return err?.response?.data?.detail || fallback;
  }
}

export default function BackupPage() {
  const { user } = useAuth();
  const canBackup = Boolean(user?.can_manage_backup); // system.backup — دانلود، بازیابی و تنظیمات
  const canDownload = canBackup;
  const canRestore = canBackup;
  const canDestinations = canBackup;

  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  const [restoreFile, setRestoreFile] = useState(null);
  const [password, setPassword] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [isRestoring, setIsRestoring] = useState(false);
  const [uploadPct, setUploadPct] = useState(null);
  const [stageMsg, setStageMsg] = useState("");
  const [restoreResult, setRestoreResult] = useState(null);
  const [restoreLog, setRestoreLog] = useState("");
  const [lastRestore, setLastRestore] = useState(null);

  const pollTimer = useRef(null);

  // نتیجه‌ی آخرین بازیابی (بعد از بازیابی، صفحه بازخوانی و گاهی ورود دوباره لازم می‌شود)
  useEffect(() => {
    if (!canRestore) return undefined;
    fetchRestoreStatus()
      .then((s) => {
        if (s.stage?.phase === "failed") setLastRestore({ ok: false, text: `آخرین بازیابی انجام نشد: ${s.stage.message}` });
        else if (s.is_finished) setLastRestore({ ok: true, text: "آخرین بازیابی با موفقیت انجام شد." });
        else if (s.is_failed) setLastRestore({ ok: false, text: "آخرین بازیابی ناموفق بود؛ داده‌ی قبلی سر جایش برگردانده شد." });
      })
      .catch(() => {});
    return () => window.clearTimeout(pollTimer.current);
  }, [canRestore]);

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
      setDownloadError(await blobErrorText(err, "ساخت بکاپ با خطا مواجه شد."));
    } finally {
      setIsDownloading(false);
    }
  }

  function pollRestoreStatus(attemptsLeft) {
    if (attemptsLeft <= 0) {
      setRestoreResult({ success: false, message: "نتیجه‌ی بازیابی مشخص نشد؛ لاگ سرور را بررسی کنید." });
      setIsRestoring(false);
      return;
    }
    const next = () => {
      pollTimer.current = window.setTimeout(() => pollRestoreStatus(attemptsLeft - 1), POLL_INTERVAL_MS);
    };
    fetchRestoreStatus()
      .then((status) => {
        if (status.stage?.phase === "failed") {
          setRestoreResult({ success: false, message: status.stage.message });
          setIsRestoring(false);
          return;
        }
        setStageMsg(status.stage?.message || "");
        setRestoreLog(status.log || "");
        if (status.is_finished) {
          setRestoreResult({
            success: true,
            message: "بازیابی با موفقیت انجام شد. اگر بعد از بازخوانی به صفحه‌ی ورود رفتید، دوباره وارد شوید.",
          });
          setIsRestoring(false);
          setTimeout(() => window.location.reload(), 3000);
          return;
        }
        if (status.is_failed) {
          setRestoreResult({ success: false, message: "بازیابی با خطا مواجه شد — جزئیات در لاگ زیر است." });
          setIsRestoring(false);
          return;
        }
        next();
      })
      .catch(next); // هنگام Stop/Start سرویس پاسخی نمی‌آید؛ دوباره تلاش
  }

  async function handleRestore() {
    setRestoreResult(null);
    setRestoreLog("");
    setStageMsg("");
    setLastRestore(null);
    setIsRestoring(true);
    setUploadPct(0);
    try {
      await restoreBackupArchive(restoreFile, confirmText, password, setUploadPct);
      setUploadPct(null);
      pollRestoreStatus(MAX_POLL_ATTEMPTS);
    } catch (err) {
      setUploadPct(null);
      setRestoreResult({ success: false, message: err.response?.data?.detail || "بازیابی با خطا مواجه شد." });
      setIsRestoring(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 720, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        پشتیبان‌گیری
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        بکاپ کامل پرتال؛ قابل بازیابی از همین صفحه.
      </Typography>

      {lastRestore && (
        <Alert severity={lastRestore.ok ? "success" : "error"} sx={{ mb: 3 }}>{lastRestore.text}</Alert>
      )}

      {canDownload && (
        <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
          <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
            چه چیزی داخل بکاپ است؟
          </Typography>
          <Typography variant="body2" color="text.secondary" component="ul" sx={{ pl: 2.5, m: 0 }}>
            <li>همه پرسنل، سایت‌ها، واحدهای سازمانی، سمت‌ها</li>
            <li>همه اطلاعیه‌ها (متنی، فیش حقوقی، فیش کارکرد) و آمار بازدید آن‌ها</li>
            <li>همه کاربران، نقش‌ها و مجوزهای دسترسی</li>
            <li>تنظیمات و تاریخچه‌ی همگام‌سازی هر سایت</li>
            <li>فایل‌های آپلودی اتوماسیون اداری</li>
            <li>ساختار کامل دیتابیس، نه فقط داده</li>
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            اگر در تنظیمات پایین «رمز فایل بکاپ» تعیین شده باشد، فایل ZIP رمزدار است (با 7-Zip یا WinRAR و همان رمز باز می‌شود).
          </Typography>
          <Divider sx={{ my: 2.5 }} />
          {downloadError && <Alert severity="error" sx={{ mb: 2 }}>{downloadError}</Alert>}
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
      )}

      {canRestore && (
        <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3, borderColor: "error.main" }}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
            <WarningAmberOutlinedIcon color="error" fontSize="small" />
            <Typography variant="subtitle2" fontWeight={700} color="error.main">
              بازیابی از فایل بکاپ
            </Typography>
          </Stack>

          {restoreResult?.success && <Alert severity="success" sx={{ mb: 2 }}>{restoreResult.message}</Alert>}
          {isRestoring && !restoreResult && (
            <Box sx={{ mb: 2 }}>
              <Alert severity="info" icon={<CircularProgress size={18} />}>
                {uploadPct != null && uploadPct < 100
                  ? `در حال ارسال فایل: ${toPersianDigits(uploadPct)}٪`
                  : stageMsg || "در حال بازیابی…"}
              </Alert>
              {uploadPct != null && <LinearProgress variant="determinate" value={uploadPct} sx={{ mt: 1 }} />}
            </Box>
          )}
          {restoreLog && (
            <Box
              sx={{ mb: 2, p: 2, borderRadius: 2, backgroundColor: "rgba(22, 50, 79, 0.06)", ...monoFontSx, fontSize: 12,
                whiteSpace: "pre-wrap", maxHeight: 260, overflowY: "auto" }}
              dir="ltr"
              style={{ direction: "ltr", textAlign: "left" }}
            >
              {restoreLog}
            </Box>
          )}

          {!restoreResult?.success && (
            <>
              <Alert severity="warning" sx={{ mb: 2 }}>
                همه‌ی داده‌ها و فایل‌های آپلودی فعلی با محتوای فایل بکاپ جایگزین می‌شود. اول فایل کامل بررسی می‌شود و اگر سالم
                نباشد هیچ تغییری داده نمی‌شود.
              </Alert>
              <Stack spacing={2}>
                <Button component="label" variant="outlined" startIcon={<CloudUploadOutlinedIcon />} disabled={isRestoring}>
                  {restoreFile ? restoreFile.name : "انتخاب فایل بکاپ (zip)"}
                  <input type="file" accept=".zip,application/zip" hidden onChange={(e) => setRestoreFile(e.target.files?.[0] || null)} />
                </Button>
                <TextField
                  label="رمز فایل بکاپ (اگر فایل رمز دارد)"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isRestoring}
                  autoComplete="new-password"
                />
                <TextField
                  label={`برای تأیید، دقیقاً «${CONFIRM_PHRASE}» را تایپ کنید`}
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  disabled={isRestoring}
                  inputProps={{ dir: "ltr", style: { textAlign: "center", fontFamily: "monospace", letterSpacing: 2 } }}
                />
                <Box>
                  {restoreResult && !restoreResult.success && (
                    <Alert severity="error" sx={{ mb: 2 }}>{restoreResult.message}</Alert>
                  )}
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
      )}

      {canDestinations && (
        <Card variant="outlined" sx={{ p: 3, mt: 3 }}>
          <BackupScheduleSettings />
        </Card>
      )}
    </Box>
  );
}
