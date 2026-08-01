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
