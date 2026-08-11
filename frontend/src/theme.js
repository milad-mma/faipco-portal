import { createTheme } from "@mui/material/styles";

/**
 * Design Tokens — FAIPCO Portal
 * ------------------------------------------------------------
 * رنگ‌ها مستقیماً از لوگوی رسمی شرکت استخراج شده‌اند (نه انتخابی جدا):
 * Primary:   #103498  (آبی سلطنتی لوگو — قاب بیضی و خطوط)
 * Primary+:  #536DB5
 * Accent:    #FEE80B  (زرد لوگو — برای اکشن‌ها، برجسته‌سازی، نشان فعال بودن)
 * Surface:   #FFFFFF
 * Background:#F5F7FA
 * Text:      #1A1F29
 * Success:   #2E7D5B
 * Warning:   #C97A2B
 * Error:     #C0392B
 * Border:    #E3E6EB
 * ------------------------------------------------------------
 * Type: Vazirmatn برای متن فارسی (نمایش + بدنه)
 *       "JetBrains Mono" برای اعداد/کدهای پرسنلی در جداول
 */
export const theme = createTheme({
  direction: "rtl",
  palette: {
    mode: "light",
    primary: {
      main: "#103498",
      light: "#536DB5",
      dark: "#0C256D",
      contrastText: "#FFFFFF",
    },
    secondary: {
      main: "#FEE80B",
      light: "#FEF060",
      dark: "#CBBA09",
      contrastText: "#0C256D",
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
  typography: {
    fontFamily: "'Vazirmatn', 'Tahoma', sans-serif",
    h1: { fontWeight: 700 },
    h2: { fontWeight: 700 },
    h3: { fontWeight: 700 },
    h4: { fontWeight: 600 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
    button: { fontWeight: 600, textTransform: "none" },
  },
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

/** کلاس CSS کمکی برای نمایش اعداد/کدها با فونت مونو‌اسپیس (خوانایی بهتر در جداول) */
export const monoFontSx = {
  fontFamily: "'JetBrains Mono', 'Consolas', monospace",
  fontFeatureSettings: '"tnum"',
};
