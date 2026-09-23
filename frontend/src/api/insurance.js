import { apiClient } from "./client";

export const INSURANCE_DOCUMENT_URL = (id, inline = false) =>
  `${apiClient.defaults.baseURL}/insurance/documents/${id}${inline ? "?inline=true" : ""}`;

export async function fetchMyInsurance() {
  const { data } = await apiClient.get("/insurance/me");
  return data; // { enabled, employee, registration, rate_table, notes, bank_codes, account_types, member_types }
}

export async function saveMyInsurance(payload) {
  const { data } = await apiClient.put("/insurance/me", payload);
  return data;
}

export async function uploadInsuranceDocument(file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post("/insurance/me/documents", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => onProgress?.(e.total ? Math.round((e.loaded * 100) / e.total) : 0),
  });
  return data; // { id, file_name, content_type, size_bytes, uploaded_at }
}

export async function deleteMyInsuranceDocument(id) {
  await apiClient.delete(`/insurance/me/documents/${id}`);
}

export async function downloadInsuranceDocument(id) {
  const { data } = await apiClient.get(`/insurance/documents/${id}`, { responseType: "blob" });
  return data;
}

// ---------- مدیریت ----------

export async function fetchInsuranceSettings() {
  const { data } = await apiClient.get("/insurance/settings");
  return data; // { enabled, rate_table, notes }
}

export async function updateInsuranceSettings(payload) {
  const { data } = await apiClient.put("/insurance/settings", payload);
  return data;
}

export async function fetchInsuranceRegistrations(params = {}) {
  const { data } = await apiClient.get("/insurance/registrations", { params });
  return data; // { items, total, registered, eligible }
}

export async function fetchInsuranceRegistration(id) {
  const { data } = await apiClient.get(`/insurance/registrations/${id}`);
  return data;
}

export async function deleteInsuranceRegistration(id) {
  await apiClient.delete(`/insurance/registrations/${id}`);
}

export async function downloadInsuranceExport(siteId) {
  const { data } = await apiClient.get("/insurance/export", {
    params: siteId ? { site_id: siteId } : {},
    responseType: "blob",
  });
  return data;
}
