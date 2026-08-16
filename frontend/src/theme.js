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
const GLASS_SURFACE = "rgba(42, 53, 82, 0.55)";
const GLASS_SURFACE_STRONG = "rgba(30, 39, 62, 0.7)";
const GLASS_BORDER = "1px solid rgba(255, 255, 255, 0.09)";
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
    // شعاع خیلی بزرگ‌تر — یکی از سیگنال‌های اصلی زبان بصری «شیشه‌ای/نرم»
    borderRadius: 22,
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

/** کلاس CSS کمکی برای نمایش اعداد/کدها با فونت مونو‌اسپیس (خوانایی بهتر در جداول) */
export const monoFontSx = {
  fontFamily: "'JetBrains Mono', 'Consolas', monospace",
  fontFeatureSettings: '"tnum"',
};
