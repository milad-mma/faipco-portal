import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
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

const PROMO_FEATURES = [
  { icon: <EventNoteOutlinedIcon fontSize="small" />, label: "درخواست مرخصی" },
  { icon: <DescriptionOutlinedIcon fontSize="small" />, label: "فیش حقوق و کارکرد" },
  { icon: <CampaignOutlinedIcon fontSize="small" />, label: "اطلاعیه‌ها و ابلاغیه‌های سازمانی" },
];

const REMEMBERED_USERNAME_KEY = "faipco_remembered_username";

export default function LoginPage() {
  const { login, user } = useAuth();
  const { appLogoSmallUrl, manifestShortName, loginTitle, loginSubtitle } = useBranding();
  const navigate = useNavigate();
  const { isOnline, isChecking, recheck } = useOnlineStatus();

  const [username, setUsername] = useState(() => localStorage.getItem(REMEMBERED_USERNAME_KEY) || "");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  // پیش‌فرض روشن (مثل نمونه HTML)
  const [rememberMe, setRememberMe] = useState(true);
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

  // ⚠️ این طراحی (بر اساس personnel_login__1_.html) عمداً تک‌حالته/فقط
  // روشن است — بدون نسخه تیره طراحی‌شده. اگر رنگ‌ها را از theme.palette
  // بگیریم (مثل text.primary)، در حالت تیره سیستم/برنامه، آن رنگ‌ها به
  // مقادیر روشن Dark Theme تبدیل می‌شدند — روی پس‌زمینه ثابت روشن این
  // صفحه (که Hardcode است، نه از تِم)، متن/بوردر تقریباً نامرئی می‌شد
  // (دقیقاً باگی که گزارش شد). با پیچیدن این طرح در یک ThemeProvider
  // مستقل و همیشه‌روشن (modernLightTheme)، تمام کامپوننت‌های MUI داخلش
  // (TextField، Typography، Button) صرف‌نظر از تنظیم روشن/تیره کاربر،
  // همیشه رنگ‌بندی درست و خوانا می‌گیرند.
  return (
    <ThemeProvider theme={modernLightTheme}>
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "#F3F7FA",
        // عکس پس‌زمینه صفحه ورود — قابل تنظیم از پنل Admin («تنظیمات
        // سامانه»). عمداً مستقیماً همین URL به‌عنوان CSS background-image
        // استفاده می‌شود، نه یک بررسی جداگانه با JS — اگر Admin هنوز
        // عکسی تنظیم نکرده باشد، Backend به این آدرس ۴۰۴ می‌دهد، که
        // مرورگر آن را کاملاً بی‌صدا نادیده می‌گیرد و همان bgcolor ثابت
        // بالا (به‌جای پس‌زمینه) دیده می‌شود — بدون هیچ خطا/چشمک‌زدن.
        backgroundImage: `url(${LOGIN_BACKGROUND_URL})`,
        backgroundSize: "cover",
        backgroundPosition: "center",
        backgroundRepeat: "no-repeat",
        // تأکید صریح روی فونت وزیرمتن — با این‌که از theme.js هم به ارث
        // می‌رسد، این تضمین اضافه (مستقل از هر تغییر احتمالی دیگر در تِم)
        // اطمینان می‌دهد این صفحه همیشه با وزیرمتن نمایش داده شود.
        fontFamily: "'Vazirmatn', 'Tahoma', sans-serif",
        position: "relative",
        // ⚠️ عمداً "block" ساده در موبایل، نه Flex — چیدمان Flex قبلی
        // (alignItems/justifyContent) نظری باید کارت را به بالا می‌چسباند،
        // ولی طبق بازخورد مستقیم هنوز فاصله‌ای بالای صفحه دیده می‌شد. با
        // "block" ساده، کارت (تنها فرزند این Box، بدون position:absolute
        // در موبایل) دقیقاً همان اولین محتوای صفحه است — هیچ منطق
        // تراز/وسط‌چینی نیست که بخواهد اشتباه پیش برود.
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
          // دسکتاپ: کارت با موقعیت مطلق، ۲۰۰px فاصله از سمت راست صفحه، وسط
          // ارتفاع صفحه. ⚠️ عمداً "left" نوشته شده، نه "right" — چون
          // stylis-plugin-rtl مقادیر فیزیکی left/right را خودکار Mirror
          // می‌کند (همان الگویی که برای راست‌چین‌کردن تاریخ اطلاعیه هم استفاده
          // شد) — یعنی این "left: 200px" در خروجی نهایی واقعاً "right: 200px"
          // فیزیکی می‌شود.
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
            // ⚠️ باگ واقعی همین‌جا بود: قبلاً "center" بدون شرط بود — چون
            // این باکس در موبایل کل ارتفاع صفحه (100vh از Paper) را پر
            // می‌کند، محتوا (هدر برند + فرم) عمودی وسط صفحه می‌افتاد، نه
            // بالا. در دسکتاپ که کارت ارتفاع محدود و معقول دارد (نه کل
            // صفحه)، وسط‌چین‌بودن مشکلی ندارد و حتی بهتر است.
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
              background: "linear-gradient(110deg, #3476ad, #2b91a5)",
              color: "#fff",
              px: 2.5,
              py: 2.25,
              mb: 3.5,
            }}
          >
            <Box
              sx={{
                width: 56,
                height: 56,
                borderRadius: "50%",
                bgcolor: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Box
                component="img"
                src={appLogoSmallUrl}
                alt={manifestShortName}
                onError={(e) => {
                  e.currentTarget.onerror = null;
                  e.currentTarget.src = "/faipco-logo.png";
                }}
                sx={{ width: 42, height: 42, objectFit: "contain" }}
              />
            </Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography fontSize={15} fontWeight={800} noWrap>
                {loginTitle}
              </Typography>
              <Typography fontSize={11} sx={{ opacity: 0.85 }} noWrap>
                {loginSubtitle}
              </Typography>
            </Box>
          </Box>

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
            position: "relative",
            overflow: "hidden",
            // دقیقاً همان دو گرادیانت ترکیبی نمونه HTML کاربر: نقطه‌های
            // شعاعی ریز (بافت) روی یک گرادیانت خطی آبی→فیروزه‌ای
            background:
              "radial-gradient(circle at 18% 15%, rgba(255,255,255,.10) 0 1px, transparent 1.5px), " +
              "linear-gradient(145deg,#3476ad 0%,#2b91a5 100%)",
            backgroundSize: "18px 18px, 100% 100%",
          }}
        >
          <Stack direction="row" spacing={1.5} alignItems="center">
            <Box
              sx={{
                width: 64,
                height: 64,
                borderRadius: "50%",
                bgcolor: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Box
                component="img"
                src={appLogoSmallUrl}
                alt={manifestShortName}
                onError={(e) => {
                  e.currentTarget.onerror = null;
                  e.currentTarget.src = "/faipco-logo.png";
                }}
                sx={{ width: 48, height: 48, objectFit: "contain" }}
              />
            </Box>
            <Box>
              <Typography fontSize={16} fontWeight={800}>
                {loginTitle}
              </Typography>
              <Typography fontSize={11} sx={{ opacity: 0.85, mt: 0.25 }}>
                {loginSubtitle}
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
    </ThemeProvider>
  );
}
