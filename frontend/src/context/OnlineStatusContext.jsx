/**
 * کانتکست وضعیت آنلاین/آفلاین برنامه؛ یک نمونه‌ی مشترک از هوک useOnlineStatus را در اختیار همه قرار می‌دهد.
 */
import { createContext, useContext } from "react";
import { useOnlineStatus as useOnlineStatusHook } from "../hooks/useOnlineStatus";

const OnlineStatusContext = createContext(null);

/**
 * Provider وضعیت اتصال؛ ورودی: children. هوک useOnlineStatus را فقط یک‌بار اجرا می‌کند تا
 * AuthContext، OfflineBanner و LoginPage همه از یک حلقه‌ی Polling مشترک (به /api/health) و یک وضعیت هم‌خوان بخوانند.
 */
export function OnlineStatusProvider({ children }) {
  const value = useOnlineStatusHook();
  return <OnlineStatusContext.Provider value={value}>{children}</OnlineStatusContext.Provider>;
}

// هوک خواندن وضعیت اتصال از کانتکست؛ بیرون از OnlineStatusProvider خطا می‌دهد
export function useOnlineStatus() {
  const ctx = useContext(OnlineStatusContext);
  if (!ctx) throw new Error("useOnlineStatus باید درون OnlineStatusProvider استفاده شود");
  return ctx;
}
