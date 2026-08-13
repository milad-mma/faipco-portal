import { useState } from "react";
import { useNavigate } from "react-router-dom";
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
import { downloadBackupArchive, restoreBackupArchive } from "../api/backup";
import { bustAppCache } from "../api/system";
import { useAuth } from "../context/AuthContext";
import { monoFontSx } from "../theme";

const CONFIRM_PHRASE = "RESTORE";

export default function BackupPage() {
  const navigate = useNavigate();
  const { logout } = useAuth();

  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  const [restoreFile, setRestoreFile] = useState(null);
  const [confirmText, setConfirmText] = useState("");
  const [isRestoring, setIsRestoring] = useState(false);
  const [restoreResult, setRestoreResult] = useState(null); // { success, message } | null

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

  async function handleRestore() {
    setRestoreResult(null);
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
      const data = await restoreBackupArchive(restoreFile, confirmText);
      setRestoreResult({ success: true, message: data.message });
      // چون SECRET_KEY هم از بکاپ جایگزین شد، توکن فعلی دیگر معتبر نیست —
      // بعد از چند ثانیه (تا سرویس Restart را تمام کند) کاربر را به صفحه
      // ورود می‌فرستیم.
      setTimeout(() => {
        logout();
        navigate("/login");
      }, 8000);
    } catch (err) {
      setRestoreResult({ success: false, message: err.response?.data?.detail || "بازیابی ناموفق بود." });
    } finally {
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
        یک بکاپ کامل و قابل‌جابه‌جایی از کل پرتال بسازید — طوری طراحی شده که با بازیابی روی
        یک سرور دیگر، دقیقاً همان اطلاعات بالا بیاید؛ انگار پروژه Clone شده باشد.
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
          <li>
            <strong>کلید رمزنگاری رمز عبور اتصال دیتابیس سایت‌ها</strong> — بدون این کلید، رمزهای
            عبور اتصال روی سرور جدید برای همیشه غیرقابل‌بازیابی می‌شوند
          </li>
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
            {restoreResult.success && " — چند ثانیه دیگر به‌صورت خودکار به صفحه ورود منتقل می‌شوید."}
          </Alert>
        )}

        {!restoreResult?.success && (
          <>
            <Alert severity="warning" sx={{ mb: 2 }}>
              این کار همهٔ داده‌های فعلی روی همین سرور (پرسنل، اطلاعیه‌ها، کاربران، سایت‌ها و...)
              را کاملاً پاک و با محتوای فایل بکاپ جایگزین می‌کند. برگشت‌ناپذیر است. سرویس چند
              ثانیه Restart می‌شود و همه باید دوباره وارد شوند.
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

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
          <WarningAmberOutlinedIcon color="warning" fontSize="small" />
          <Typography variant="subtitle2" fontWeight={700}>
            بازیابی روی سرور دیگر (Clone)
          </Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          برای ساخت یک نسخه کامل از پرتال روی یک سرور جدید، فایل بکاپ را روی یک{" "}
          <strong>نصب کاملاً تازه</strong> (سرور جدید، یا همین سرور با پوشه نصب خالی) از طریق خط‌فرمان
          بازیابی کنید (روی سرور دیگر، پنل وب فعلی هنوز در دسترس نیست):
        </Typography>
        <Box
          sx={{
            p: 2,
            borderRadius: 2,
            backgroundColor: "rgba(22, 50, 79, 0.06)",
            ...monoFontSx,
            fontSize: 13,
            direction: "ltr",
            textAlign: "left",
            overflowX: "auto",
          }}
        >
          sudo bash install.sh --restore-backup /path/to/faipco-backup-....zip
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1.5, display: "block" }}>
          همان گزینه‌های معمول نصب (مثل <code>--domain</code>) را هم می‌توانید کنار همین دستور
          بدهید. اگر روی همان مسیر نصب موجود اجرا کنید (نه یک پوشه/سرور تازه)، برای جلوگیری از
          خطر از‌بین‌رفتن داده زنده، نصب‌کننده با خطا متوقف می‌شود.
        </Typography>
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
