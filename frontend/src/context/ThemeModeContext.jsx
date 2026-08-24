import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { darkTheme, lightTheme } from "../theme";

const STORAGE_KEY = "faipco_theme_mode"; // "light" | "dark"

const ThemeModeContext = createContext(null);

function getSystemPrefersDark() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/**
 * دو استایل کاملاً مستقل («کلاسیک» و «مدرن تیره») که از پنل (منوی حساب
 * کاربری) قابل‌انتخابن — فقط ظاهر عوض می‌شه، متن‌ها/لوگو/ساختار صفحات
 * دست‌نخورده می‌مونه چون این‌ها فقط رنگ‌بندی سطح MUI Theme هستن.
 *
 * پیش‌فرض (اگر کاربر قبلاً دستی چیزی انتخاب نکرده باشد): از تنظیمات سیستم
 * خودِ کاربر (prefers-color-scheme) پیروی می‌کند — و اگر کاربر همان لحظه
 * تنظیمات سیستمش را عوض کند (مثلاً ساعت مشخصی از شب به تیره سوییچ می‌کند)،
 * پرتال هم زنده همراهش عوض می‌شود. به‌محض این‌که کاربر یک‌بار دستی از همین
 * منو انتخاب کند، آن انتخاب در localStorage ذخیره و دیگر همیشه همان اعمال
 * می‌شود (نه وابسته به کاربر لاگین‌شده، تا حتی قبل از ورود هم همان استایل
 * انتخابی اعمال بشه) — پیروی از سیستم دیگر تا وقتی کاربر دستی «پیروی از
 * سیستم» را دوباره فعال نکند (resetToSystem)، متوقف می‌ماند.
 */
export function ThemeModeProvider({ children }) {
  const [mode, setModeState] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "dark" || saved === "light") return saved;
    return getSystemPrefersDark() ? "dark" : "light";
  });
  // آیا کاربر تا الان دستی چیزی انتخاب کرده؟ اگر نه، باید زنده از سیستم پیروی کنیم.
  const [isManual, setIsManual] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === "dark" || saved === "light";
  });

  // پیروی زنده از تغییر تنظیمات سیستم — فقط تا وقتی کاربر دستی انتخاب نکرده
  useEffect(() => {
    if (isManual || !window.matchMedia) return;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");
    function handleChange(e) {
      setModeState(e.matches ? "dark" : "light");
    }
    mql.addEventListener("change", handleChange);
    return () => mql.removeEventListener("change", handleChange);
  }, [isManual]);

  function setMode(nextMode) {
    setModeState(nextMode);
    setIsManual(true);
    localStorage.setItem(STORAGE_KEY, nextMode);
  }

  function toggleMode() {
    setMode(mode === "light" ? "dark" : "light");
  }

  /** برگشت به پیروی خودکار از تنظیمات سیستم (لغو انتخاب دستی قبلی) */
  function resetToSystem() {
    localStorage.removeItem(STORAGE_KEY);
    setIsManual(false);
    setModeState(getSystemPrefersDark() ? "dark" : "light");
  }

  const theme = useMemo(() => (mode === "dark" ? darkTheme : lightTheme), [mode]);

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

export function useThemeMode() {
  const ctx = useContext(ThemeModeContext);
  if (!ctx) throw new Error("useThemeMode باید درون ThemeModeProvider استفاده شود");
  return ctx;
}
