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
  IconButton,
  InputAdornment,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import GetAppOutlinedIcon from "@mui/icons-material/GetAppOutlined";
import VpnLockOutlinedIcon from "@mui/icons-material/VpnLockOutlined";
import WifiOffOutlinedIcon from "@mui/icons-material/WifiOffOutlined";
import RefreshOutlinedIcon from "@mui/icons-material/RefreshOutlined";
import PersonOutlineIcon from "@mui/icons-material/PersonOutline";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import VisibilityOffOutlinedIcon from "@mui/icons-material/VisibilityOffOutlined";
import EventNoteOutlinedIcon from "@mui/icons-material/EventNoteOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import { useAuth } from "../context/AuthContext";
import { useOnlineStatus } from "../context/OnlineStatusContext";
import { enablePushNotifications, isPushSupported } from "../utils/push";
import { getIsInstallable, isIos, isRunningStandalone, promptPwaInstall } from "../utils/pwaInstall";
import { fetchAppVersion } from "../api/system";
import faipcoLogo from "../assets/faipco-logo.png";

// ⚠️ سوییچ طراحی جدید صفحه ورود — راه برگشت امن (دقیقاً هم‌الگو با
// NEW_DESIGN_ENABLED در theme.js): اگر true باشد، طرح دوپانلی جدید (بر
// اساس personnel_login__1_.html ارسالی کاربر) نمایش داده می‌شود. اگر
// مشکلی پیش آمد، فقط همین یک مقدار را به false تغییر دهید — بدون هیچ
// تغییر دیگری، طرح قدیمی (تک‌کارت وسط‌چین) که سال‌ها استفاده می‌شد
// برمی‌گردد. کل منطق ورود (handleSubmit، PWA، VPN، آفلاین) بین هر دو طرح
// کاملاً مشترک است — فقط JSX نمایشی فرق دارد.
const NEW_LOGIN_DESIGN_ENABLED = true;

const PROMO_FEATURES = [
  { icon: <EventNoteOutlinedIcon fontSize="small" />, label: "درخواست مرخصی" },
  { icon: <DescriptionOutlinedIcon fontSize="small" />, label: "فیش حقوق و کارکرد" },
  { icon: <CampaignOutlinedIcon fontSize="small" />, label: "اطلاعیه‌ها و ابلاغیه‌های سازمانی" },
];

export default function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const { isOnline, isChecking, recheck } = useOnlineStatus();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [vpnBlockedMessage, setVpnBlockedMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [canInstall, setCanInstall] = useState(getIsInstallable());
  const [appVersion, setAppVersion] = useState("");

  useEffect(() => {
    // اگر کاربر همین الان اینجا (صفحه ورود) نشسته، ولی Session او در پس‌زمینه
    // معتبر تشخیص داده شد (مثلاً بعد از قطعی موقت اینترنت که با توکن قبلی
    // خودکار دوباره تأیید شد — نگاه کنید AuthContext)، نباید مجبور به تایپ
    // دوباره رمز عبور شود؛ همان لحظه به صفحه اصلی هدایت می‌شود.
    if (user) {
      navigate("/", { replace: true });
    }
  }, [user, navigate]);

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

  // ---------------------------------------------------------------------
  // بخش‌های مشترک بین هر دو طرح (قدیمی/جدید) — یک‌بار تعریف، در هردو
  // Layout استفاده می‌شود؛ منطق واقعی (Submit، PWA، خطاها) کاملاً مشترک است.
  // ---------------------------------------------------------------------

  const installPrompt = (
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
    </>
  );

  const offlineState = (
    <Stack spacing={2} alignItems="center" sx={{ textAlign: "center", py: 2 }}>
      <WifiOffOutlinedIcon sx={{ fontSize: 56 }} color="error" />
      <Typography variant="subtitle1" fontWeight={700}>
        اتصال به اینترنت برقرار نیست
      </Typography>
      <Typography variant="body2" color="text.secondary">
        برای ورود به پرتال، ابتدا اتصال اینترنت خود را بررسی کنید — بعد از وصل‌شدن، این صفحه خودکار
        به‌روز می‌شود.
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
  );

  const vpnDialog = (
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
  );

  if (!NEW_LOGIN_DESIGN_ENABLED) {
    // =====================================================================
    // طرح قدیمی — کاملاً دست‌نخورده، فقط برای راه برگشت
    // =====================================================================
    return (
      <Box
        sx={(theme) => ({
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: `linear-gradient(160deg, ${theme.palette.primary.dark} 0%, ${theme.palette.primary.main} 55%, ${theme.palette.primary.light} 100%)`,
          px: 2,
        })}
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
              {installPrompt}
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
            offlineState
          )}
        </Paper>

        {appVersion && (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 2, opacity: 0.6, direction: "ltr" }}>
            {appVersion}
          </Typography>
        )}

        {vpnDialog}
      </Box>
    );
  }

  // =========================================================================
  // طرح جدید — دوپانلی، بر اساس personnel_login__1_.html ارسالی کاربر
  // =========================================================================
  const formFields = (
    <Box component="form" onSubmit={handleSubmit} sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <TextField
        label="کد پرسنلی / نام کاربری"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        required
        autoFocus
        fullWidth
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <PersonOutlineIcon fontSize="small" color="action" />
            </InputAdornment>
          ),
        }}
      />
      <TextField
        label="رمز عبور"
        type={showPassword ? "text" : "password"}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        fullWidth
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <LockOutlinedIcon fontSize="small" color="action" />
            </InputAdornment>
          ),
          endAdornment: (
            <InputAdornment position="end">
              <IconButton
                size="small"
                edge="end"
                onClick={() => setShowPassword((v) => !v)}
                aria-label="نمایش رمز عبور"
                tabIndex={-1}
              >
                {showPassword ? (
                  <VisibilityOffOutlinedIcon fontSize="small" />
                ) : (
                  <VisibilityOutlinedIcon fontSize="small" />
                )}
              </IconButton>
            </InputAdornment>
          ),
        }}
      />
      <Button
        type="submit"
        variant="contained"
        size="large"
        disabled={isSubmitting}
        sx={{ mt: 1, borderRadius: 999, height: 48 }}
      >
        {isSubmitting ? "در حال ورود..." : "ورود به پرتال"}
      </Button>
    </Box>
  );

  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "#F3F7FA",
        display: "flex",
        alignItems: "center",
        // ⚠️ عمداً "center" ساده، نه "flex-end" — چون justify-content با
        // flex-start/flex-end در حالت RTL معنای «شروع/پایان خط» دارد (نه
        // چپ/راست فیزیکی)، و رفتار دقیقش وابسته به جزئیات ظریف Flexbox/RTL
        // است که ریسک اشتباه دوباره (مثل باگ قبلی راست‌چین تاریخ) داشت.
        // نیاز اصلی («فرم سمت راست») از ترتیب DOM (پنل فرم اول) به‌دست
        // می‌آید، نه از این‌جا — همین‌جا فقط کل کارت را وسط صفحه نگه می‌دارد.
        justifyContent: "center",
        p: { xs: 0, md: 6 },
      }}
    >
      <Paper
        elevation={0}
        sx={{
          width: "100%",
          maxWidth: { xs: "100%", md: 780 },
          minHeight: { md: 575 },
          display: "flex",
          flexDirection: { xs: "column", md: "row" },
          borderRadius: { xs: 0, md: 4 },
          boxShadow: { xs: "none", md: "0 24px 55px rgba(33,67,91,.13)" },
          overflow: "hidden",
        }}
      >
        {/* پنل فرم ورود — همیشه اول در DOM، یعنی در دسکتاپ سمت راست (طبق RTL) */}
        <Box
          sx={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            bgcolor: "#fff",
            p: { xs: 0, md: 4.5 },
          }}
        >
          {/* هدر برند — فقط موبایل (در دسکتاپ پنل معرفی کنارش برند را نشان می‌دهد) */}
          <Box
            sx={{
              display: { xs: "flex", md: "none" },
              alignItems: "center",
              gap: 1.5,
              background: "linear-gradient(110deg, #185E95, #2E84AA)",
              color: "#fff",
              px: 2.5,
              py: 2.25,
              mb: 3.5,
            }}
          >
            <Box
              sx={{
                width: 42,
                height: 42,
                borderRadius: "50%",
                bgcolor: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Box component="img" src={faipcoLogo} alt="FAIPCO" sx={{ width: 30, height: 30, objectFit: "contain" }} />
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography fontSize={15} fontWeight={800} noWrap>
                سامانه مدیریت پرسنل فایپکو
              </Typography>
              <Typography fontSize={11} sx={{ opacity: 0.85 }} noWrap>
                شرکت تولیدی صنعتی فواد الیاف
              </Typography>
            </Box>
          </Box>

          <Box sx={{ px: { xs: 2.5, md: 0 }, pb: { xs: 4, md: 0 }, maxWidth: 430, mx: { xs: "auto", md: 0 }, width: "100%" }}>
            <Typography variant="h6" fontWeight={800} sx={{ mb: 1 }}>
              ورود به حساب کاربری
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3, lineHeight: 1.9 }}>
              برای دسترسی به داشبورد، کد پرسنلی و رمز عبور خود را وارد کنید.
            </Typography>

            {isOnline ? (
              <>
                {installPrompt}
                {error && (
                  <Alert severity="error" sx={{ mb: 2 }}>
                    {error}
                  </Alert>
                )}
                {formFields}
              </>
            ) : (
              offlineState
            )}

            {appVersion && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: "block", textAlign: "center", mt: 3, opacity: 0.6, direction: "ltr" }}
              >
                {appVersion}
              </Typography>
            )}
          </Box>
        </Box>

        {/* پنل معرفی — فقط دسکتاپ، در سمت چپ (دومین فرزند، طبق RTL) */}
        <Box
          sx={{
            display: { xs: "none", md: "flex" },
            flex: 1,
            flexDirection: "column",
            justifyContent: "center",
            gap: 3.5,
            color: "#fff",
            p: 4.5,
            background: "linear-gradient(145deg, #185E95 0%, #2E84AA 100%)",
          }}
        >
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Box
              sx={{
                width: 46,
                height: 46,
                borderRadius: "50%",
                bgcolor: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Box component="img" src={faipcoLogo} alt="FAIPCO" sx={{ width: 32, height: 32, objectFit: "contain" }} />
            </Box>
            <Box>
              <Typography fontSize={16} fontWeight={800}>
                سامانه مدیریت پرسنل فایپکو
              </Typography>
              <Typography fontSize={11} sx={{ opacity: 0.85, mt: 0.25 }}>
                شرکت تولیدی صنعتی فواد الیاف
              </Typography>
            </Box>
          </Stack>

          <Box>
            <Typography variant="h5" fontWeight={800} sx={{ mb: 2, lineHeight: 1.8 }}>
              همه خدمات پرسنلی،
              <br />
              در یک نگاه
            </Typography>
            <Typography variant="body2" sx={{ opacity: 0.9, lineHeight: 2.1, mb: 3 }}>
              با وارد شدن به پرتال، تردد، مرخصی، فیش حقوقی و اطلاعیه‌های سازمانی همیشه در دسترس
              شماست.
            </Typography>
            <Stack spacing={1.5}>
              {PROMO_FEATURES.map((f) => (
                <Stack
                  key={f.label}
                  direction="row"
                  spacing={1.5}
                  alignItems="center"
                  sx={{
                    minHeight: 47,
                    px: 2,
                    borderRadius: 999,
                    bgcolor: "rgba(255,255,255,0.09)",
                    border: "1px solid rgba(255,255,255,0.07)",
                  }}
                >
                  {f.icon}
                  <Typography fontSize={13} fontWeight={700}>
                    {f.label}
                  </Typography>
                </Stack>
              ))}
            </Stack>
          </Box>
        </Box>
      </Paper>

      {vpnDialog}
    </Box>
  );
}
