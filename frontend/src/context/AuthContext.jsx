import { createContext, useContext, useEffect, useState } from "react";
import { fetchCurrentUser, loginRequest } from "../api/auth";
import { useOnlineStatus } from "./OnlineStatusContext";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const { isOnline } = useOnlineStatus();

  async function tryRestoreSession() {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setIsLoading(false);
      return;
    }
    try {
      const currentUser = await fetchCurrentUser();
      setUser(currentUser);
    } catch (error) {
      // فقط اگر واقعاً سرور گفته «این توکن معتبر نیست» (۴۰۱) پاک کن و
      // Logout کن — نه برای خطای شبکه (آفلاین بودن، Timeout، یا سرور
      // موقتاً در دسترس نیست)، چون در آن حالت توکن‌ها هنوز کاملاً معتبرند،
      // فقط همین لحظه قابل‌تأیید نیستند. قبلاً هر نوع خطایی (حتی قطعی
      // اینترنت) باعث پاک‌شدن توکن می‌شد — یعنی کاربری که با اینترنت قطع
      // به پنل برمی‌گشت، مجبور به ورود دوباره می‌شد، با اینکه Session او
      // هنوز کاملاً معتبر بود.
      if (error.response?.status === 401) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      }
      // برای خطای شبکه، توکن دست‌نخورده می‌ماند — همین که اینترنت برگردد
      // (افکت پایین)، همین تابع دوباره تلاش می‌کند، بدون نیاز به ورود مجدد.
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    tryRestoreSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // اگر اتصال از قطع به وصل تغییر کرد و هنوز کاربری تأیید نشده (ولی
    // توکن در localStorage هست، طبق منطق بالا)، همین الان دوباره تلاش کن —
    // کاربر نباید مجبور شود دوباره رمز عبور وارد کند فقط چون یک لحظه
    // اینترنتش قطع بوده.
    if (isOnline && !user && localStorage.getItem("access_token")) {
      tryRestoreSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOnline]);

  async function login(username, password) {
    // فرم ورود یکپارچه است: همین یک تابع هم برای مدیریت (یوزرنیم/پسورد)
    // و هم برای پرسنل (کد پرسنلی/کد ملی) کار می‌کند — تشخیص در Backend انجام می‌شود.
    const tokens = await loginRequest(username, password);
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    const currentUser = await fetchCurrentUser();
    setUser(currentUser);
    return currentUser;
  }

  /** بعد از تغییر موفق رمز عبور (مثلاً پاک‌شدن must_change_password) صدا
   * زده می‌شود — بدون نیاز به خروج/ورود دوباره یا Reload کامل صفحه. */
  async function refetchUser() {
    const currentUser = await fetchCurrentUser();
    setUser(currentUser);
    return currentUser;
  }

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, refetchUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth باید درون AuthProvider استفاده شود");
  return ctx;
}
