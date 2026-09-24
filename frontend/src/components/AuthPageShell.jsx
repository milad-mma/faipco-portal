import { Box, Paper, ThemeProvider, Typography } from "@mui/material";
import EventNoteOutlinedIcon from "@mui/icons-material/EventNoteOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import { LOGIN_BACKGROUND_URL } from "../api/system";
import { useBranding } from "../context/BrandingContext";
import BrandLogo, { desktopPanelBackground, surfaceTitleSx } from "./BrandLogo";
import { modernLightTheme } from "../theme";

// آیتم‌های معرفی قابلیت‌ها در پنل گرادیانتی دسکتاپ
const PROMO_FEATURES = [
  { icon: <EventNoteOutlinedIcon fontSize="small" />, label: "درخواست مرخصی" },
  { icon: <DescriptionOutlinedIcon fontSize="small" />, label: "فیش حقوق و کارکرد" },
  { icon: <CampaignOutlinedIcon fontSize="small" />, label: "اطلاعیه‌ها و ابلاغیه‌های سازمانی" },
];

/**
 * قالب مشترک صفحات احراز هویت (فراموشی و بازنشانی رمز عبور) با همان طرح دوپانلی LoginPage.jsx:
 * پس‌زمینه‌ی قابل‌تنظیم از پنل ادمین، کارت با موقعیت مطلق در دسکتاپ، پنل فرم (راست) و
 * پنل معرفی گرادیانتی (چپ، فقط دسکتاپ). در موبایل به‌جای پنل معرفی یک هدر برند بالای فرم نمایش داده می‌شود.
 * ورودی: title و subtitle (عنوان و زیرعنوان فرم) و children (محتوای فرم).
 * خروجی: کل صفحه داخل ThemeProvider با تم روشن ثابت (modernLightTheme).
 */
export default function AuthPageShell({ title, subtitle, children }) {
  const { loginTitle, loginSubtitle, authTitle, authSubtitle, surfaces } = useBranding();
  // تنظیمات ظاهری جای نمایش "auth" (لوگو، پس‌زمینه، نمایش عنوان)؛ عنوان/زیرعنوان خالی = همان متن صفحه‌ی ورود
  const cfg = surfaces.auth;
  const headerTitle = authTitle || loginTitle;
  const headerSubtitle = authSubtitle || loginSubtitle;

  return (
    <ThemeProvider theme={modernLightTheme}>
      {/* پس‌زمینه‌ی تمام‌صفحه با تصویر قابل‌تنظیم ورود */}
      <Box
        sx={{
          minHeight: "100vh",
          bgcolor: "#F3F7FA",
          backgroundImage: `url(${LOGIN_BACKGROUND_URL})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
          backgroundRepeat: "no-repeat",
          fontFamily: "'Vazirmatn', 'Tahoma', sans-serif",
          position: "relative",
          display: "block",
          p: 0,
        }}
      >
        {/* کارت اصلی: در موبایل تمام‌صفحه، در دسکتاپ کارت شناور با موقعیت مطلق */}
        <Paper
          elevation={0}
          sx={{
            width: "100%",
            maxWidth: { xs: "100%", md: 780 },
            minHeight: { xs: "100vh", md: 575 },
            display: "flex",
            flexDirection: { xs: "column", md: "row" },
            borderRadius: { xs: 0, md: 4 },
            position: { md: "absolute" },
            top: { md: "50%" },
            left: { md: "200px" }, // داخل sx است و stylis-plugin-rtl آن را به right تبدیل می‌کند
            transform: { md: "translateY(-50%)" },
            boxShadow: { xs: "none", md: "0 24px 55px rgba(33,67,91,.13)" },
            overflow: "hidden",
          }}
        >
          {/* پنل فرم — همیشه اول در DOM، یعنی در دسکتاپ سمت راست (طبق RTL) */}
          <Box
            sx={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              justifyContent: { xs: "flex-start", md: "center" },
              bgcolor: "#fff",
              p: { xs: 0, md: 4.5 },
            }}
          >
            {/* هدر برند — فقط موبایل */}
            <Box
              sx={{
                display: { xs: "flex", md: "none" },
                alignItems: "center",
                gap: 1.5,
                background: cfg.background || "linear-gradient(110deg, #3476ad, #2b91a5)",
                // فاصله‌ی ناحیه‌ی امن بالای صفحه (ناچ/Dynamic Island با viewport-fit=cover)؛
                // این صفحات خارج از Layout اصلی رندر می‌شوند و باید خودشان این فاصله را اعمال کنند.
                pt: "env(safe-area-inset-top, 0px)",
                color: "#fff",
                px: 2.5,
                py: 2.25,
                mb: 3.5,
              }}
            >
              <BrandLogo surface="auth" alt={headerTitle} />
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

            {/* عنوان، زیرعنوان و محتوای فرم */}
            <Box
              sx={{
                px: { xs: 2.5, md: 0 },
                pb: { xs: 4, md: 0 },
                maxWidth: 430,
                mx: { xs: "auto", md: 0 },
                width: "100%",
              }}
            >
              <Typography variant="h4" fontWeight={800} sx={{ mb: 1 }}>
                {title}
              </Typography>
              {subtitle && (
                <Typography variant="body2" fontWeight={600} color="text.primary" sx={{ mb: 3, lineHeight: 1.9 }}>
                  {subtitle}
                </Typography>
              )}
              {children}
            </Box>
          </Box>

          {/* پنل معرفی — فقط دسکتاپ */}
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
              background:
                "radial-gradient(circle at 18% 15%, rgba(255,255,255,.10) 0 1px, transparent 1.5px), " +
                desktopPanelBackground(cfg.background),
              backgroundSize: "18px 18px, 100% 100%",
            }}
          >
            {/* لوگو و عنوان برند */}
            <Box sx={{ display: "flex", flexDirection: "row", gap: 1.5, alignItems: "center" }}>
              <BrandLogo surface="auth" alt={headerTitle} />
              <Box>
                {cfg.show_title && <Typography sx={surfaceTitleSx(cfg, "title")}>{headerTitle}</Typography>}
              {cfg.show_subtitle && (
                <Typography sx={{ mt: 0.25, ...surfaceTitleSx(cfg, "subtitle") }}>{headerSubtitle}</Typography>
              )}
              </Box>
            </Box>

            {/* متن معرفی و فهرست قابلیت‌ها */}
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
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                {PROMO_FEATURES.map((f) => (
                  <Box
                    key={f.label}
                    sx={{
                      display: "flex",
                      flexDirection: "row",
                      gap: 1.5,
                      alignItems: "center",
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
                  </Box>
                ))}
              </Box>
            </Box>
          </Box>
        </Paper>
      </Box>
    </ThemeProvider>
  );
}
