import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * مثل AdminRoute، ولی به‌جای فقط چک‌کردن is_superuser، یک شرط دلخواه
 * (check) روی user می‌گیرد — برای مسیرهایی که مجوزشان مخصوص is_superuser
 * نیست (مثلاً بین چند نقش مشترک است، مثل hr-manager). این هم فقط یک لایه
 * محافظتی در UI است؛ بررسی واقعی امنیتی همیشه در Backend انجام می‌شود —
 * ولی همین لایه UI باعث می‌شود بدون دسترسی، خودِ صفحه اصلاً رندر/باز نشود
 * (نه این‌که باز شود و فقط درخواست‌های API‌اش خطا بدهند).
 */
export default function PermissionRoute({ check, children }) {
  const { user } = useAuth();
  if (!check(user)) {
    return <Navigate to="/notices" replace />;
  }
  return children;
}
