/**
 * API اپ اندروید: وضعیت کاربر جاری، کد اتصال، و پنل مدیریت گوشی‌ها، رویدادها، معافیت‌ها، تنظیمات و APK.
 */
import { apiClient } from "./client";

// GET /mobile/me؛ خروجی: { required, exempt, healthy, devices, latest_release, permission_issues }
export async function fetchMyMobileStatus() {
  const { data } = await apiClient.get("/mobile/me");
  return data;
}

// POST /mobile/pairing-code؛ خروجی: { code, expires_in }
// POST /mobile/link؛ اتصال خودکار این گوشی (کد ساخته‌شده توسط اپ) به حساب کاربر واردشده
export async function linkDevice(link) {
  const { data } = await apiClient.post("/mobile/link", { link });
  return data;
}

export async function createPairingCode() {
  const { data } = await apiClient.post("/mobile/pairing-code");
  return data;
}

// GET /mobile/app/latest؛ خروجی: آخرین نسخه یا null
export async function fetchLatestRelease() {
  const { data } = await apiClient.get("/mobile/app/latest");
  return data;
}

export const APK_DOWNLOAD_PATH = "/api/v1/mobile/app/download";

// ---------- پنل

export async function fetchMobileSummary(siteId) {
  const { data } = await apiClient.get("/mobile/summary", { params: siteId ? { site_id: siteId } : {} });
  return data;
}

export async function fetchMobileDevices({ siteId, search, health, includeRevoked } = {}) {
  const params = {};
  if (siteId) params.site_id = siteId;
  if (search) params.search = search;
  if (health) params.health = health;
  if (includeRevoked) params.include_revoked = true;
  const { data } = await apiClient.get("/mobile/devices", { params });
  return data;
}

export async function fetchMobileLabels() {
  const { data } = await apiClient.get("/mobile/issue-labels");
  return data;
}

export async function revokeMobileDevice(id) {
  await apiClient.post(`/mobile/devices/${id}/revoke`);
}

export async function fetchExemptions() {
  const { data } = await apiClient.get("/mobile/exemptions");
  return data;
}

export async function addExemption(employeeId, reason) {
  await apiClient.post("/mobile/exemptions", { employee_id: employeeId, reason: reason || null });
}

export async function deleteExemption(id) {
  await apiClient.delete(`/mobile/exemptions/${id}`);
}

export async function fetchGeofenceEvents({ siteId, status, search, hours = 168, limit = 50, offset = 0 } = {}) {
  const params = { hours, limit, offset };
  if (siteId) params.site_id = siteId;
  if (status) params.status = status;
  if (search) params.search = search;
  const { data } = await apiClient.get("/mobile/geofence-events", { params });
  return data;
}

export async function fetchMobileSettings() {
  const { data } = await apiClient.get("/mobile/settings");
  return data;
}

export async function saveMobileSettings(settings) {
  const { data } = await apiClient.put("/mobile/settings", settings);
  return data;
}

export async function fetchReleases() {
  const { data } = await apiClient.get("/mobile/app/releases");
  return data;
}

export async function uploadRelease({ file, versionCode, versionName, notes }, onProgress) {
  const form = new FormData();
  form.append("file", file);
  form.append("version_code", String(versionCode));
  form.append("version_name", versionName);
  if (notes) form.append("notes", notes);
  const { data } = await apiClient.post("/mobile/app/releases", form, {
    timeout: 300000,
    onUploadProgress: (e) => onProgress?.(e.total ? Math.round((e.loaded / e.total) * 100) : 0),
  });
  return data;
}

export async function deleteRelease(id) {
  await apiClient.delete(`/mobile/app/releases/${id}`);
}

// GET/PUT /system/mobile-app-feature؛ کلید اصلی قابلیت اپ اندروید (مجوز system.settings)
export async function fetchMobileAppFeature() {
  const { data } = await apiClient.get("/system/mobile-app-feature");
  return data;
}

export async function saveMobileAppFeature(enabled) {
  const { data } = await apiClient.put("/system/mobile-app-feature", { enabled });
  return data;
}
