/** API «گزارش خطاها» (مجوز system.logs). */
import { apiClient } from "./client";

export async function fetchErrorLogs(params) {
  const { data } = await apiClient.get("/error-logs", { params });
  return data;
}

export async function fetchErrorLog(id) {
  const { data } = await apiClient.get(`/error-logs/${id}`);
  return data;
}

export async function resolveErrorLog(id) {
  const { data } = await apiClient.post(`/error-logs/${id}/resolve`);
  return data;
}

export async function reopenErrorLog(id) {
  const { data } = await apiClient.post(`/error-logs/${id}/reopen`);
  return data;
}

export async function resolveAllErrorLogs(params) {
  const { data } = await apiClient.post("/error-logs/resolve-all", null, { params });
  return data;
}

export async function fetchErrorAlertSettings() {
  const { data } = await apiClient.get("/error-logs/settings");
  return data;
}

export async function saveErrorAlertSettings(payload) {
  const { data } = await apiClient.put("/error-logs/settings", payload);
  return data;
}

export async function sendTestErrorAlert() {
  const { data } = await apiClient.post("/error-logs/settings/test");
  return data;
}
