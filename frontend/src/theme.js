import { createTheme } from "@mui/material/styles";

/**
 * ⚠️ سوییچ اصلی طراحی جدید — راه برگشت امن
 * ==========================================
 * اگر true باشد، کل پروژه از طراحی جدید (بر اساس نمونه HTML ارسالی کاربر:
 * personnel_portal.html) استفاده می‌کند. اگر مشکلی پیش آمد، فقط همین یک
 * مقدار را به false تغییر دهید — بدون هیچ تغییر دیگری در کل پروژه، دقیقاً
 * همان دو Theme قبلی (کلاسیک/شیشه‌ای) که سال‌ها استفاده می‌شدند برمی‌گردند.
 * تم‌های قدیمی پایین (legacyLightTheme/legacyDarkTheme) کاملاً دست‌نخورده
 * نگه داشته شده‌اند.
 */
export const NEW_DESIGN_ENABLED = true;

const FONT_FAMILY = "'Vazirmatn', 'Tahoma', sans-serif";

const sharedTypography = {
  fontFamily: FONT_FAMILY,
  h1: { fontWeight: 700 },
  h2: { fontWeight: 700 },
  h3: { fontWeight: 700 },
  h4: { fontWeight: 600 },
  h5: { fontWeight: 600 },
  h6: { fontWeight: 600 },
  button: { fontWeight: 600, textTransform: "none" },
};

// ⚠️ فقط برای طراحی جدید (modernLightTheme/modernDarkTheme) — عمداً از
// sharedTypography بالا جداست تا تِم قدیمی (Legacy، برای راه برگشت) دست‌نخورده
// بماند. طبق بازخورد: اندازه فونت همه صفحه‌ها باید با داشبورد شخصی پرسنل
// (PersonalDashboardPage.jsx که از ابتدا با اندازه‌های کوچک‌تر، مثلاً
// fontSize={14}/{12}/{11}/{10}، طراحی شده بود) یکی شود — به‌جای اندازه‌های
// نسبتاً بزرگ‌تر پیش‌فرض MUI (که بقیه صفحات، مثل جداول Admin، هنوز داشتند).
const modernTypography = {
  ...sharedTypography,
  h1: { ...sharedTypography.h1, fontSize: "2.25rem" },
  h2: { ...sharedTypography.h2, fontSize: "1.875rem" },
  h3: { ...sharedTypography.h3, fontSize: "1.5rem" },
  h4: { ...sharedTypography.h4, fontSize: "1.25rem" },
  h5: { ...sharedTypography.h5, fontSize: "1.125rem" },
  h6: { ...sharedTypography.h6, fontSize: "1rem" },
  subtitle1: { fontSize: "0.9375rem" },
  subtitle2: { fontSize: "0.8125rem" },
  body1: { fontSize: "0.875rem" },
  body2: { fontSize: "0.8125rem" },
  caption: { fontSize: "0.6875rem" },
  button: { ...sharedTypography.button, fontSize: "0.8125rem" },
};

// ============================================================
// طراحی جدید — بر اساس personnel_portal.html (نمونه ارسالی کاربر)
// ============================================================
// رنگ‌ها و نسبت‌ها دقیقاً از همان فایل کپی شده‌اند (نه حدسی) — کارت‌های
// خیلی گرد (۲۰px+)، سایه نرم، دکمه/برچسب‌های Pill-شکل، آبی/فیروزه‌ای.
const NEW_LIGHT_BLUE = "#1468A7";
const NEW_LIGHT_TEAL = "#2F9CAC";
const NEW_LIGHT_DANGER = "#E53347";

export const modernLightTheme = createTheme({
  direction: "rtl",
  palette: {
    mode: "light",
    primary: {
      main: NEW_LIGHT_BLUE,
      light: "#2E84AA",
      dark: "#0F5F9B",
      contrastText: "#FFFFFF",
    },
    secondary: {
      main: NEW_LIGHT_TEAL,
      light: "#5DB9C6",
      dark: "#25818F",
      contrastText: "#FFFFFF",
    },
    background: {
      default: "#F3F7FB",
      paper: "#FFFFFF",
    },
    text: {
      primary: "#08172C",
      secondary: "#6F7C8D",
    },
    success: { main: "#2F9CAC" },
    warning: { main: "#C97A2B" },
    error: { main: NEW_LIGHT_DANGER },
    divider: "#DCE5EC",
  },
  typography: modernTypography,
  shape: {
    borderRadius: 6,
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none" },
        outlined: {
          border: "1px solid rgba(196, 208, 219, 0.62)",
          boxShadow: "0 7px 16px rgba(25, 55, 85, 0.10), 0 1px 2px rgba(25, 55, 85, 0.05)",
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: { backgroundColor: "#FFFFFF", backgroundImage: "none", boxShadow: "none" },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: { backgroundColor: "#FFFFFF", backgroundImage: "none" },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 6 },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: { borderRadius: 6 },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: { fontWeight: 700, backgroundColor: "#F3F7FB" },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 700, borderRadius: 999 },
      },
    },
  },
});

// نسخه تیره طراحی جدید — چون نمونه HTML کاربر فقط حالت روشن داشت، این
// نسخه با همان زبان طراحی (کارت‌های گرد، آبی/فیروزه‌ای) برای پس‌زمینه
// تیره طراحی شد — همان تناسب رنگ‌ها، روشن‌تر شده برای کنتراست کافی روی
// زمینه تیره.
export const modernDarkTheme = createTheme({
  direction: "rtl",
  palette: {
    mode: "dark",
    primary: {
      main: "#4FA8DA",
      light: "#7BC1E6",
      dark: "#2E84AA",
      contrastText: "#07141F",
    },
    secondary: {
      main: "#4DBCCB",
      light: "#7DD0DC",
      dark: "#2F9CAC",
      contrastText: "#071A1D",
    },
    background: {
      default: "#0F1824",
      paper: "#182534",
    },
    text: {
      primary: "#EEF4F9",
      secondary: "#90A0B0",
    },
    success: { main: "#4DBCCB" },
    warning: { main: "#FBBF24" },
    error: { main: "#F0798A" },
    divider: "rgba(255, 255, 255, 0.10)",
  },
  typography: modernTypography,
  shape: {
    borderRadius: 6,
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none" },
        outlined: {
          backgroundColor: "#182534",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          boxShadow: "0 7px 16px rgba(0, 0, 0, 0.28)",
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: { backgroundColor: "#182534", backgroundImage: "none", boxShadow: "none" },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: { backgroundColor: "#182534", backgroundImage: "none" },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 6 },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: { borderRadius: 6 },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: { fontWeight: 700, backgroundColor: "rgba(255, 255, 255, 0.04)" },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 700, borderRadius: 999 },
      },
    },
    // ⚠️ این سه مورد (Dialog/Popover/Autocomplete) در نسخه اول طراحی جدید
    // فراموش شده بودند — legacyDarkTheme این‌ها را داشت (پس‌زمینه کدر
    // مشخص، برای خوانایی روی هر محتوایی که زیرش باز می‌شوند)، ولی
    // modernDarkTheme نداشت؛ بدون این override ها، این عناصر روی پس‌زمینه
    // سفارشی تیره این پروژه (#0F1824) از رنگ‌های پیش‌فرض MUI استفاده
    // می‌کردند که می‌توانست کنتراست/خوانایی پایینی داشته باشد.
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundColor: "#1E2D3F",
          backgroundImage: "none",
          border: "1px solid rgba(255, 255, 255, 0.08)",
        },
      },
    },
    MuiPopover: {
      styleOverrides: {
        paper: {
          backgroundColor: "#1E2D3F",
          backgroundImage: "none",
          border: "1px solid rgba(255, 255, 255, 0.08)",
        },
      },
    },
    MuiAutocomplete: {
      styleOverrides: {
        paper: {
          backgroundColor: "#1E2D3F",
          backgroundImage: "none",
          border: "1px solid rgba(255, 255, 255, 0.08)",
        },
      },
    },
  },
});

/**
 * دو زبان طراحی قدیمی — دست‌نخورده، فقط برای راه برگشت (NEW_DESIGN_ENABLED=false):
 *
 * ۱) کلاسیک (Light) — همون ظاهر همیشگی پروژه: کارت‌های تخت با کادر نازک،
 *    گوشه‌های نسبتاً تیز، دکمه‌های مستطیلی ساده، پس‌زمینه یک‌دست.
 *
 * ۲) مدرن شیشه‌ای (Dark/Glass) — یک زبان بصری کاملاً متفاوت:
 *    - پس‌زمینه گرادیانت محو (نه رنگ یک‌دست)
 *    - کارت‌ها «شیشه‌ای» (پس‌زمینه نیمه‌شفاف + Blur + سایه نرم، بدون کادر تیز)
 *    - دکمه‌های اصلی، Pill-شکل با گرادیانت فیروزه‌ای→بنفش
 *    - نوار بالا/کناری هم شیشه‌ای و شناور (Blur)، نه یک‌دست و صاف
 *    - گوشه‌های خیلی گردتر همه‌جا
 *
 * متن‌ها، لوگو، و ساختار صفحات کاملاً دست‌نخورده می‌مونن — این‌ها فقط Theme
 * سطح MUI هستن.
 */

// ============================================================
// ۱) کلاسیک (Light)
// ============================================================
export const legacyLightTheme = createTheme({
  direction: "rtl",
  palette: {
    mode: "light",
    primary: {
      main: "#16324F",
      light: "#1F4B75",
      dark: "#0E2138",
      contrastText: "#FFFFFF",
    },
    secondary: {
      main: "#E0A458",
      light: "#EBBD82",
      dark: "#C68B3F",
      contrastText: "#16324F",
    },
    background: {
      default: "#F5F7FA",
      paper: "#FFFFFF",
    },
    text: {
      primary: "#1A1F29",
      secondary: "#5B6675",
    },
    success: { main: "#2E7D5B" },
    warning: { main: "#C97A2B" },
    error: { main: "#C0392B" },
    divider: "#E3E6EB",
  },
  typography: sharedTypography,
  shape: {
    borderRadius: 10,
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: "#FFFFFF",
          backgroundImage: "none",
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: "#FFFFFF",
          backgroundImage: "none",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 700,
          backgroundColor: "#F5F7FA",
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
        },
      },
    },
  },
});

// ============================================================
// ۲) مدرن شیشه‌ای (Dark/Glass)
// ============================================================
const GLASS_SURFACE = "rgba(42, 53, 82, 0.55)";
const GLASS_SURFACE_STRONG = "rgba(30, 39, 62, 0.7)";
const GLASS_BORDER = "1px solid rgba(255, 255, 255, 0.09)";
const GLASS_BLUR = "blur(20px)";
const GRADIENT_ACCENT = "linear-gradient(135deg, #2DD4BF 0%, #A78BFA 100%)";

export const legacyDarkTheme = createTheme({
  direction: "rtl",
  palette: {
    mode: "dark",
    primary: {
      main: "#2DD4BF",
      light: "#5EEAD4",
      dark: "#14B8A6",
      contrastText: "#07110E",
    },
    secondary: {
      main: "#A78BFA",
      light: "#C4B5FD",
      dark: "#8B5CF6",
      contrastText: "#150F26",
    },
    background: {
      // پیش‌تر تقریباً مشکی (#070B14) بود — طبق بازخورد، الان یک سرمه‌ای
      // متوسط و قابل‌تحمل‌تر است، نه یک Dark Mode افراطی
      default: "#161F33",
      paper: GLASS_SURFACE,
    },
    text: {
      primary: "#EEF2F7",
      secondary: "#A0ABC0",
    },
    success: { main: "#34D399" },
    warning: { main: "#FBBF24" },
    error: { main: "#F87171" },
    divider: "rgba(255, 255, 255, 0.10)",
  },
  typography: sharedTypography,
  shape: {
    // قبلاً ۲۲ بود — خیلی گرد بود. کاهش داده شد.
    borderRadius: 12,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          minHeight: "100vh",
          // پس‌زمینه گرادیانت محو (نه رنگ یک‌دست) — روشن‌تر از نسخه قبلی
          background:
            "radial-gradient(circle at 15% 10%, rgba(45, 212, 191, 0.18), transparent 45%)," +
            "radial-gradient(circle at 85% 0%, rgba(167, 139, 250, 0.20), transparent 48%)," +
            "radial-gradient(circle at 50% 100%, rgba(45, 212, 191, 0.10), transparent 55%)," +
            "#161F33",
          backgroundAttachment: "fixed",
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
        // این دقیقاً همون Style ای است که همه Card های "variant=outlined" این
        // پروژه استفاده می‌کنن — یعنی بدون تغییر یک خط کد در صفحات، همه
        // کارت‌ها خودکار «شیشه‌ای» می‌شن: نیمه‌شفاف + Blur + سایه نرم،
        // بدون کادر تیز مثل حالت کلاسیک
        outlined: {
          backgroundColor: GLASS_SURFACE,
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
          border: GLASS_BORDER,
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.32)",
        },
        elevation1: {
          backgroundColor: GLASS_SURFACE,
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.32)",
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: GLASS_SURFACE_STRONG,
          backgroundImage: "none",
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
          boxShadow: "none",
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: GLASS_SURFACE_STRONG,
          backgroundImage: "none",
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
        },
      },
    },
    // نکته مهم: کارت‌های داخل خودِ صفحه (MuiPaper "outlined"/"elevation1")
    // عمداً شفافیت دارن تا پس‌زمینه گرادیانت از پشتشون کمی دیده بشه — این
    // بخشی از حس «شیشه‌ای» است. ولی Dialog و Menu/Popover روی محتوای دیگه
    // باز می‌شن و باید کاملاً خوانا باشن، نه این‌که پشتشون معلوم باشه؛ پس
    // این دو عمداً تقریباً کدر (Opacity ~0.97) هستن، نه شفاف.
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundColor: "rgba(24, 32, 52, 0.97)",
          backgroundImage: "none",
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
          border: GLASS_BORDER,
          boxShadow: "0 20px 60px rgba(0, 0, 0, 0.5)",
        },
      },
    },
    MuiPopover: {
      styleOverrides: {
        paper: {
          backgroundColor: "rgba(24, 32, 52, 0.97)",
          backgroundImage: "none",
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
          border: GLASS_BORDER,
          boxShadow: "0 12px 40px rgba(0, 0, 0, 0.45)",
        },
      },
    },
    MuiAutocomplete: {
      styleOverrides: {
        paper: {
          backgroundColor: "rgba(24, 32, 52, 0.97)",
          backgroundImage: "none",
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
          border: GLASS_BORDER,
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          // Pill کامل — یکی دیگه از سیگنال‌های واضح تمایز با دکمه‌های
          // نیمه‌گرد استایل کلاسیک
          borderRadius: 999,
          paddingInline: "20px",
        },
        contained: {
          backgroundImage: GRADIENT_ACCENT,
          color: "#07110E",
          boxShadow: "0 6px 20px rgba(45, 212, 191, 0.28)",
          "&:hover": {
            backgroundImage: "linear-gradient(135deg, #5EEAD4 0%, #C4B5FD 100%)",
            boxShadow: "0 8px 26px rgba(45, 212, 191, 0.4)",
          },
        },
        outlined: {
          borderColor: "rgba(255, 255, 255, 0.18)",
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 700,
          backgroundColor: "rgba(255, 255, 255, 0.04)",
          borderBottom: "1px solid rgba(255, 255, 255, 0.09)",
        },
        root: {
          borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
          borderRadius: 999,
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        variant: "filled",
      },
    },
    MuiFilledInput: {
      styleOverrides: {
        root: {
          borderRadius: 14,
          backgroundColor: "rgba(255, 255, 255, 0.05)",
          "&:before, &:after": { display: "none" },
          "&:hover": { backgroundColor: "rgba(255, 255, 255, 0.07)" },
          "&.Mui-focused": { backgroundColor: "rgba(255, 255, 255, 0.08)" },
        },
      },
    },
  },
});

// خروجی نهایی که همه‌جای پروژه import می‌کنند — نقطه واحد سوییچ. هیچ فایل
// دیگری نیازی به تغییر ندارد؛ فقط NEW_DESIGN_ENABLED بالا را عوض کنید.
export const lightTheme = NEW_DESIGN_ENABLED ? modernLightTheme : legacyLightTheme;
export const darkTheme = NEW_DESIGN_ENABLED ? modernDarkTheme : legacyDarkTheme;

/** کلاس CSS کمکی برای نمایش اعداد/کدها با فونت مونو‌اسپیس (خوانایی بهتر در جداول) */
export const monoFontSx = {
  fontFamily: "'JetBrains Mono', 'Consolas', monospace",
  fontFeatureSettings: '"tnum"',
};
