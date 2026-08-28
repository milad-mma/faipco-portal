import { createTheme } from "@mui/material/styles";

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

// خروجی نهایی که همه‌جای پروژه import می‌کنند.
export const lightTheme = modernLightTheme;
export const darkTheme = modernDarkTheme;

/** کلاس CSS کمکی برای نمایش اعداد/کدها با فونت مونو‌اسپیس (خوانایی بهتر در جداول) */
export const monoFontSx = {
  fontFamily: "'JetBrains Mono', 'Consolas', monospace",
  fontFeatureSettings: '"tnum"',
};
