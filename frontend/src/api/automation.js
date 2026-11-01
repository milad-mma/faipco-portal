// توابع API اتوماسیون اداری (پیشوند /automation در بک‌اند) — فاز ۱: تنظیمات پیوست، وضعیت اسکنر و آزمایش آپلود.
import { apiClient } from "./client";

// { catalog: {formats, forbidden_label, server_max_file_mb, defaults, ...}, sites: [{site_id, site_name, is_default, values}] }
export async function fetchAttachmentSettings() {
  const { data } = await apiClient.get("/automation/settings/attachments");
  return data;
}

export async function saveAttachmentSettings(siteId, values) {
  const { data } = await apiClient.put(`/automation/settings/attachments/${siteId}`, values);
  return data;
}

// { scanner: {available, engine, db, db_date, db_stale, error}, disk: {total, used, free}, counts, storage_dir }
export async function fetchAutomationStatus() {
  const { data } = await apiClient.get("/automation/settings/status");
  return data;
}

export async function testUpload(siteId, file, onProgress) {
  const formData = new FormData();
  formData.append("site_id", String(siteId));
  formData.append("file", file);
  const { data } = await apiClient.post("/automation/files/test-upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 5 * 60 * 1000,
    onUploadProgress: (e) => onProgress?.(e.total ? Math.round((e.loaded * 100) / e.total) : 0),
  });
  return data;
}

export async function fetchMyFiles(siteId) {
  const { data } = await apiClient.get("/automation/files/mine", { params: siteId ? { site_id: siteId } : {} });
  return data;
}

export async function downloadFile(fileId) {
  const response = await apiClient.get(`/automation/files/${fileId}/download`, { responseType: "blob", timeout: 5 * 60 * 1000 });
  return response;
}

export async function deleteFile(fileId) {
  await apiClient.delete(`/automation/files/${fileId}`);
}

// روشن/خاموش اسکن ویروس (فقط ادمین کل؛ روشن کردن فقط وقتی ClamAV پاسخ می‌دهد)
export async function setScanEnabled(enabled) {
  const { data } = await apiClient.put("/automation/settings/scan", { enabled });
  return data;
}

// action: install | update-db | start | stop — اجرا در پس‌زمینه روی سرور؛ پیشرفت در status.clamav_job
export async function runClamavAction(action) {
  const { data } = await apiClient.post(`/automation/clamav/${action}`);
  return data;
}
