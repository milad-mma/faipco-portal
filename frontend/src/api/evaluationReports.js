import { apiClient } from "./client";

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

export async function fetchSitePeriodReport(siteId, periodId) {
  const { data } = await apiClient.get(`/performance/reports/sites/${siteId}/periods/${periodId}`);
  return data;
}

export async function downloadSitePeriodReport(siteId, periodId) {
  await downloadBlob(
    `/performance/reports/sites/${siteId}/periods/${periodId}/export`,
    `performance-report-${siteId}-${periodId}.xlsx`
  );
}

export async function emailSitePeriodReport(siteId, periodId, email) {
  const { data } = await apiClient.post(`/performance/reports/sites/${siteId}/periods/${periodId}/email`, {
    email,
  });
  return data;
}

export async function fetchPeriodComparison(siteId, periodIdA, periodIdB) {
  const { data } = await apiClient.get(`/performance/reports/sites/${siteId}/compare`, {
    params: { period_id_a: periodIdA, period_id_b: periodIdB },
  });
  return data;
}

export async function downloadPeriodComparison(siteId, periodIdA, periodIdB) {
  await downloadBlob(
    `/performance/reports/sites/${siteId}/compare/export?period_id_a=${periodIdA}&period_id_b=${periodIdB}`,
    `performance-comparison-${siteId}-${periodIdA}-${periodIdB}.xlsx`
  );
}

export async function emailPeriodComparison(siteId, periodIdA, periodIdB, email) {
  const { data } = await apiClient.post(
    `/performance/reports/sites/${siteId}/compare/email?period_id_a=${periodIdA}&period_id_b=${periodIdB}`,
    { email }
  );
  return data;
}
