import { createContext, useContext, useEffect, useState } from "react";
import { fetchCurrentUser, loginRequest } from "../api/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setIsLoading(false);
      return;
    }
    fetchCurrentUser()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      })
      .finally(() => setIsLoading(false));
  }, []);

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
