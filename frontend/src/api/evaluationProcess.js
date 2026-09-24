/**
 * توابع API فرایند انجام ارزیابی عملکرد: تولید تخصیص‌ها، شروع/ذخیره/ارسال/بازگشایی ارزیابی
 * و دریافت ارزیابی‌ها و نتایج کاربر جاری (ارزیاب یا ارزیابی‌شونده).
 */
import { apiClient } from "./client";

// POST /performance/periods/{id}/generate-assignments با form_id؛ تخصیص‌های ارزیابی دوره را تولید و نتیجه را برمی‌گرداند
export async function generateEvaluationAssignments(periodId, formId) {
  const { data } = await apiClient.post(`/performance/periods/${periodId}/generate-assignments`, {
    form_id: formId,
  });
  return data;
}

// GET /performance/my-evaluations؛ ارزیابی‌هایی که کاربر جاری باید انجام دهد را برمی‌گرداند
export async function fetchMyEvaluations() {
  const { data } = await apiClient.get("/performance/my-evaluations");
  return data;
}

// GET /performance/my-shift-lead-evaluations؛ ارزیابی‌های کاربر جاری در نقش سرشیفت را برمی‌گرداند
export async function fetchMyShiftLeadEvaluations() {
  const { data } = await apiClient.get("/performance/my-shift-lead-evaluations");
  return data;
}

// GET /performance/evaluations/{id}؛ جزئیات یک ارزیابی (فرم و پاسخ‌ها) را برمی‌گرداند
export async function fetchEvaluationById(evaluationId) {
  const { data } = await apiClient.get(`/performance/evaluations/${evaluationId}`);
  return data;
}

// POST /performance/assignments/{id}/start؛ ارزیابی را برای یک تخصیص شروع می‌کند و رکورد ارزیابی را برمی‌گرداند
export async function startEvaluation(assignmentId) {
  const { data } = await apiClient.post(`/performance/assignments/${assignmentId}/start`);
  return data;
}

// PUT /performance/evaluations/{id}/answers؛ پاسخ‌ها را ذخیره (پیش‌نویس) می‌کند و ارزیابی به‌روزشده را برمی‌گرداند
export async function saveEvaluationAnswers(evaluationId, answers) {
  const { data } = await apiClient.put(`/performance/evaluations/${evaluationId}/answers`, { answers });
  return data;
}

// POST /performance/evaluations/{id}/submit؛ ارزیابی را ارسال نهایی می‌کند و نتیجه را برمی‌گرداند
export async function submitEvaluation(evaluationId) {
  const { data } = await apiClient.post(`/performance/evaluations/${evaluationId}/submit`);
  return data;
}

// GET /performance/my-results؛ نتایج ارزیابی‌های کاربر جاری (به‌عنوان ارزیابی‌شونده) را برمی‌گرداند
export async function fetchMyEvaluationResults() {
  const { data } = await apiClient.get("/performance/my-results");
  return data;
}

// GET /performance/my-results/{id}/answers؛ پاسخ‌های یک نتیجه‌ی ارزیابی کاربر جاری را برمی‌گرداند
export async function fetchMyEvaluationResultAnswers(evaluationId) {
  const { data } = await apiClient.get(`/performance/my-results/${evaluationId}/answers`);
  return data;
}

// POST /performance/evaluations/{id}/reopen؛ ارزیابی ارسال‌شده را برای ویرایش دوباره باز می‌کند
export async function reopenEvaluation(evaluationId) {
  const { data } = await apiClient.post(`/performance/evaluations/${evaluationId}/reopen`);
  return data;
}

// GET /performance/my-yearly-average (jalali_year اختیاری)؛ میانگین سالانه‌ی امتیاز کاربر جاری را برمی‌گرداند
export async function fetchMyYearlyAverage(jalaliYear) {
  const { data } = await apiClient.get("/performance/my-yearly-average", {
    params: jalaliYear ? { jalali_year: jalaliYear } : {},
  });
  return data;
}

// GET /performance/my-dashboard-summary؛ خلاصه‌ی داشبورد (تعداد نتایج و ارزیابی‌های در انتظار) را برمی‌گرداند
export async function fetchMyEvaluationDashboardSummary() {
  const { data } = await apiClient.get("/performance/my-dashboard-summary");
  return data;
}
