import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * فقط کاربر Admin (is_superuser) به این مسیرها دسترسی دارد — بقیه نقش‌ها
 * (مدیر سایت، مدیر میانی، پرسنل عادی) به داشبورد شخصی خودشان هدایت
 * می‌شوند (قبلاً به /notices بود — با اضافه‌شدن داشبورد شخصی جدید،
 * صفحه پیش‌فرض هرکسی که Admin نیست همان شد، مطابق طرح جدید که «داشبورد»
 * تب پیش‌فرض/اول است). این یک لایه محافظتی در UI است؛ بررسی واقعی
 * امنیتی همیشه در Backend انجام می‌شود.
 */
export default function AdminRoute({ children }) {
  const { user } = useAuth();
  if (!user?.is_superuser) {
    return <Navigate to="/my-dashboard" replace />;
  }
  return children;
}
