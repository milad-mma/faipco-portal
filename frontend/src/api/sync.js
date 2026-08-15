import { apiClient } from "./client";

export async function testSiteConnection(siteId) {
  const { data } = await apiClient.post(`/sync/${siteId}/test-connection`);
  return data;
}

export async function runSiteSync(siteId) {
  const { data } = await apiClient.post(`/sync/${siteId}/run`);
  return data;
}

export async function fetchSyncLogs(siteId) {
  const { data } = await apiClient.get(`/sync/${siteId}/logs`);
  return data;
}

export async function fetchSyncSettings() {
  const { data } = await apiClient.get("/sync/settings");
  return data;
}

export async function updateSyncSettings(intervalMinutes) {
  const { data } = await apiClient.put("/sync/settings", { interval_minutes: intervalMinutes });
  return data;
}

export async function fetchSyncStatusSummary() {
  const { data } = await apiClient.get("/sync/status-summary");
  return data; // { total_sites, success_today, failed_today, not_run_today }
}
