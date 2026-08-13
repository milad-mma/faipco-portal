import { createTheme } from "@mui/material/styles";

/**
 * دو زبان طراحی کاملاً متفاوت — نه فقط دو پالت رنگ:
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

// ============================================================
// ۱) کلاسیک (Light)
// ============================================================
export const lightTheme = createTheme({
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
const GLASS_SURFACE = "rgba(22, 30, 50, 0.6)";
const GLASS_SURFACE_STRONG = "rgba(13, 18, 32, 0.75)";
const GLASS_BORDER = "1px solid rgba(255, 255, 255, 0.08)";
const GLASS_BLUR = "blur(20px)";
const GRADIENT_ACCENT = "linear-gradient(135deg, #2DD4BF 0%, #A78BFA 100%)";

export const darkTheme = createTheme({
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
      default: "#070B14",
      paper: GLASS_SURFACE,
    },
    text: {
      primary: "#EAF0F5",
      secondary: "#8E9BB3",
    },
    success: { main: "#34D399" },
    warning: { main: "#FBBF24" },
    error: { main: "#F87171" },
    divider: "rgba(255, 255, 255, 0.09)",
  },
  typography: sharedTypography,
  shape: {
    // شعاع خیلی بزرگ‌تر — یکی از سیگنال‌های اصلی زبان بصری «شیشه‌ای/نرم»
    borderRadius: 22,
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          minHeight: "100vh",
          // پس‌زمینه گرادیانت محو (نه رنگ یک‌دست) — تفاوت فوری و آشکار با
          // استایل کلاسیک که پس‌زمینه‌اش تخت و یک‌دست است
          background:
            "radial-gradient(circle at 15% 10%, rgba(45, 212, 191, 0.16), transparent 42%)," +
            "radial-gradient(circle at 85% 0%, rgba(167, 139, 250, 0.18), transparent 45%)," +
            "radial-gradient(circle at 50% 100%, rgba(45, 212, 191, 0.08), transparent 50%)," +
            "#070B14",
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
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.45)",
        },
        elevation1: {
          backgroundColor: GLASS_SURFACE,
          backdropFilter: GLASS_BLUR,
          WebkitBackdropFilter: GLASS_BLUR,
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.45)",
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

/** کلاس CSS کمکی برای نمایش اعداد/کدها با فونت مونو‌اسپیس (خوانایی بهتر در جداول) */
export const monoFontSx = {
  fontFamily: "'JetBrains Mono', 'Consolas', monospace",
  fontFeatureSettings: '"tnum"',
};
