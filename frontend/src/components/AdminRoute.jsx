import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * محافظ مسیرهای مدیریتی: فقط کاربر Admin (is_superuser) به children دسترسی دارد.
 * ورودی: children (محتوای مسیر). خروجی: همان children، یا برای بقیه‌ی نقش‌ها
 * (مدیر سایت، مدیر میانی، پرسنل عادی) هدایت به داشبورد شخصی /my-dashboard.
 * این فقط یک لایه‌ی محافظتی در UI است؛ بررسی امنیتی واقعی در Backend انجام می‌شود.
 */
export default function AdminRoute({ children }) {
  const { user } = useAuth();
  if (!user?.is_superuser) {
    return <Navigate to="/my-dashboard" replace />;
  }
  return children;
}
