/**
 * توابع API مدیریت دوره‌های ارزیابی عملکرد (/performance/periods).
 * شامل CRUD دوره، تغییر وضعیت/عنوان، غیرفعال‌سازی و مدیریت ارزیابی‌های منتشرشده‌ی هر دوره.
 */
import { apiClient } from "./client";

// GET /performance/periods با site_id؛ فهرست دوره‌های ارزیابی سایت را برمی‌گرداند
export async function fetchEvaluationPeriods(siteId) {
  const { data } = await apiClient.get("/performance/periods", { params: { site_id: siteId } });
  return data;
}

// POST /performance/periods؛ دوره‌ی جدید می‌سازد و دوره‌ی ایجادشده را برمی‌گرداند
export async function createEvaluationPeriod(payload) {
  const { data } = await apiClient.post("/performance/periods", payload);
  return data;
}

// PUT /performance/periods/{id}؛ اطلاعات دوره را ویرایش می‌کند و دوره‌ی به‌روزشده را برمی‌گرداند
export async function updateEvaluationPeriod(periodId, payload) {
  const { data } = await apiClient.put(`/performance/periods/${periodId}`, payload);
  return data;
}

// PUT /performance/periods/{id}/status؛ وضعیت دوره را تغییر می‌دهد و دوره‌ی به‌روزشده را برمی‌گرداند
export async function updateEvaluationPeriodStatus(periodId, status) {
  const { data } = await apiClient.put(`/performance/periods/${periodId}/status`, { status });
  return data;
}

// PUT /performance/periods/{id}/title؛ عنوان دوره را تغییر می‌دهد و دوره‌ی به‌روزشده را برمی‌گرداند
export async function updateEvaluationPeriodTitle(periodId, title) {
  const { data } = await apiClient.put(`/performance/periods/${periodId}/title`, { title });
  return data;
}

// DELETE /performance/periods/{id}؛ دوره را حذف می‌کند (خروجی ندارد)
// confirmTitle: برای دوره‌ای که ارزیابی منتشرشده دارد، عنوان دقیق دوره (تأیید حذف قطعی)
export async function deleteEvaluationPeriod(periodId, confirmTitle) {
  await apiClient.delete(`/performance/periods/${periodId}`, {
    params: confirmTitle ? { confirm_title: confirmTitle } : undefined,
  });
}

// PUT /performance/periods/{id}/disabled؛ دوره را فعال/غیرفعال می‌کند و دوره‌ی به‌روزشده را برمی‌گرداند
export async function setEvaluationPeriodDisabled(periodId, isDisabled) {
  const { data } = await apiClient.put(`/performance/periods/${periodId}/disabled`, { is_disabled: isDisabled });
  return data;
}

// GET /performance/periods/{id}/assignments؛ فهرست ارزیابی‌های منتشرشده‌ی دوره را برمی‌گرداند
export async function fetchPublishedEvaluations(periodId) {
  const { data } = await apiClient.get(`/performance/periods/${periodId}/assignments`);
  return data;
}

// DELETE /performance/periods/{id}/assignments/{assignmentId}؛ یک ارزیابی منتشرشده را حذف می‌کند
export async function deletePublishedEvaluation(periodId, assignmentId) {
  await apiClient.delete(`/performance/periods/${periodId}/assignments/${assignmentId}`);
}
