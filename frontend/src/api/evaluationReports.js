/**
 * توابع API گزارش‌های ارزیابی عملکرد (/performance/reports).
 * شامل گزارش دوره‌ی سایت، مقایسه‌ی دو دوره، روند پرسنل، دانلود Excel و ارسال گزارش با ایمیل.
 */
import { apiClient } from "./client";

// فایل را از url به‌صورت blob می‌گیرد و با یک لینک موقت با نام filename در مرورگر دانلود می‌کند
async function downloadBlob(url, filename) {
  const response = await apiClient.get(url, { responseType: "blob" });
  const blobUrl = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(blobUrl);
}

// GET /performance/reports/sites/{siteId}/periods/{periodId}؛ گزارش یک دوره‌ی سایت را برمی‌گرداند
export async function fetchSitePeriodReport(siteId, periodId) {
  const { data } = await apiClient.get(`/performance/reports/sites/${siteId}/periods/${periodId}`);
  return data;
}

// GET .../periods/{periodId}/export؛ فایل Excel گزارش دوره را دانلود می‌کند
export async function downloadSitePeriodReport(siteId, periodId) {
  await downloadBlob(
    `/performance/reports/sites/${siteId}/periods/${periodId}/export`,
    `performance-report-${siteId}-${periodId}.xlsx`
  );
}

// POST .../periods/{periodId}/email؛ گزارش دوره را به ایمیل داده‌شده می‌فرستد و پاسخ سرور را برمی‌گرداند
export async function emailSitePeriodReport(siteId, periodId, email) {
  const { data } = await apiClient.post(`/performance/reports/sites/${siteId}/periods/${periodId}/email`, {
    email,
  });
  return data;
}

// GET /performance/reports/sites/{siteId}/compare؛ مقایسه‌ی دو دوره (A و B) را برمی‌گرداند
export async function fetchPeriodComparison(siteId, periodIdA, periodIdB) {
  const { data } = await apiClient.get(`/performance/reports/sites/${siteId}/compare`, {
    params: { period_id_a: periodIdA, period_id_b: periodIdB },
  });
  return data;
}

// GET .../compare/export؛ فایل Excel مقایسه‌ی دو دوره را دانلود می‌کند
export async function downloadPeriodComparison(siteId, periodIdA, periodIdB) {
  await downloadBlob(
    `/performance/reports/sites/${siteId}/compare/export?period_id_a=${periodIdA}&period_id_b=${periodIdB}`,
    `performance-comparison-${siteId}-${periodIdA}-${periodIdB}.xlsx`
  );
}

// POST .../compare/email؛ گزارش مقایسه‌ی دو دوره را به ایمیل داده‌شده می‌فرستد
export async function emailPeriodComparison(siteId, periodIdA, periodIdB, email) {
  const { data } = await apiClient.post(
    `/performance/reports/sites/${siteId}/compare/email?period_id_a=${periodIdA}&period_id_b=${periodIdB}`,
    { email }
  );
  return data;
}

// GET .../evaluations/{id}/answers؛ پاسخ‌های یک ارزیابی را برای نمایش در گزارش برمی‌گرداند
export async function fetchEvaluationAnswersForReport(siteId, evaluationId) {
  const { data } = await apiClient.get(
    `/performance/reports/sites/${siteId}/evaluations/${evaluationId}/answers`
  );
  return data;
}

// GET .../employees/{personnelCode}/trend؛ روند امتیاز یک پرسنل در دوره‌های مختلف را برمی‌گرداند
export async function fetchEmployeeTrend(siteId, personnelCode) {
  const { data } = await apiClient.get(
    `/performance/reports/sites/${siteId}/employees/${encodeURIComponent(personnelCode)}/trend`
  );
  return data;
}
