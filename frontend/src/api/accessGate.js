import { apiClient } from "./client";

export async function fetchMyAccessGateStatus() {
  const { data } = await apiClient.get("/access-gate/my-status");
  return data;
}

export async function fetchAccessGateSettings() {
  const { data } = await apiClient.get("/access-gate/settings");
  return data;
}

export async function updateAccessGateSetting(gate, feature, enabled) {
  const { data } = await apiClient.put("/access-gate/settings", { gate, feature, enabled });
  return data;
}
