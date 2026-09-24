/**
 * کانتکست حالت تم (روشن/تیره).
 * حالت انتخابی را در localStorage نگه می‌دارد، در نبود انتخاب دستی از تنظیم سیستم (prefers-color-scheme) پیروی می‌کند
 * و ThemeProvider و CssBaseline متریال را با تم متناظر رندر می‌کند.
 */
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { darkTheme, lightTheme } from "../theme";

const STORAGE_KEY = "faipco_theme_mode"; // کلید localStorage برای انتخاب دستی: "light" | "dark"

const ThemeModeContext = createContext(null);

// خروجی: true اگر تنظیم سیستم‌عامل/مرورگر کاربر حالت تیره باشد
function getSystemPrefersDark() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/**
 * Provider تم؛ ورودی: children. بین دو تم «کلاسیک» (روشن) و «مدرن تیره» جابه‌جا می‌کند (فقط رنگ‌بندی MUI Theme).
 * بدون انتخاب دستی، زنده از prefers-color-scheme سیستم پیروی می‌کند؛ انتخاب دستی در localStorage
 * (مستقل از کاربر واردشده، تا پیش از ورود هم اعمال شود) ذخیره می‌شود و تا فراخوانی resetToSystem همان اعمال می‌شود.
 */
export function ThemeModeProvider({ children }) {
  // حالت اولیه: انتخاب ذخیره‌شده در localStorage، در غیر این صورت تنظیم سیستم
  const [mode, setModeState] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "dark" || saved === "light") return saved;
    return getSystemPrefersDark() ? "dark" : "light";
  });
  // آیا کاربر دستی حالتی انتخاب کرده است؛ اگر نه، حالت زنده از سیستم پیروی می‌کند
  const [isManual, setIsManual] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === "dark" || saved === "light";
  });

  // گوش دادن به تغییر prefers-color-scheme سیستم و اعمال زنده‌ی آن؛ فقط وقتی انتخاب دستی وجود ندارد
  useEffect(() => {
    if (isManual || !window.matchMedia) return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    function handleChange(e) {
      setModeState(e.matches ? "dark" : "light");
    }
    mql.addEventListener("change", handleChange);
    return () => mql.removeEventListener("change", handleChange);
  }, [isManual]);

  // تنظیم دستی حالت تم و ذخیره‌ی آن در localStorage
  function setMode(nextMode) {
    setModeState(nextMode);
    setIsManual(true);
    localStorage.setItem(STORAGE_KEY, nextMode);
  }

  // جابه‌جایی بین حالت روشن و تیره
  function toggleMode() {
    setMode(mode === "light" ? "dark" : "light");
  }

  /** برگشت به پیروی خودکار از تنظیمات سیستم (حذف انتخاب دستی از localStorage) */
  function resetToSystem() {
    localStorage.removeItem(STORAGE_KEY);
    setIsManual(false);
    setModeState(getSystemPrefersDark() ? "dark" : "light");
  }

  // انتخاب شیء تم MUI متناظر با حالت فعلی
  const theme = useMemo(() => (mode === "dark" ? darkTheme : lightTheme), [mode]);

  // مقدار کانتکست؛ فقط با تغییر mode یا isManual دوباره ساخته می‌شود
  const value = useMemo(
    () => ({ mode, setMode, toggleMode, isManual, resetToSystem }),
    [mode, isManual]
  );

  return (
    <ThemeModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemeModeContext.Provider>
  );
}

// هوک دسترسی به کانتکست تم؛ بیرون از ThemeModeProvider خطا می‌دهد
export function useThemeMode() {
  const ctx = useContext(ThemeModeContext);
  if (!ctx) throw new Error("useThemeMode باید درون ThemeModeProvider استفاده شود");
  return ctx;
}
