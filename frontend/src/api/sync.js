/**
 * توابع فراخوانی API همگام‌سازی (Sync) اطلاعات سایت‌ها.
 */
import { apiClient } from "./client";

// POST /sync/{id}/test-connection؛ خروجی: نتیجه‌ی تست اتصال به دیتابیس سایت
export async function testSiteConnection(siteId) {
  const { data } = await apiClient.post(`/sync/${siteId}/test-connection`);
  return data;
}

// POST /sync/{id}/run؛ اجرای فوری همگام‌سازی سایت؛ خروجی: نتیجه‌ی اجرا
export async function runSiteSync(siteId) {
  const { data } = await apiClient.post(`/sync/${siteId}/run`);
  return data;
}

// GET /sync/{id}/logs؛ خروجی: تاریخچه‌ی اجرای همگام‌سازی سایت
export async function fetchSyncLogs(siteId) {
  const { data } = await apiClient.get(`/sync/${siteId}/logs`);
  return data;
}

// GET /sync/settings؛ خروجی: تنظیمات همگام‌سازی خودکار
export async function fetchSyncSettings() {
  const { data } = await apiClient.get("/sync/settings");
  return data;
}

// PUT /sync/settings؛ ذخیره‌ی فاصله‌ی زمانی همگام‌سازی خودکار (دقیقه)؛ خروجی: تنظیمات ذخیره‌شده
export async function updateSyncSettings(intervalMinutes) {
  const { data } = await apiClient.put("/sync/settings", { interval_minutes: intervalMinutes });
  return data;
}

// GET /sync/status-summary؛ خروجی: خلاصه‌ی وضعیت همگام‌سازی امروز سایت‌ها
export async function fetchSyncStatusSummary() {
  const { data } = await apiClient.get("/sync/status-summary");
  return data; // { total_sites, success_today, failed_today, not_run_today }
}
