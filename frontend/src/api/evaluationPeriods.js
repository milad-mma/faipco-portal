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

export async function updateEvaluationPeriodTitle(periodId, title) {
  const { data } = await apiClient.put(`/performance/periods/${periodId}/title`, { title });
  return data;
}

// confirmTitle: برای دوره‌ای که ارزیابی منتشرشده دارد، عنوان دقیق دوره (تأیید حذف قطعی)
export async function deleteEvaluationPeriod(periodId, confirmTitle) {
  await apiClient.delete(`/performance/periods/${periodId}`, {
    params: confirmTitle ? { confirm_title: confirmTitle } : undefined,
  });
}

export async function setEvaluationPeriodDisabled(periodId, isDisabled) {
  const { data } = await apiClient.put(`/performance/periods/${periodId}/disabled`, { is_disabled: isDisabled });
  return data;
}

export async function fetchPublishedEvaluations(periodId) {
  const { data } = await apiClient.get(`/performance/periods/${periodId}/assignments`);
  return data;
}

export async function deletePublishedEvaluation(periodId, assignmentId) {
  await apiClient.delete(`/performance/periods/${periodId}/assignments/${assignmentId}`);
}
