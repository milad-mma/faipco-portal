import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * فقط کاربر Admin (is_superuser) به این مسیرها دسترسی دارد — بقیه نقش‌ها
 * (مدیر سایت، مدیر میانی، پرسنل عادی) فقط باید صفحه اطلاعیه‌ها را ببینند.
 * این یک لایه محافظتی در UI است؛ بررسی واقعی امنیتی همیشه در Backend انجام می‌شود.
 */
export default function AdminRoute({ children }) {
  const { user } = useAuth();
  if (!user?.is_superuser) {
    return <Navigate to="/notices" replace />;
  }
  return children;
}
