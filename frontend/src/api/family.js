// توابع فراخوانی API ماژول «مشخصات خانوادگی» (پیشوند /family در بک‌اند).
import { apiClient } from "./client";

// ---------- پرسنل ----------

// فرم + پرونده‌ی جاری + تنظیمات فیلدها/مدارک: { enabled, can_edit, lock_reason, employee, profile, form }
export async function fetchMyFamily() {
  const { data } = await apiClient.get("/family/me");
  return data;
}

// ثبت/ویرایش فرم (جایگزینی کامل)؛ خروجی پرونده‌ی ذخیره‌شده
export async function saveMyFamily(payload) {
  const { data } = await apiClient.put("/family/me", payload);
  return data;
}

// آپلود یک مدرک از نوع docType؛ onProgress با درصد پیشرفت صدا زده می‌شود
export async function uploadFamilyDocument(file, docType, onProgress) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("doc_type", docType);
  const { data } = await apiClient.post("/family/me/documents", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 3 * 60 * 1000,
    onUploadProgress: (e) => onProgress?.(e.total ? Math.round((e.loaded * 100) / e.total) : 0),
  });
  return data;
}

// حذف مدرکی که هنوز در فرم ثبت نشده
export async function deleteMyFamilyDocument(id) {
  await apiClient.delete(`/family/me/documents/${id}`);
}

// محتوای مدرک به‌صورت Blob (صاحب مدرک یا دارنده‌ی family.view)
export async function downloadFamilyDocument(id) {
  const { data } = await apiClient.get(`/family/documents/${id}`, { responseType: "blob" });
  return data;
}

// ---------- منابع انسانی ----------

// { settings, meta }
export async function fetchFamilySettings() {
  const { data } = await apiClient.get("/family/settings");
  return data;
}

export async function updateFamilySettings(payload) {
  const { data } = await apiClient.put("/family/settings", payload);
  return data;
}

// پارامترها: search, site_id, status_filter, flag, as_of, page, page_size → { items, total, stats }
export async function fetchFamilyProfiles(params = {}) {
  const { data } = await apiClient.get("/family/profiles", { params });
  return data;
}

export async function fetchFamilyProfile(id, asOf) {
  const { data } = await apiClient.get(`/family/profiles/${id}`, { params: asOf ? { as_of: asOf } : {} });
  return data;
}

export async function approveFamilyProfile(id, payload) {
  const { data } = await apiClient.post(`/family/profiles/${id}/approve`, payload);
  return data;
}

export async function rejectFamilyProfile(id, note) {
  const { data } = await apiClient.post(`/family/profiles/${id}/reject`, { note });
  return data;
}

export async function returnFamilyProfile(id, note) {
  const { data } = await apiClient.post(`/family/profiles/${id}/return`, { note });
  return data;
}

// سابقه بیمه (روز) و یادداشت داخلی؛ payload: { insurance_days?, clear_insurance_days?, hr_note? }
export async function updateFamilyHrFields(employeeId, payload) {
  const { data } = await apiClient.put(`/family/employees/${employeeId}/hr-fields`, payload);
  return data;
}

// ورود گروهی سابقه بیمه از Excel؛ mode: prior (پیش از استخدام) | total (کل سابقه) → { updated, not_found, invalid, ambiguous }
export async function importFamilyInsuranceDays(file, mode, siteId) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("mode", mode);
  if (siteId) formData.append("site_id", siteId);
  const { data } = await apiClient.post("/family/insurance-days/import", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 2 * 60 * 1000,
  });
  return data;
}

export async function downloadFamilyExport(params = {}) {
  const { data } = await apiClient.get("/family/export", { params, responseType: "blob" });
  return data;
}
