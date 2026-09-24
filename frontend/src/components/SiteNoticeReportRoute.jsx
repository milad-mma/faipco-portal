import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * محافظ مسیر /notice-reports که هم ادمین (گزارش کل سیستم) و هم site_manager (گزارش سایت خودش) باید ببینند.
 * ورودی: children. خروجی: اگر user.can_view_site_notice_report درست باشد children، وگرنه هدایت به /notices.
 * این فلگ در Backend (get_me) برای is_superuser یا مدیر حداقل یک سایت درست است.
 * این فقط لایه‌ی UI است؛ بررسی امنیتی واقعی (کدام سایت‌ها) در Backend انجام می‌شود.
 */
export default function SiteNoticeReportRoute({ children }) {
  const { user } = useAuth();
  if (!user?.can_view_site_notice_report) {
    return <Navigate to="/notices" replace />;
  }
  return children;
}
