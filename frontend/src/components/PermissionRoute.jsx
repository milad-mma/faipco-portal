import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * محافظ مسیر بر اساس یک شرط دلخواه روی کاربر (مشابه AdminRoute ولی نه فقط is_superuser).
 * ورودی: check (تابعی که user را می‌گیرد و true/false برمی‌گرداند) و children.
 * خروجی: اگر شرط برقرار باشد children، وگرنه هدایت به /notices؛ بنابراین صفحه‌ی بدون دسترسی اصلاً رندر نمی‌شود.
 * این فقط لایه‌ی UI است؛ بررسی امنیتی واقعی در Backend انجام می‌شود.
 */
export default function PermissionRoute({ check, children }) {
  const { user } = useAuth();
  if (!check(user)) {
    return <Navigate to="/notices" replace />;
  }
  return children;
}
