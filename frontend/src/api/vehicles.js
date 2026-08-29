import { apiClient } from "./client";

export async function fetchMyVehicles() {
  const { data } = await apiClient.get("/vehicles/me");
  return data;
}

export async function createMyVehicle(payload) {
  const { data } = await apiClient.post("/vehicles/me", payload);
  return data;
}

export async function deleteMyVehicle(vehicleId) {
  await apiClient.delete(`/vehicles/me/${vehicleId}`);
}

export async function fetchAllVehicles(siteId) {
  const { data } = await apiClient.get("/vehicles", { params: siteId ? { site_id: siteId } : {} });
  return data;
}

export async function updateVehicleAdmin(vehicleId, payload) {
  const { data } = await apiClient.patch(`/vehicles/${vehicleId}`, payload);
  return data;
}

export async function deleteVehicleAdmin(vehicleId) {
  await apiClient.delete(`/vehicles/${vehicleId}`);
}
