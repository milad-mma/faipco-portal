// توابع API اتوماسیون اداری فاز ۲: قالب نامه و پیش‌نویس شخصی (بک‌اند: endpoints/automation_letters.py).
import { apiClient } from "./client";

// ---------- قالب‌ها (مجوز automation.templates) ----------

// { templates: [...], default_layouts: {A4, A5}, paper_mm: {A4: [210, 297], A5: [148, 210]} } — قالب برای همه یکسان
export async function fetchTemplates() {
  const { data } = await apiClient.get("/automation/templates");
  return data;
}

export async function saveTemplate(templateId, payload) {
  const { data } = templateId
    ? await apiClient.put(`/automation/templates/${templateId}`, payload)
    : await apiClient.post("/automation/templates", payload);
  return data;
}

export async function fetchTemplateVersions(templateId) {
  const { data } = await apiClient.get(`/automation/templates/${templateId}/versions`);
  return data;
}

export async function uploadTemplateLogo(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post("/automation/templates/logo", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 2 * 60 * 1000,
  });
  return data; // file_out: { id, original_name, ... }
}

// تصویر لوگو به‌صورت Blob (img معمولی توکن نمی‌فرستد)
export async function fetchLogoBlob(fileId) {
  const { data } = await apiClient.get(`/automation/templates/logo/${fileId}`, { responseType: "blob" });
  return data;
}

// ---------- پیش‌نویس (مجوز automation.compose) ----------

// { sites, templates: [{id, site_id, name, default_paper_size}], urgencies, confidentiality }
export async function fetchComposeOptions() {
  const { data } = await apiClient.get("/automation/compose/options");
  return data;
}

export async function fetchMyDrafts() {
  const { data } = await apiClient.get("/automation/drafts");
  return data;
}

export async function createDraft(payload) {
  const { data } = await apiClient.post("/automation/drafts", payload);
  return data;
}

export async function fetchDraft(id) {
  const { data } = await apiClient.get(`/automation/drafts/${id}`);
  return data;
}

export async function saveDraft(id, payload) {
  const { data } = await apiClient.put(`/automation/drafts/${id}`, payload);
  return data;
}

export async function discardDraft(id) {
  await apiClient.delete(`/automation/drafts/${id}`);
}

// ---------- فاز ۳الف: گیرنده، پیوست، ارسال، کارتابل، نامه ----------

// { people: [{employee_id, name, title, department}], departments: [{id, name, site}] } — بدون کد پرسنلی/ملی
export async function fetchPeople(params) {
  const { data } = await apiClient.get("/automation/people", { params });
  return data;
}

export async function saveDraftRecipients(id, items) {
  const { data } = await apiClient.put(`/automation/drafts/${id}/recipients`, { items });
  return data; // { recipients, attachments }
}

export async function uploadDraftAttachment(id, file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post(`/automation/drafts/${id}/attachments`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 10 * 60 * 1000,
    onUploadProgress: (e) => onProgress?.(e.total ? Math.round((e.loaded * 100) / e.total) : 0),
  });
  return data; // { attachments }
}

export async function removeDraftAttachment(id, attachmentId) {
  const { data } = await apiClient.delete(`/automation/drafts/${id}/attachments/${attachmentId}`);
  return data;
}

export async function sendDraft(id, rowVersion) {
  const { data } = await apiClient.post(`/automation/drafts/${id}/send`, { row_version: rowVersion });
  return data; // { letter_id }
}

export async function fetchCartable(box, q, page) {
  const { data } = await apiClient.get("/automation/cartable", { params: { box, q, page } });
  return data; // { items, total, page, page_size }
}

export async function fetchLetter(id) {
  const { data } = await apiClient.get(`/automation/letters/${id}`);
  return data;
}

export async function referLetter(id, payload) {
  const { data } = await apiClient.post(`/automation/letters/${id}/refer`, payload);
  return data;
}

export async function completeTask(taskId, note) {
  const { data } = await apiClient.post(`/automation/tasks/${taskId}/done`, { note });
  return data;
}

export async function addLetterNote(id, text) {
  const { data } = await apiClient.post(`/automation/letters/${id}/notes`, { text });
  return data;
}

export async function makeLetterConfidential(id, reason) {
  const { data } = await apiClient.post(`/automation/letters/${id}/make-confidential`, { reason });
  return data;
}

// دانلود پیوست (نامه‌ی ارسال‌شده یا پیش‌نویس خود کاربر) به‌صورت Blob
export async function downloadLetterAttachment({ letterId, attachmentId, draft = false }) {
  const base = draft ? "drafts" : "letters";
  const { data } = await apiClient.get(`/automation/${base}/${letterId}/attachments/${attachmentId}/download`, {
    responseType: "blob",
    timeout: 10 * 60 * 1000,
  });
  return data;
}

// ---------- فاز ۳الف بخش دوم: پاسخ/عطف/پیرو و تنظیمات اعلان ----------

// type: reply | reference | follow_up ؛ خروجی: { draft_id }
export async function createRelatedDraft(letterId, type) {
  const { data } = await apiClient.post(`/automation/letters/${letterId}/related-draft`, { type });
  return data;
}

// { events: [{ key, label, enabled }] }
export async function fetchNotificationPrefs() {
  const { data } = await apiClient.get("/automation/notification-prefs");
  return data;
}

export async function saveNotificationPrefs(enabled) {
  const { data } = await apiClient.put("/automation/notification-prefs", { enabled });
  return data;
}
