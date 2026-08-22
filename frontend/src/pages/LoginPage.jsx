import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import GetAppOutlinedIcon from "@mui/icons-material/GetAppOutlined";
import VpnLockOutlinedIcon from "@mui/icons-material/VpnLockOutlined";
import WifiOffOutlinedIcon from "@mui/icons-material/WifiOffOutlined";
import RefreshOutlinedIcon from "@mui/icons-material/RefreshOutlined";
import { useAuth } from "../context/AuthContext";
import { useOnlineStatus } from "../hooks/useOnlineStatus";
import { enablePushNotifications, isPushSupported } from "../utils/push";
import { getIsInstallable, isIos, isRunningStandalone, promptPwaInstall } from "../utils/pwaInstall";
import { fetchAppVersion } from "../api/system";
import faipcoLogo from "../assets/faipco-logo.png";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const { isOnline, isChecking, recheck } = useOnlineStatus();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [vpnBlockedMessage, setVpnBlockedMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [canInstall, setCanInstall] = useState(getIsInstallable());
  const [appVersion, setAppVersion] = useState("");

  useEffect(() => {
    // بی‌صدا — اگه به هر دلیلی این درخواست شکست بخوره (مثلاً بک‌اند هنوز
    // بالا نیومده)، فقط شماره نسخه نشون داده نمی‌شه، صفحه ورود خراب نمی‌شه
    fetchAppVersion()
      .then(setAppVersion)
      .catch(() => {});
  }, []);

  useEffect(() => {
    function handleInstallableChange() {
      setCanInstall(getIsInstallable());
    }
    window.addEventListener("pwa-installable-changed", handleInstallableChange);
    return () => window.removeEventListener("pwa-installable-changed", handleInstallableChange);
  }, []);

  const showIosHint = isIos() && !isRunningStandalone();

  async function handleInstallClick() {
    await promptPwaInstall();
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      // فرم ورود یکپارچه است: همین دو فیلد هم برای مدیریت (نام کاربری/رمز عبور)
      // و هم برای پرسنل (کد پرسنلی/کد ملی) کار می‌کند — Backend خودش تشخیص می‌دهد.
      await login(username, password);

      // چون این یک سیستم اطلاع‌رسانی است، همین لحظه ورود موفق از کاربر
      // اجازه ارسال اعلان می‌خواهیم — رد شدن یا عدم پشتیبانی مرورگر، به
      // روند ورود لطمه‌ای نمی‌زند (کاملاً بی‌صدا نادیده گرفته می‌شود).
      if (isPushSupported()) {
        enablePushNotifications().catch(() => {});
      }

      navigate("/", { replace: true });
    } catch (err) {
      // اگر IP کاربر خارج از رنج‌های مجاز باشد (۴۰۳)، به‌جای هشدار معمولی
      // بالای فرم، یک Dialog جدا و پررنگ نشان می‌دهیم — چون این خطا با بقیه
      // خطاهای ورود (رمز اشتباه و...) فرق دارد و باید واضح‌تر دیده شود.
      if (err.response?.status === 403) {
        setVpnBlockedMessage(
          err.response?.data?.detail ||
            "دسترسی به پرتال فقط از شبکه مجاز امکان‌پذیر است. لطفاً اتصال VPN خود را قطع کنید."
        );
      } else {
        setError(err.response?.data?.detail || "ورود ناموفق بود. اطلاعات وارد‌شده را بررسی کنید.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(160deg, #0E2138 0%, #16324F 55%, #1F4B75 100%)",
        px: 2,
      }}
    >
      <Paper elevation={0} sx={{ width: "100%", maxWidth: 400, p: 4, borderRadius: 3 }}>
        <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", mb: 3 }}>
          <Box
            component="img"
            src={faipcoLogo}
            alt="FAIPCO"
            sx={{ width: 128, height: 128, objectFit: "contain", mb: 1.5 }}
          />
          <Typography variant="h6" fontWeight={700}>
            پرتال سازمانی پرسنل
          </Typography>
          <Typography variant="body2" color="text.secondary">
            شرکت تولیدی صنعتی فوادالیاف
          </Typography>
        </Box>

        {isOnline ? (
          <>
            {canInstall && (
              <Button
                fullWidth
                variant="outlined"
                startIcon={<GetAppOutlinedIcon />}
                onClick={handleInstallClick}
                sx={{ mb: 2 }}
              >
                نصب اپلیکیشن روی این دستگاه
              </Button>
            )}
            {showIosHint && (
              <Alert severity="info" sx={{ mb: 2, fontSize: 13 }}>
                برای نصب روی آیفون: دکمه Share را بزنید و «Add to Home Screen» را انتخاب کنید.
              </Alert>
            )}

            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            <Box component="form" onSubmit={handleSubmit} sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <TextField
                label="نام کاربری"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                fullWidth
              />
              <TextField
                label="رمز عبور"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                fullWidth
              />

              <Button type="submit" variant="contained" size="large" disabled={isSubmitting} sx={{ mt: 1 }}>
                {isSubmitting ? "در حال ورود..." : "ورود"}
              </Button>
            </Box>
          </>
        ) : (
          <Stack spacing={2} alignItems="center" sx={{ textAlign: "center", py: 2 }}>
            <WifiOffOutlinedIcon sx={{ fontSize: 56 }} color="error" />
            <Typography variant="subtitle1" fontWeight={700}>
              اتصال به اینترنت برقرار نیست
            </Typography>
            <Typography variant="body2" color="text.secondary">
              برای ورود به پرتال، ابتدا اتصال اینترنت خود را بررسی کنید — بعد از وصل‌شدن، این صفحه
              خودکار به‌روز می‌شود.
            </Typography>
            <Button
              variant="contained"
              startIcon={<RefreshOutlinedIcon />}
              onClick={recheck}
              disabled={isChecking}
              sx={{ mt: 1 }}
            >
              {isChecking ? "در حال بررسی..." : "تلاش مجدد"}
            </Button>
          </Stack>
        )}
      </Paper>

      {appVersion && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ mt: 2, opacity: 0.6, direction: "ltr" }}
        >
          {appVersion}
        </Typography>
      )}

      <Dialog open={Boolean(vpnBlockedMessage)} onClose={() => setVpnBlockedMessage("")} maxWidth="xs" fullWidth>
        <DialogTitle>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <VpnLockOutlinedIcon color="error" />
            <span>اتصال VPN شناسایی شد</span>
          </Stack>
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2">{vpnBlockedMessage}</Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button variant="contained" onClick={() => setVpnBlockedMessage("")}>
            متوجه شدم
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
