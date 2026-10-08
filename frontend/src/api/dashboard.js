import { apiClient } from "./client";

// GET /dashboard/site-stats؛ خروجی: آمار کارت‌های داشبورد به تفکیک سایت
// [{site_id, site_name, employees_active, departments_total, departments_without_supervisor, sync_today, notices_week, portal_disabled}]
export async function fetchDashboardSiteStats() {
  const { data } = await apiClient.get("/dashboard/site-stats");
  return data;
}
