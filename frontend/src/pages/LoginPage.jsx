import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Box, Button, Paper, TextField, Typography } from "@mui/material";
import GetAppOutlinedIcon from "@mui/icons-material/GetAppOutlined";
import { useAuth } from "../context/AuthContext";
import { enablePushNotifications, isPushSupported } from "../utils/push";
import { getIsInstallable, isIos, isRunningStandalone, promptPwaInstall } from "../utils/pwaInstall";
import faipcoLogo from "../assets/faipco-logo.png";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [canInstall, setCanInstall] = useState(getIsInstallable());

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
      setError(err.response?.data?.detail || "ورود ناموفق بود. اطلاعات وارد‌شده را بررسی کنید.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
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
            sx={{ width: 88, height: 88, objectFit: "contain", mb: 1.5 }}
          />
          <Typography variant="h6" fontWeight={700}>
            ورود به FAIPCO Portal
          </Typography>
          <Typography variant="body2" color="text.secondary">
            پرتال سازمانی مدیریت پرسنل
          </Typography>
        </Box>

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
      </Paper>
    </Box>
  );
}
