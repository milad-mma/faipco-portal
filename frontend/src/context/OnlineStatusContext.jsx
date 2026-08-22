import { createContext, useContext } from "react";
import { useOnlineStatus as useOnlineStatusHook } from "../hooks/useOnlineStatus";

const OnlineStatusContext = createContext(null);

/**
 * یک نمونه مشترک از useOnlineStatus برای کل برنامه — چون AuthContext،
 * OfflineBanner، و LoginPage هرکدام به این وضعیت نیاز دارند، اگر هرکدام
 * جدا خودِ Hook را صدا بزنند، چند حلقه Polling کاملاً مستقل (هرکدام هر ۲۰
 * ثانیه یک درخواست به /api/health) هم‌زمان اجرا می‌شود — هم اتلاف
 * درخواست، هم ریسک اینکه لحظه‌ای با هم ناهم‌خوان باشند (مثلاً بنر بگوید
 * آنلاین ولی صفحه ورود هنوز آفلاین نشان بدهد). با این Provider، یک منبع
 * واحد وجود دارد که همه از آن می‌خوانند.
 */
export function OnlineStatusProvider({ children }) {
  const value = useOnlineStatusHook();
  return <OnlineStatusContext.Provider value={value}>{children}</OnlineStatusContext.Provider>;
}

export function useOnlineStatus() {
  const ctx = useContext(OnlineStatusContext);
  if (!ctx) throw new Error("useOnlineStatus باید درون OnlineStatusProvider استفاده شود");
  return ctx;
}
