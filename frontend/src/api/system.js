import { apiClient } from "./client";

export async function bustAppCache() {
  const { data } = await apiClient.post("/system/cache-bust");
  return data; // { success, version, message }
}

export async function fetchIpAllowlist() {
  const { data } = await apiClient.get("/system/ip-allowlist");
  return data;
}

export async function addIpAllowlistEntry({ cidr, label }) {
  const { data } = await apiClient.post("/system/ip-allowlist", { cidr, label: label || null });
  return data;
}

export async function deleteIpAllowlistEntry(entryId) {
  await apiClient.delete(`/system/ip-allowlist/${entryId}`);
}
