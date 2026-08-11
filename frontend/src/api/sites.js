import { apiClient } from "./client";

export async function fetchSites() {
  const { data } = await apiClient.get("/sites");
  return data;
}

export async function createSite(payload) {
  const { data } = await apiClient.post("/sites", payload);
  return data;
}

export async function setSiteActive(siteId, isActive) {
  const { data } = await apiClient.patch(`/sites/${siteId}`, { is_active: isActive });
  return data;
}

export async function deleteSite(siteId) {
  await apiClient.delete(`/sites/${siteId}`);
}

export async function fetchSiteConnection(siteId) {
  const { data } = await apiClient.get(`/sites/${siteId}/connection`);
  return data; // null اگر تعریف نشده باشد
}

export async function upsertSiteConnection(siteId, payload) {
  const { data } = await apiClient.put(`/sites/${siteId}/connection`, payload);
  return data;
}

export async function deleteSiteConnection(siteId) {
  await apiClient.delete(`/sites/${siteId}/connection`);
}

export async function setSiteConnectionActive(siteId, isActive) {
  const { data } = await apiClient.patch(`/sites/${siteId}/connection/status`, { is_active: isActive });
  return data;
}

export async function fetchSiteMapping(siteId) {
  const { data } = await apiClient.get(`/sites/${siteId}/mapping`);
  return data; // null اگر تعریف نشده باشد
}

export async function upsertSiteMapping(siteId, payload) {
  const { data } = await apiClient.put(`/sites/${siteId}/mapping`, payload);
  return data;
}

export async function deleteSiteMapping(siteId) {
  await apiClient.delete(`/sites/${siteId}/mapping`);
}
