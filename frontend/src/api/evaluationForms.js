/**
 * توابع API مدیریت فرم‌های ارزیابی عملکرد (/performance/forms).
 * شامل CRUD فرم، تغییر وضعیت/عنوان، کپی فرم و مدیریت دسته‌ها و سؤال‌های فرم.
 */
import { apiClient } from "./client";

// GET /performance/forms با site_id؛ فهرست فرم‌های ارزیابی سایت را برمی‌گرداند
export async function fetchEvaluationForms(siteId) {
  const { data } = await apiClient.get("/performance/forms", { params: { site_id: siteId } });
  return data;
}

// GET /performance/forms/{id}؛ جزئیات کامل یک فرم (با دسته‌ها و سؤال‌ها) را برمی‌گرداند
export async function fetchEvaluationForm(formId) {
  const { data } = await apiClient.get(`/performance/forms/${formId}`);
  return data;
}

// POST /performance/forms؛ فرم جدید می‌سازد و فرم ایجادشده را برمی‌گرداند
export async function createEvaluationForm(payload) {
  const { data } = await apiClient.post("/performance/forms", payload);
  return data;
}

// PUT /performance/forms/{id}؛ اطلاعات فرم را ویرایش می‌کند و فرم به‌روزشده را برمی‌گرداند
export async function updateEvaluationForm(formId, payload) {
  const { data } = await apiClient.put(`/performance/forms/${formId}`, payload);
  return data;
}

// PUT /performance/forms/{id}/status؛ وضعیت فرم را تغییر می‌دهد و فرم به‌روزشده را برمی‌گرداند
export async function updateEvaluationFormStatus(formId, status) {
  const { data } = await apiClient.put(`/performance/forms/${formId}/status`, { status });
  return data;
}

// PUT /performance/forms/{id}/title؛ عنوان فرم را تغییر می‌دهد و فرم به‌روزشده را برمی‌گرداند
export async function updateEvaluationFormTitle(formId, title) {
  const { data } = await apiClient.put(`/performance/forms/${formId}/title`, { title });
  return data;
}

// POST /performance/forms/{id}/duplicate؛ یک کپی از فرم می‌سازد و فرم جدید را برمی‌گرداند
export async function duplicateEvaluationForm(formId) {
  const { data } = await apiClient.post(`/performance/forms/${formId}/duplicate`);
  return data;
}

// DELETE /performance/forms/{id}؛ فرم را حذف می‌کند (خروجی ندارد)
export async function deleteEvaluationForm(formId) {
  await apiClient.delete(`/performance/forms/${formId}`);
}

// POST /performance/forms/{id}/categories؛ دسته‌ی جدید به فرم اضافه می‌کند و دسته را برمی‌گرداند
export async function addEvaluationCategory(formId, payload) {
  const { data } = await apiClient.post(`/performance/forms/${formId}/categories`, payload);
  return data;
}

// PUT /performance/forms/categories/{id}؛ دسته را ویرایش می‌کند و دسته‌ی به‌روزشده را برمی‌گرداند
export async function updateEvaluationCategory(categoryId, payload) {
  const { data } = await apiClient.put(`/performance/forms/categories/${categoryId}`, payload);
  return data;
}

// DELETE /performance/forms/categories/{id}؛ دسته را حذف می‌کند (خروجی ندارد)
export async function deleteEvaluationCategory(categoryId) {
  await apiClient.delete(`/performance/forms/categories/${categoryId}`);
}

// POST /performance/forms/categories/{id}/questions؛ سؤال جدید به دسته اضافه می‌کند و سؤال را برمی‌گرداند
export async function addEvaluationQuestion(categoryId, payload) {
  const { data } = await apiClient.post(`/performance/forms/categories/${categoryId}/questions`, payload);
  return data;
}

// PUT /performance/forms/questions/{id}؛ سؤال را ویرایش می‌کند و سؤال به‌روزشده را برمی‌گرداند
export async function updateEvaluationQuestion(questionId, payload) {
  const { data } = await apiClient.put(`/performance/forms/questions/${questionId}`, payload);
  return data;
}

// DELETE /performance/forms/questions/{id}؛ سؤال را حذف می‌کند (خروجی ندارد)
export async function deleteEvaluationQuestion(questionId) {
  await apiClient.delete(`/performance/forms/questions/${questionId}`);
}
