import { apiClient } from "./client";

export async function fetchEvaluationPeriods(siteId) {
  const { data } = await apiClient.get("/performance/periods", { params: { site_id: siteId } });
  return data;
}

export async function createEvaluationPeriod(payload) {
  const { data } = await apiClient.post("/performance/periods", payload);
  return data;
}

export async function updateEvaluationPeriod(periodId, payload) {
  const { data } = await apiClient.put(`/performance/periods/${periodId}`, payload);
  return data;
}

export async function updateEvaluationPeriodStatus(periodId, status) {
  const { data } = await apiClient.put(`/performance/periods/${periodId}/status`, { status });
  return data;
}

export async function deleteEvaluationPeriod(periodId) {
  await apiClient.delete(`/performance/periods/${periodId}`);
}
