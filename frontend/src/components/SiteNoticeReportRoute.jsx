import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

/**
 * برخلاف AdminRoute (که فقط is_superuser را می‌پذیرد)، این یکی برای
 * /notice-reports است — که هم Admin واقعی (گزارش کامل سیستم) و هم
 * site_manager (گزارش سایت خودش) باید ببینند. can_view_site_notice_report
 * از قبل هردو حالت را روی Backend پوشش می‌دهد (در get_me()، یا is_superuser
 * یا حداقل یک سایت تحت مدیریت). این یک لایه محافظتی در UI است؛ بررسی
 * واقعی امنیتی (کدام سایت‌ها) همیشه در Backend انجام می‌شود.
 */
export default function SiteNoticeReportRoute({ children }) {
  const { user } = useAuth();
  if (!user?.can_view_site_notice_report) {
    return <Navigate to="/notices" replace />;
  }
  return children;
}
