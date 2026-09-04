import { Box, Paper, ThemeProvider, Typography } from "@mui/material";
import EventNoteOutlinedIcon from "@mui/icons-material/EventNoteOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import { LOGIN_BACKGROUND_URL } from "../api/system";
import { useBranding } from "../context/BrandingContext";
import { modernLightTheme } from "../theme";

const PROMO_FEATURES = [
  { icon: <EventNoteOutlinedIcon fontSize="small" />, label: "درخواست مرخصی" },
  { icon: <DescriptionOutlinedIcon fontSize="small" />, label: "فیش حقوق و کارکرد" },
  { icon: <CampaignOutlinedIcon fontSize="small" />, label: "اطلاعیه‌ها و ابلاغیه‌های سازمانی" },
];

/**
 * قالب مشترک صفحات احراز هویت (ورود، فراموشی رمز عبور، بازنشانی رمز
 * عبور) - عیناً همان طرح دوپانلی LoginPage.jsx: پس‌زمینه قابل‌تنظیم از
 * پنل ادمین، کارت با موقعیت مطلق در دسکتاپ، پنل فرم (راست) + پنل معرفی
 * با گرادیانت (چپ، فقط دسکتاپ).
 *
 * title/subtitle/children فقط محتوای داخل پنل فرم را مشخص می‌کنند - همه
 * صفحاتی که از این قالب استفاده می‌کنند، از نظر ظاهری کاملاً یکسان به
 * نظر می‌رسند، دقیقاً مثل صفحه ورود.
 */
export default function AuthPageShell({ title, subtitle, children }) {
  const { appLogoSmallUrl, manifestShortName, loginTitle, loginSubtitle } = useBranding();

  return (
    <ThemeProvider theme={modernLightTheme}>
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
            left: { md: "200px" },
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
                "linear-gradient(145deg,#3476ad 0%,#2b91a5 100%)",
              backgroundSize: "18px 18px, 100% 100%",
            }}
          >
            <Box sx={{ display: "flex", flexDirection: "row", gap: 1.5, alignItems: "center" }}>
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
            </Box>

            <Box>
              <Typography variant="h5" fontWeight={800} sx={{ mb: 2, lineHeight: 1.8 }}>
                همه خدمات پرسنلی،
                <br />
                در یک نگاه
              </Typography>
              <Typography variant="body2" sx={{ opacity: 0.9, lineHeight: 2.1, mb: 3 }}>
                با ورود به پرتال، تردد، مرخصی، فیش حقوقی و اطلاعیه‌های سازمانی همواره در دسترس شما
                خواهد بود.
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
