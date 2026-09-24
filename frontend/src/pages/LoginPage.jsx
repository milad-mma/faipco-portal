/**
 * صفحه ورود یکپارچه پرتال (مدیران با نام کاربری/رمز، پرسنل با کد پرسنلی/کد ملی).
 * چیدمان دوپانلی: پنل فرم (در موبایل با هدر برند) و پنل معرفی خدمات (فقط دسکتاپ).
 * شامل «مرا به خاطر بسپار»، پیشنهاد نصب PWA، حالت آفلاین، درخواست مجوز اعلان پس از ورود
 * و دیالوگ مسدودسازی IP/VPN هنگام پاسخ ۴۰۳.
 */
import { useEffect, useState } from "react";
import { useNavigate, Link as RouterLink } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  InputAdornment,
  Link,
  Paper,
  Stack,
  TextField,
  ThemeProvider,
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
import { modernLightTheme } from "../theme";
import { LOGIN_BACKGROUND_URL } from "../api/system";
import { useBranding } from "../context/BrandingContext";
import BrandLogo, { desktopPanelBackground, surfaceTitleSx } from "../components/BrandLogo";

// فهرست خدمات نمایش‌داده‌شده در پنل معرفی دسکتاپ
const PROMO_FEATURES = [
  { icon: <EventNoteOutlinedIcon fontSize="small" />, label: "درخواست مرخصی" },
  { icon: <DescriptionOutlinedIcon fontSize="small" />, label: "فیش حقوق و کارکرد" },
  { icon: <CampaignOutlinedIcon fontSize="small" />, label: "اطلاعیه‌ها و ابلاغیه‌های سازمانی" },
];

const REMEMBERED_USERNAME_KEY = "faipco_remembered_username";  // کلید localStorage برای نام کاربری ذخیره‌شده

// کامپوننت صفحه ورود؛ ورودی ندارد. پس از ورود موفق به صفحه اصلی هدایت می‌کند
export default function LoginPage() {
  const { login, user } = useAuth();
  const { loginTitle, loginSubtitle, surfaces } = useBranding();
  const cfg = surfaces.login;  // تنظیمات برندینگ سطح «login» (پس‌زمینه، نمایش عنوان/زیرعنوان)
  const headerTitle = loginTitle;
  const headerSubtitle = loginSubtitle;
  const navigate = useNavigate();
  const { isOnline, isChecking, recheck } = useOnlineStatus();

  const [username, setUsername] = useState(() => localStorage.getItem(REMEMBERED_USERNAME_KEY) || "");  // مقدار اولیه از نام کاربری ذخیره‌شده
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true); // «مرا به خاطر بسپار»؛ پیش‌فرض روشن
  const [error, setError] = useState("");
  const [vpnBlockedMessage, setVpnBlockedMessage] = useState("");  // متن دیالوگ مسدودسازی IP؛ رشته خالی = دیالوگ بسته
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [canInstall, setCanInstall] = useState(getIsInstallable());  // مرورگر امکان نصب PWA را اعلام کرده است
  const [appVersion, setAppVersion] = useState("");

  useEffect(() => {
    // اگر Session کاربر در پس‌زمینه معتبر تشخیص داده شود (مثلاً بعد از قطعی موقت اینترنت
    // که با توکن موجود خودکار دوباره تأیید می‌شود؛ AuthContext)، بدون نیاز به ورود
    // مجدد همان لحظه به صفحه اصلی هدایت می‌شود.
    if (user) {
      navigate("/", { replace: true });
    }
  }, [user, navigate]);

  useEffect(() => {
    // دریافت شماره نسخه برنامه؛ خطا (مثلاً در دسترس نبودن Backend) بی‌صدا نادیده گرفته
    // می‌شود و فقط شماره نسخه نمایش داده نمی‌شود
    fetchAppVersion()
      .then(setAppVersion)
      .catch(() => {});
  }, []);

  // گوش دادن به رویداد pwa-installable-changed تا دکمه نصب با تغییر امکان نصب به‌روز شود
  useEffect(() => {
    function handleInstallableChange() {
      setCanInstall(getIsInstallable());
    }
    window.addEventListener("pwa-installable-changed", handleInstallableChange);
    return () => window.removeEventListener("pwa-installable-changed", handleInstallableChange);
  }, []);

  const showIosHint = isIos() && !isRunningStandalone();  // راهنمای نصب دستی فقط در iOS و وقتی برنامه نصب‌شده اجرا نمی‌شود

  // پنجره نصب PWA مرورگر را نمایش می‌دهد
  async function handleInstallClick() {
    await promptPwaInstall();
  }

  // ارسال فرم ورود: ورود، ذخیره/حذف نام کاربری طبق «مرا به خاطر بسپار»، درخواست مجوز اعلان
  // و هدایت به صفحه اصلی؛ خطای ۴۰۳ (IP غیرمجاز) در دیالوگ جدا و بقیه خطاها بالای فرم نمایش داده می‌شوند
  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      // فرم ورود یکپارچه است: همین دو فیلد هم برای مدیریت (نام کاربری/رمز عبور)
      // و هم برای پرسنل (کد پرسنلی/کد ملی) کار می‌کند — Backend خودش تشخیص می‌دهد.
      await login(username, password);

      // «مرا به خاطر بسپار» — فقط نام کاربری (هرگز رمز عبور، به دلایل
      // امنیتی) در همین دستگاه ذخیره می‌شود تا دفعه بعد از‌پیش پر شده باشد.
      if (rememberMe) {
        localStorage.setItem(REMEMBERED_USERNAME_KEY, username);
      } else {
        localStorage.removeItem(REMEMBERED_USERNAME_KEY);
      }

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
        setError(err.response?.data?.detail || "ورود با خطا مواجه شد. اطلاعات وارد‌شده را بررسی کنید.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  // ---------------------------------------------------------------------
  // بخش‌های JSX که جداگانه تعریف و در چیدمان اصلی استفاده می‌شوند
  // ---------------------------------------------------------------------

  // دکمه نصب PWA (در صورت امکان) و راهنمای نصب در iOS
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

  // نمایش حالت آفلاین به‌جای فرم، با دکمه بررسی مجدد اتصال
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
        onClick={() => recheck({ force: true })}
        disabled={isChecking}
        sx={{ mt: 1 }}
      >
        {isChecking ? "در حال بررسی..." : "تلاش مجدد"}
      </Button>
    </Stack>
  );

  // دیالوگ مسدودسازی ورود از IP غیرمجاز (مثلاً VPN) با متن تنظیم‌شده در سرور
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

  // =========================================================================
  // فرم ورود: شناسه، رمز عبور (با نمایش/مخفی)، «مرا به خاطر بسپار»، لینک فراموشی رمز
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
        InputLabelProps={{ sx: { color: "text.primary", fontWeight: 600 } }}
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
        InputLabelProps={{ sx: { color: "text.primary", fontWeight: 600 } }}
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
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <FormControlLabel
          control={
            <Checkbox
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              size="small"
            />
          }
          label={<Typography variant="body2">مرا به خاطر بسپار</Typography>}
          sx={{ mr: 0 }}
        />
        <Link component={RouterLink} to="/forgot-password" variant="body2">
          فراموشی رمز عبور
        </Link>
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
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

  // این طرح فقط حالت روشن دارد و پس‌زمینه‌اش ثابت و روشن است؛ برای این‌که رنگ متن/بوردر
  // در حالت تیره کاربر نامرئی نشود، کل صفحه در ThemeProvider همیشه‌روشن (modernLightTheme)
  // پیچیده شده تا کامپوننت‌های MUI داخلش همیشه رنگ‌بندی روشن بگیرند.
  return (
    <ThemeProvider theme={modernLightTheme}>
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "#F3F7FA",
        // عکس پس‌زمینه صفحه ورود (قابل تنظیم در «تنظیمات سامانه» پنل Admin) مستقیماً به‌عنوان
        // CSS background-image؛ اگر عکسی تنظیم نشده باشد Backend پاسخ ۴۰۴ می‌دهد، مرورگر
        // آن را بی‌صدا نادیده می‌گیرد و همان bgcolor بالا دیده می‌شود.
        backgroundImage: `url(${LOGIN_BACKGROUND_URL})`,
        backgroundSize: "cover",
        backgroundPosition: "center",
        backgroundRepeat: "no-repeat",
        // فونت وزیرمتن به‌صورت صریح (مستقل از تنظیمات تم) برای کل صفحه
        fontFamily: "'Vazirmatn', 'Tahoma', sans-serif",
        position: "relative",
        // چیدمان "block" ساده (نه Flex): در موبایل کارت (تنها فرزند، بدون position:absolute)
        // بدون هیچ فاصله‌ای از بالای صفحه شروع می‌شود؛ در دسکتاپ کارت موقعیت مطلق دارد.
        display: "block",
        p: 0,
      }}
    >
      <Paper
        elevation={0}
        sx={{
          width: "100%",
          maxWidth: { xs: "100%", md: 780 },
          minHeight: { xs: "100vh", md: 575 },
          display: "flex",
          flexDirection: { xs: "column", md: "row" },
          borderRadius: { xs: 0, md: 4 },
          // دسکتاپ: کارت با موقعیت مطلق، ۲۰۰px فاصله از سمت راست صفحه و وسط ارتفاع صفحه.
          // "left" نوشته شده چون stylis-plugin-rtl مقادیر left/right را خودکار قرینه می‌کند
          // و "left: 200px" در خروجی نهایی به "right: 200px" تبدیل می‌شود.
          position: { md: "absolute" },
          top: { md: "50%" },
          left: { md: "200px" },
          transform: { md: "translateY(-50%)" },
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
            // موبایل: محتوا (هدر برند + فرم) از بالا شروع می‌شود، چون این باکس کل ارتفاع صفحه
            // (100vh) را پر می‌کند؛ دسکتاپ: کارت ارتفاع محدود دارد و محتوا عمودی وسط‌چین است.
            justifyContent: { xs: "flex-start", md: "center" },
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
              background: cfg.background || "linear-gradient(110deg, #3476ad, #2b91a5)",
              color: "#fff",
              // فاصله ناحیه امن بالا: هدر در موبایل به بالای صفحه چسبیده و با viewport-fit=cover
              // نباید زیر Dynamic Island / ناچ برود (این صفحه خارج از Layout اصلی رندر می‌شود).
              pt: "env(safe-area-inset-top, 0px)",
              px: 2.5,
              py: 2.25,
              mb: 3.5,
            }}
          >
            <BrandLogo surface="login" alt={headerTitle} />
            <Box sx={{ minWidth: 0 }}>
              {cfg.show_title && (
                <Typography noWrap sx={surfaceTitleSx(cfg, "title")}>
                  {headerTitle}
                </Typography>
              )}
              {cfg.show_subtitle && (
                <Typography noWrap sx={surfaceTitleSx(cfg, "subtitle")}>
                  {headerSubtitle}
                </Typography>
              )}
            </Box>
          </Box>

          {/* عنوان، فرم ورود (یا حالت آفلاین) و شماره نسخه */}
          <Box sx={{ px: { xs: 2.5, md: 0 }, pb: { xs: 4, md: 0 }, maxWidth: 430, mx: { xs: "auto", md: 0 }, width: "100%" }}>
            <Typography variant="h4" fontWeight={800} sx={{ mb: 1 }}>
              ورود به حساب کاربری
            </Typography>
            <Typography variant="body2" fontWeight={600} color="text.primary" sx={{ mb: 3, lineHeight: 1.9 }}>
              برای دسترسی به داشبورد، کد پرسنلی و رمز عبور خود را وارد کنید.
            </Typography>

            {isOnline ? (
              <>
                {installPrompt}
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
            position: "relative",
            overflow: "hidden",
            // دو لایه پس‌زمینه: نقطه‌های شعاعی ریز (بافت) روی گرادیانت پنل (طبق تنظیمات برندینگ)
            background:
              "radial-gradient(circle at 18% 15%, rgba(255,255,255,.10) 0 1px, transparent 1.5px), " +
              desktopPanelBackground(cfg.background),
            backgroundSize: "18px 18px, 100% 100%",
          }}
        >
          {/* لوگو و عنوان برند */}
          <Stack direction="row" spacing={1.5} alignItems="center">
            <BrandLogo surface="login" alt={headerTitle} />
            <Box>
              {cfg.show_title && <Typography sx={surfaceTitleSx(cfg, "title")}>{headerTitle}</Typography>}
              {cfg.show_subtitle && (
                <Typography sx={{ mt: 0.25, ...surfaceTitleSx(cfg, "subtitle") }}>{headerSubtitle}</Typography>
              )}
            </Box>
          </Stack>

          {/* متن معرفی و فهرست خدمات */}
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

      {/* دیالوگ مسدودسازی IP */}
      {vpnDialog}
    </Box>
    </ThemeProvider>
  );
}
