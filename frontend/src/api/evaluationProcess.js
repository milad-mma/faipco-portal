import { apiClient } from "./client";

export async function generateEvaluationAssignments(periodId, formId) {
  const { data } = await apiClient.post(`/performance/periods/${periodId}/generate-assignments`, {
    form_id: formId,
  });
  return data;
}

export async function fetchMyEvaluations() {
  const { data } = await apiClient.get("/performance/my-evaluations");
  return data;
}

export async function fetchMyShiftLeadEvaluations() {
  const { data } = await apiClient.get("/performance/my-shift-lead-evaluations");
  return data;
}

export async function fetchEvaluationById(evaluationId) {
  const { data } = await apiClient.get(`/performance/evaluations/${evaluationId}`);
  return data;
}

export async function startEvaluation(assignmentId) {
  const { data } = await apiClient.post(`/performance/assignments/${assignmentId}/start`);
  return data;
}

export async function saveEvaluationAnswers(evaluationId, answers) {
  const { data } = await apiClient.put(`/performance/evaluations/${evaluationId}/answers`, { answers });
  return data;
}

export async function submitEvaluation(evaluationId) {
  const { data } = await apiClient.post(`/performance/evaluations/${evaluationId}/submit`);
  return data;
}

export async function fetchMyEvaluationResults() {
  const { data } = await apiClient.get("/performance/my-results");
  return data;
}

export async function reopenEvaluation(evaluationId) {
  const { data } = await apiClient.post(`/performance/evaluations/${evaluationId}/reopen`);
  return data;
}

export async function fetchMyYearlyAverage(jalaliYear) {
  const { data } = await apiClient.get("/performance/my-yearly-average", {
    params: jalaliYear ? { jalali_year: jalaliYear } : {},
  });
  return data;
}

export async function fetchMyEvaluationDashboardSummary() {
  const { data } = await apiClient.get("/performance/my-dashboard-summary");
  return data;
}
