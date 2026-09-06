import { apiClient } from "./client";

export async function fetchEvaluationForms(siteId) {
  const { data } = await apiClient.get("/performance/forms", { params: { site_id: siteId } });
  return data;
}

export async function fetchEvaluationForm(formId) {
  const { data } = await apiClient.get(`/performance/forms/${formId}`);
  return data;
}

export async function createEvaluationForm(payload) {
  const { data } = await apiClient.post("/performance/forms", payload);
  return data;
}

export async function updateEvaluationForm(formId, payload) {
  const { data } = await apiClient.put(`/performance/forms/${formId}`, payload);
  return data;
}

export async function updateEvaluationFormStatus(formId, status) {
  const { data } = await apiClient.put(`/performance/forms/${formId}/status`, { status });
  return data;
}

export async function duplicateEvaluationForm(formId) {
  const { data } = await apiClient.post(`/performance/forms/${formId}/duplicate`);
  return data;
}

export async function deleteEvaluationForm(formId) {
  await apiClient.delete(`/performance/forms/${formId}`);
}

export async function addEvaluationCategory(formId, payload) {
  const { data } = await apiClient.post(`/performance/forms/${formId}/categories`, payload);
  return data;
}

export async function updateEvaluationCategory(categoryId, payload) {
  const { data } = await apiClient.put(`/performance/forms/categories/${categoryId}`, payload);
  return data;
}

export async function deleteEvaluationCategory(categoryId) {
  await apiClient.delete(`/performance/forms/categories/${categoryId}`);
}

export async function addEvaluationQuestion(categoryId, payload) {
  const { data } = await apiClient.post(`/performance/forms/categories/${categoryId}/questions`, payload);
  return data;
}

export async function updateEvaluationQuestion(questionId, payload) {
  const { data } = await apiClient.put(`/performance/forms/questions/${questionId}`, payload);
  return data;
}

export async function deleteEvaluationQuestion(questionId) {
  await apiClient.delete(`/performance/forms/questions/${questionId}`);
}
