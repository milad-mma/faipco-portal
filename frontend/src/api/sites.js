/**
 * توابع فراخوانی API سایت‌ها.
 * فهرست و مدیریت سایت‌ها، موقعیت GPS، تنظیمات اتصال به دیتابیس سایت، کشف ساختار جداول،
 * نگاشت ستون‌های پرسنل و حضور و پیشنهاد خودکار نگاشت ستون‌ها.
 */
import { apiClient } from "./client";

// GET /sites؛ خروجی: همه‌ی سایت‌های سیستم
export async function fetchSites() {
  const { data } = await apiClient.get("/sites");
  return data;
}

/**
 * GET /sites/my-accessible؛ سایت‌هایی که کاربر جاری برای Permission Code داده‌شده به آن‌ها دسترسی دارد
 * (برای فیلتر «سایت» در صفحات گزارش). خروجی: { unrestricted, sites }
 * اگر unrestricted درست باشد (Admin یا انتصاب سراسری)، باید از fetchSites (همه‌ی سایت‌ها) استفاده کرد.
 */
export async function fetchMyAccessibleSites(permission) {
  const { data } = await apiClient.get("/sites/my-accessible", { params: { permission } });
  return data;
}

// POST /sites؛ ایجاد سایت؛ خروجی: سایت ساخته‌شده
export async function createSite(payload) {
  const { data } = await apiClient.post("/sites", payload);
  return data;
}

// PATCH /sites/{id}؛ فعال/غیرفعال کردن سایت؛ خروجی: سایت به‌روزشده
export async function setSiteActive(siteId, isActive) {
  const { data } = await apiClient.patch(`/sites/${siteId}`, { is_active: isActive });
  return data;
}

// DELETE /sites/{id}؛ حذف سایت
export async function deleteSite(siteId) {
  await apiClient.delete(`/sites/${siteId}`);
}

// PUT /sites/{id}/gps؛ ذخیره‌ی مختصات و شعاع مجاز حضور سایت؛ خروجی: سایت به‌روزشده
export async function updateSiteGpsLocation(siteId, { gps_latitude, gps_longitude, gps_radius_meters }) {
  const { data } = await apiClient.put(`/sites/${siteId}/gps`, {
    gps_latitude,
    gps_longitude,
    gps_radius_meters,
  });
  return data;
}

// GET /sites/{id}/connection؛ خروجی: تنظیمات اتصال دیتابیس سایت
export async function fetchSiteConnection(siteId) {
  const { data } = await apiClient.get(`/sites/${siteId}/connection`);
  return data; // null اگر تعریف نشده باشد
}

// GET /sites/{id}/discover-schema؛ خروجی: جداول و ستون‌های دیتابیس سایت
export async function discoverSiteSchema(siteId) {
  const { data } = await apiClient.get(`/sites/${siteId}/discover-schema`, { timeout: 30000 });
  return data;
}

// PUT /sites/{id}/connection؛ ایجاد یا ویرایش تنظیمات اتصال؛ خروجی: اتصال ذخیره‌شده
export async function upsertSiteConnection(siteId, payload) {
  const { data } = await apiClient.put(`/sites/${siteId}/connection`, payload);
  return data;
}

// DELETE /sites/{id}/connection؛ حذف تنظیمات اتصال سایت
export async function deleteSiteConnection(siteId) {
  await apiClient.delete(`/sites/${siteId}/connection`);
}

// PATCH /sites/{id}/connection/status؛ فعال/غیرفعال کردن اتصال؛ خروجی: اتصال به‌روزشده
export async function setSiteConnectionActive(siteId, isActive) {
  const { data } = await apiClient.patch(`/sites/${siteId}/connection/status`, { is_active: isActive });
  return data;
}

// GET /sites/{id}/mapping؛ خروجی: نگاشت ستون‌های جدول پرسنل سایت
export async function fetchSiteMapping(siteId) {
  const { data } = await apiClient.get(`/sites/${siteId}/mapping`);
  return data; // null اگر تعریف نشده باشد
}

// PUT /sites/{id}/mapping؛ ایجاد یا ویرایش نگاشت پرسنل؛ خروجی: نگاشت ذخیره‌شده
export async function upsertSiteMapping(siteId, payload) {
  const { data } = await apiClient.put(`/sites/${siteId}/mapping`, payload);
  return data;
}

// POST /sites/{id}/mapping/org-preview؛ پیش‌نمایش فیلتر واحد ریشه با نگاشت فرم (بدون ذخیره)؛
// خروجی: { units, sites, unassigned_active_employees, error }
export async function previewSiteOrgFilter(siteId, payload) {
  const { data } = await apiClient.post(`/sites/${siteId}/mapping/org-preview`, payload);
  return data;
}

// DELETE /sites/{id}/mapping؛ حذف نگاشت پرسنل
export async function deleteSiteMapping(siteId) {
  await apiClient.delete(`/sites/${siteId}/mapping`);
}

// GET /sites/{id}/attendance-mapping؛ خروجی: نگاشت ستون‌های جدول تردد سایت
export async function fetchSiteAttendanceMapping(siteId) {
  const { data } = await apiClient.get(`/sites/${siteId}/attendance-mapping`);
  return data; // null اگر تعریف نشده باشد
}

// PUT /sites/{id}/attendance-mapping؛ ایجاد یا ویرایش نگاشت تردد؛ خروجی: نگاشت ذخیره‌شده
export async function upsertSiteAttendanceMapping(siteId, payload) {
  const { data } = await apiClient.put(`/sites/${siteId}/attendance-mapping`, payload);
  return data;
}

// DELETE /sites/{id}/attendance-mapping؛ حذف نگاشت تردد
export async function deleteSiteAttendanceMapping(siteId) {
  await apiClient.delete(`/sites/${siteId}/attendance-mapping`);
}

// POST /mapping-suggestions؛ پیشنهاد تطبیق ستون‌ها با مفاهیم؛ خروجی: نگاشت پیشنهادی
export async function suggestColumnMapping(columns, concepts) {
  const { data } = await apiClient.post("/mapping-suggestions", { columns, concepts });
  return data;
}

// POST /sites/{id}/suggest-mapping؛ پیشنهاد نگاشت برای یک جدول سایت؛ خروجی: نگاشت پیشنهادی
export async function suggestMappingForSite(siteId, tableName, columns, concepts) {
  const { data } = await apiClient.post(`/sites/${siteId}/suggest-mapping`, {
    table_name: tableName,
    columns,
    concepts,
  });
  return data;
}
