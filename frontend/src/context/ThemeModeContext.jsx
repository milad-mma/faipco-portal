import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { darkTheme, lightTheme } from "../theme";

const STORAGE_KEY = "faipco_theme_mode"; // "light" | "dark"

const ThemeModeContext = createContext(null);

/**
 * دو استایل کاملاً مستقل («کلاسیک» و «مدرن تیره») که از پنل (منوی حساب
 * کاربری) قابل‌انتخابن — فقط ظاهر عوض می‌شه، متن‌ها/لوگو/ساختار صفحات
 * دست‌نخورده می‌مونه چون این‌ها فقط رنگ‌بندی سطح MUI Theme هستن. انتخاب در
 * localStorage ذخیره می‌شه (نه وابسته به کاربر لاگین‌شده) تا حتی قبل از
 * ورود (صفحه Login) هم همون استایل انتخابی اعمال بشه.
 */
export function ThemeModeProvider({ children }) {
  const [mode, setMode] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === "dark" ? "dark" : "light";
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, mode);
  }, [mode]);

  function toggleMode() {
    setMode((prev) => (prev === "light" ? "dark" : "light"));
  }

  const theme = useMemo(() => (mode === "dark" ? darkTheme : lightTheme), [mode]);

  const value = useMemo(() => ({ mode, setMode, toggleMode }), [mode]);

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
