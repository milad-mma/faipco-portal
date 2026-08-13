import { createTheme } from "@mui/material/styles";

/**
 * دو Design Token کاملاً مستقل — «کلاسیک» (پیش‌فرض قبلی پروژه) و «مدرن تیره»
 * (استایل دوم، انتخابی از پنل). فقط رنگ‌بندی/شکل ظاهری فرق دارن — متن‌ها،
 * لوگو، و ساختار صفحات کاملاً دست‌نخورده می‌مونن چون این‌ها فقط Theme
 * سطح MUI هستن، نه چیزی که محتوای صفحات رو عوض کنه.
 * ------------------------------------------------------------
 * کلاسیک (Light):
 *   Primary:   #16324F  (سرمه‌ای صنعتی)      Accent: #E0A458 (طلایی‌کهربایی)
 *   Background:#F5F7FA                       Surface: #FFFFFF
 * ------------------------------------------------------------
 * مدرن تیره (Dark):
 *   Primary:   #2DD4BF  (فیروزه‌ای مدرن)      Accent: #FBBF24 (کهربایی روشن)
 *   Background:#0B1220  (سرمه‌ای تقریباً مشکی) Surface: #141B2D
 * ------------------------------------------------------------
 * Type (هر دو حالت): Vazirmatn برای متن فارسی، "JetBrains Mono" برای
 * اعداد/کدهای پرسنلی در جداول.
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

export const darkTheme = createTheme({
  direction: "rtl",
  palette: {
    mode: "dark",
    primary: {
      main: "#2DD4BF",
      light: "#5EEAD4",
      dark: "#14B8A6",
      contrastText: "#08130F",
    },
    secondary: {
      main: "#FBBF24",
      light: "#FDD061",
      dark: "#E0A812",
      contrastText: "#1A1204",
    },
    background: {
      default: "#0B1220",
      paper: "#141B2D",
    },
    text: {
      primary: "#E8EDF2",
      secondary: "#8B96A8",
    },
    success: { main: "#34D399" },
    warning: { main: "#F59E0B" },
    error: { main: "#F87171" },
    divider: "#232B40",
  },
  typography: sharedTypography,
  shape: {
    // شعاع بزرگ‌تر — یکی از سیگنال‌های بصری که این استایل رو از استایل
    // کلاسیک (که شعاع کوچیک‌تر و رسمی‌تری داره) متمایز می‌کنه
    borderRadius: 16,
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          border: "1px solid #232B40",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 12,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontWeight: 700,
          backgroundColor: "#1A2338",
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
