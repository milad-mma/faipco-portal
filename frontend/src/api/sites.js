import { apiClient } from "./client";

export async function fetchSites() {
  const { data } = await apiClient.get("/sites");
  return data;
}

export async function createSite(payload) {
  const { data } = await apiClient.post("/sites", payload);
  return data;
}

export async function upsertSiteConnection(siteId, payload) {
  const { data } = await apiClient.put(`/sites/${siteId}/connection`, payload);
  return data;
}

export async function upsertSiteMapping(siteId, payload) {
  const { data } = await apiClient.put(`/sites/${siteId}/mapping`, payload);
  return data;
}
