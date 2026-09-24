/**
 * کانتکست احراز هویت.
 * کاربر جاری، وضعیت بارگذاری و توابع ورود/خروج/بازخوانی کاربر را فراهم می‌کند؛
 * هنگام شروع برنامه و پس از وصل شدن دوباره‌ی اینترنت، Session را از توکن ذخیره‌شده بازیابی می‌کند.
 */
import { createContext, useContext, useEffect, useState } from "react";
import { fetchCurrentUser, loginRequest } from "../api/auth";
import { useOnlineStatus } from "./OnlineStatusContext";
import { setCacheOwner } from "../api/swrCache";

// کانتکست نگهدارنده‌ی { user, isLoading, login, logout, refetchUser }
const AuthContext = createContext(null);

/**
 * Provider احراز هویت؛ ورودی: children. وضعیت کاربر و توابع احراز هویت را در اختیار زیرشاخه قرار می‌دهد.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const { isOnline } = useOnlineStatus();
  // Cache داده‌های صفحات متعلق به همین کاربر است؛ با تغییر کاربر (خروج/ورود دیگری) پاک می‌شود.
  // عمداً در بدنه‌ی رندر (نه useEffect) تا قبل از effect صفحات فرزند اعمال شود؛ فراخوانی تکراری بی‌اثر است.
  setCacheOwner(user?.id);

  // اگر access_token ذخیره شده باشد، کاربر جاری را از سرور می‌گیرد؛ در پایان isLoading را false می‌کند
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
      // توکن‌ها فقط با پاسخ 401 (توکن نامعتبر) پاک می‌شوند؛ خطای شبکه، Timeout یا در دسترس نبودن
      // سرور توکن را پاک نمی‌کند چون توکن هنوز معتبر است و فقط همین لحظه قابل تأیید نیست
      if (error.response?.status === 401) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      }
      // در خطای شبکه توکن می‌ماند و با وصل شدن اینترنت (افکت پایین) همین تابع دوباره اجرا می‌شود
    } finally {
      setIsLoading(false);
    }
  }

  // بازیابی Session یک‌بار هنگام mount
  useEffect(() => {
    tryRestoreSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // وقتی اتصال برقرار می‌شود و کاربر هنوز تأیید نشده ولی توکن موجود است، بازیابی Session دوباره انجام می‌شود
  // تا کاربر پس از قطعی موقت اینترنت نیازی به ورود مجدد نداشته باشد
  useEffect(() => {
    if (isOnline && !user && localStorage.getItem("access_token")) {
      tryRestoreSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOnline]);

  // ورود کاربر: توکن‌ها را می‌گیرد و ذخیره می‌کند، سپس کاربر جاری را می‌خواند؛ خروجی: کاربر جاری
  async function login(username, password) {
    // فرم ورود یکپارچه است: هم مدیر (نام کاربری/رمز) و هم پرسنل (کد پرسنلی/کد ملی)؛ تشخیص در Backend انجام می‌شود
    const tokens = await loginRequest(username, password);
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    const currentUser = await fetchCurrentUser();
    setUser(currentUser);
    return currentUser;
  }

  /** اطلاعات کاربر جاری را دوباره از سرور می‌خواند (مثلاً پس از تغییر رمز و پاک شدن must_change_password)
   * بدون نیاز به خروج/ورود یا Reload صفحه؛ خروجی: کاربر جاری */
  async function refetchUser() {
    const currentUser = await fetchCurrentUser();
    setUser(currentUser);
    return currentUser;
  }

  // خروج: حذف توکن‌ها از localStorage و خالی کردن کاربر جاری
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

// هوک دسترسی به کانتکست احراز هویت؛ بیرون از AuthProvider خطا می‌دهد
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth باید درون AuthProvider استفاده شود");
  return ctx;
}
