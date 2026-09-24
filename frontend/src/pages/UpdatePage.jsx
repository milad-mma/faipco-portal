// صفحه‌ی بررسی و اعمال آپدیت پرتال.
// نسخه‌ی فعلی را با آخرین نسخه‌ی GitHub مقایسه می‌کند، در صورت وجود آپدیت با تأیید رمز عبور
// آن را اعمال و لاگ نصب را زنده نمایش می‌دهد؛ ویرایشگر اعلان تغییرات و کارت بررسی‌های پروژه هم در همین صفحه است.
import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import SystemUpdateAltOutlinedIcon from "@mui/icons-material/SystemUpdateAltOutlined";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import RefreshOutlinedIcon from "@mui/icons-material/RefreshOutlined";
import { applyUpdate, checkForUpdate, fetchUpdateStatus } from "../api/system";
import { monoFontSx } from "../theme";
import AnnouncementSettings from "../components/AnnouncementSettings";
import ProjectChecksCard from "../components/ProjectChecksCard";

const CONFIRM_PHRASE = "UPDATE";  // عبارتی که کاربر باید برای تأیید آپدیت تایپ کند
const POLL_INTERVAL_MS = 3000;  // فاصله‌ی پرسیدن وضعیت آپدیت از سرور
const MAX_POLL_ATTEMPTS = 120; // حداکثر تعداد پرسش وضعیت (حدود ۶ دقیقه، چون Build فرانت‌اند زمان‌بر است)

// کامپوننت صفحه‌ی آپدیت؛ ورودی ندارد.
// هنگام بارگذاری وجود آپدیت را بررسی می‌کند و فرم اعمال آپدیت را فقط در صورت وجود نسخه‌ی جدید نشان می‌دهد.
export default function UpdatePage() {
  const [checkResult, setCheckResult] = useState(null); // خروجی checkForUpdate | null
  const [isChecking, setIsChecking] = useState(true);

  const [confirmText, setConfirmText] = useState("");
  const [password, setPassword] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateResult, setUpdateResult] = useState(null); // { success, message } | null
  const [updateLog, setUpdateLog] = useState("");  // خروجی زنده‌ی اسکریپت نصب

  // وجود نسخه‌ی جدید را از سرور می‌پرسد؛ در صورت خطا نتیجه را checked=false می‌گذارد
  function runCheck() {
    setIsChecking(true);
    checkForUpdate()
      .then(setCheckResult)
      .catch(() => setCheckResult({ checked: false }))
      .finally(() => setIsChecking(false));
  }

  useEffect(() => {
    // بررسی آپدیت هنگام باز شدن صفحه
    runCheck();
  }, []);

  // وضعیت آپدیت را هر چند ثانیه می‌پرسد و لاگ را نمایش می‌دهد.
  // ورودی: تعداد تلاش‌های باقی‌مانده. با موفقیت صفحه را بازخوانی می‌کند؛ با خطا یا اتمام تلاش‌ها نتیجه را نشان می‌دهد.
  async function pollUpdateStatus(attemptsLeft) {
    if (attemptsLeft <= 0) {
      setUpdateResult({
        success: false,
        message: "بعد از چند دقیقه هنوز نتیجه مشخص نشد — لطفاً دستی از سرور چک کنید: sudo cat /var/log/faipco-install.log",
      });
      setIsUpdating(false);
      return;
    }
    try {
      const status = await fetchUpdateStatus();
      setUpdateLog(status.log || "");
      if (status.is_finished) {
        setUpdateResult({ success: true, message: "آپدیت با موفقیت انجام شد." });
        setIsUpdating(false);
        setTimeout(() => window.location.reload(), 2000);
        return;
      }
      if (status.is_failed) {
        setUpdateResult({ success: false, message: "آپدیت با خطا مواجه شد — جزئیات کامل در لاگ زیر است." });
        setIsUpdating(false);
        return;
      }
      setTimeout(() => pollUpdateStatus(attemptsLeft - 1), POLL_INTERVAL_MS);
    } catch {
      // در زمان Stop/Start سرویس، درخواست موقتاً پاسخ نمی‌گیرد؛ بدون نمایش خطا دوباره تلاش می‌شود
      setTimeout(() => pollUpdateStatus(attemptsLeft - 1), POLL_INTERVAL_MS);
    }
  }

  // عبارت تأیید و رمز عبور را بررسی می‌کند، درخواست آپدیت را می‌فرستد و پیگیری وضعیت را شروع می‌کند؛
  // رمز عبور در هر حالت از فرم پاک می‌شود
  async function handleUpdate() {
    setUpdateResult(null);
    setUpdateLog("");
    if (confirmText !== CONFIRM_PHRASE) {
      setUpdateResult({ success: false, message: `برای تأیید، دقیقاً «${CONFIRM_PHRASE}» را تایپ کنید.` });
      return;
    }
    if (!password) {
      setUpdateResult({ success: false, message: "رمز عبور فعلی خودتان را وارد کنید." });
      return;
    }
    setIsUpdating(true);
    try {
      await applyUpdate(confirmText, password);
      pollUpdateStatus(MAX_POLL_ATTEMPTS);
    } catch (err) {
      setUpdateResult({ success: false, message: err.response?.data?.detail || "آپدیت با خطا مواجه شد." });
      setIsUpdating(false);
    } finally {
      setPassword("");
    }
  }

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        بررسی و اعمال آپدیت
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        نسخه فعلی را با آخرین نسخه منتشرشده در GitHub مقایسه می‌کند و در صورت وجود آپدیت، امکان
        نصب آن را مستقیم از همین‌جا می‌دهد.
      </Typography>
      {/* کانال آپدیت فعال سرور (تگ یا شاخه) */}
      {checkResult?.update_channel && (
        <Alert severity={checkResult.update_channel === "tag" ? "info" : "warning"} sx={{ mb: 3 }}>
          {checkResult.update_channel === "tag" ? (
            <>
              کانال آپدیت: <strong>ریلیز (تگ)</strong> — فقط آخرین تگ منتشرشده نصب می‌شود؛ commitهای بعد از تگ تا
              انتشار تگ بعدی نصب نمی‌شوند.
            </>
          ) : (
            <>
              کانال آپدیت: <strong>شاخه (هر push)</strong> — آخرین commit شاخه نصب می‌شود، حتی اگر هنوز تگ/ریلیز
              نشده باشد. مناسب سرور تست؛ برای سرور اصلی در <code>backend/.env</code> مقدار{" "}
              <code>UPDATE_CHANNEL=tag</code> بگذارید.
            </>
          )}
        </Alert>
      )}

      {/* کارت نتیجه‌ی بررسی: در حال بررسی / خطای اتصال / نسخه‌ی جدید / به‌روز بودن */}
      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
        {isChecking ? (
          <Stack direction="row" spacing={1.5} alignItems="center">
            <CircularProgress size={20} />
            <Typography variant="body2" color="text.secondary">
              در حال بررسی...
            </Typography>
          </Stack>
        ) : !checkResult?.checked ? (
          <Stack spacing={1.5}>
            <Alert severity="warning">
              امکان بررسی آپدیت نبود — اتصال اینترنت یا GitHub در دسترس نیست. نسخه فعلی:{" "}
              <span style={monoFontSx}>{checkResult?.current_version}</span>
            </Alert>
            <Box>
              <Button size="small" startIcon={<RefreshOutlinedIcon />} onClick={runCheck}>
                دوباره امتحان کن
              </Button>
            </Box>
          </Stack>
        ) : checkResult.has_update ? (
          <Stack spacing={1.5}>
            <Alert severity="info" icon={<SystemUpdateAltOutlinedIcon />}>
              نسخه جدید <strong style={monoFontSx}>{checkResult.latest_version}</strong> در دسترس است — نسخه فعلی
              شما: <span style={monoFontSx}>{checkResult.current_version}</span>
            </Alert>
            {checkResult.release_url && (
              <Typography variant="caption">
                <a href={checkResult.release_url} target="_blank" rel="noopener noreferrer">
                  مشاهده جزئیات این نسخه در GitHub
                </a>
              </Typography>
            )}
          </Stack>
        ) : (
          <Stack direction="row" spacing={1.5} alignItems="center">
            <CheckCircleOutlineIcon color="success" />
            <Typography variant="body2">
              شما آخرین نسخه را دارید (<span style={monoFontSx}>{checkResult.current_version}</span>)
            </Typography>
          </Stack>
        )}
      </Card>

      {/* کارت اعمال آپدیت؛ فقط وقتی نسخه‌ی جدید وجود دارد */}
      {checkResult?.has_update && (
        <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
          {updateResult?.success && (
            <Alert severity="success" sx={{ mb: 2 }}>
              {updateResult.message} — اکنون صفحه به‌طور خودکار بازخوانی می‌شود.
            </Alert>
          )}

          {isUpdating && !updateResult && (
            <Alert severity="info" icon={<CircularProgress size={18} />} sx={{ mb: 2 }}>
              در حال آپدیت — این بخش هر چند ثانیه یک‌بار به‌صورت خودکار به‌روزرسانی می‌شود. سرویس چند
              لحظه در دسترس نخواهد بود.
            </Alert>
          )}

          {/* لاگ زنده‌ی نصب (چپ‌چین) */}
          {updateLog && (
            <Box
              sx={{
                mb: 2,
                p: 2,
                borderRadius: 2,
                backgroundColor: "rgba(22, 50, 79, 0.06)",
                ...monoFontSx,
                fontSize: 12,
                whiteSpace: "pre-wrap",
                maxHeight: 260,
                overflowY: "auto",
              }}
              // direction/textAlign در style خطی تعریف می‌شوند چون stylis-plugin-rtl مقادیر sx را قرینه می‌کند
              dir="ltr"
              style={{ direction: "ltr", textAlign: "left" }}
            >
              {updateLog}
            </Box>
          )}

          {/* فرم تأیید آپدیت؛ پس از آپدیت موفق پنهان می‌شود */}
          {!updateResult?.success && (
            <>
              <Alert severity="warning" sx={{ mb: 2 }}>
                این کار معادل اجرای <code>sudo bash install.sh</code> روی سرور است — کد جدید را
                می‌گیرد، فرانت‌اند را از نو Build می‌کند، Migration های دیتابیس را اجرا می‌کند، و
                سرویس را Restart می‌کند. برگشت‌ناپذیر نیست (کد قبلی جایگزین می‌شود، نه پاک)، ولی
                سرویس چند لحظه در دسترس نخواهد بود.
              </Alert>

              <Stack spacing={2}>
                <TextField
                  label="رمز عبور فعلی شما"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  fullWidth
                  disabled={isUpdating}
                  helperText="برای تأیید اضافی — مستقل از ورود فعلی‌تان"
                />
                <TextField
                  label={`برای تأیید، «${CONFIRM_PHRASE}» را تایپ کنید`}
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  fullWidth
                  disabled={isUpdating}
                />
                <Box>
                  {updateResult && !updateResult.success && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                      {updateResult.message}
                    </Alert>
                  )}
                  <Button
                    variant="contained"
                    color="warning"
                    startIcon={isUpdating ? <CircularProgress size={18} color="inherit" /> : <SystemUpdateAltOutlinedIcon />}
                    onClick={handleUpdate}
                    disabled={isUpdating || confirmText !== CONFIRM_PHRASE || !password}
                  >
                    {isUpdating ? "در حال آپدیت..." : "تأیید و آپدیت"}
                  </Button>
                </Box>
              </Stack>
            </>
          )}
        </Card>
      )}

      {/* ویرایشگر اعلان تغییرات برای اطلاع‌رسانی تغییرات نسخه به کاربران پس از آپدیت */}
      <Card variant="outlined" sx={{ borderRadius: 2, p: 3, mt: 3 }}>
        <AnnouncementSettings />
      </Card>

      {/* کارت بررسی‌های وضعیت پروژه */}
      <ProjectChecksCard />
    </Box>
  );
}
