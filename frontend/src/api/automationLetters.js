// توابع API اتوماسیون اداری فاز ۲: قالب نامه و پیش‌نویس شخصی (بک‌اند: endpoints/automation_letters.py).
import { apiClient } from "./client";

// ---------- قالب‌ها (مجوز automation.templates) ----------

// { sites: [{id, name}], templates: [...], default_layouts: {A4, A5}, paper_mm: {A4: [210, 297], A5: [148, 210]} }
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

export async function uploadTemplateLogo(siteId, file) {
  const formData = new FormData();
  formData.append("site_id", String(siteId));
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
