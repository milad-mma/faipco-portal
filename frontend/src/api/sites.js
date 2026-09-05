import { apiClient } from "./client";

export async function fetchSites() {
  const { data } = await apiClient.get("/sites");
  return data;
}

/**
 * برای فیلترهای «سایت» در صفحات گزارش‌گیری — به‌جای fetchSites (که همه
 * سایت‌های سیستم را برمی‌گرداند، صرف‌نظر از دسترسی واقعی کاربر)، فقط
 * سایت‌هایی که کاربر جاری واقعاً برای این Permission Code دسترسی دارد.
 * { unrestricted, sites } — اگر unrestricted بود، یعنی Admin/انتصاب
 * سراسری است؛ در آن حالت باید از fetchSites معمولی (همه سایت‌ها) استفاده کرد.
 */
export async function fetchMyAccessibleSites(permission) {
  const { data } = await apiClient.get("/sites/my-accessible", { params: { permission } });
  return data;
}

export async function createSite(payload) {
  const { data } = await apiClient.post("/sites", payload);
  return data;
}

export async function setSiteActive(siteId, isActive) {
  const { data } = await apiClient.patch(`/sites/${siteId}`, { is_active: isActive });
  return data;
}

export async function deleteSite(siteId) {
  await apiClient.delete(`/sites/${siteId}`);
}

export async function updateSiteGpsLocation(siteId, { gps_latitude, gps_longitude, gps_radius_meters }) {
  const { data } = await apiClient.put(`/sites/${siteId}/gps`, {
    gps_latitude,
    gps_longitude,
    gps_radius_meters,
  });
  return data;
}

export async function fetchSiteConnection(siteId) {
  const { data } = await apiClient.get(`/sites/${siteId}/connection`);
  return data; // null اگر تعریف نشده باشد
}

export async function discoverSiteSchema(siteId) {
  const { data } = await apiClient.get(`/sites/${siteId}/discover-schema`, { timeout: 30000 });
  return data;
}

export async function upsertSiteConnection(siteId, payload) {
  const { data } = await apiClient.put(`/sites/${siteId}/connection`, payload);
  return data;
}

export async function deleteSiteConnection(siteId) {
  await apiClient.delete(`/sites/${siteId}/connection`);
}

export async function setSiteConnectionActive(siteId, isActive) {
  const { data } = await apiClient.patch(`/sites/${siteId}/connection/status`, { is_active: isActive });
  return data;
}

export async function fetchSiteMapping(siteId) {
  const { data } = await apiClient.get(`/sites/${siteId}/mapping`);
  return data; // null اگر تعریف نشده باشد
}

export async function upsertSiteMapping(siteId, payload) {
  const { data } = await apiClient.put(`/sites/${siteId}/mapping`, payload);
  return data;
}

export async function deleteSiteMapping(siteId) {
  await apiClient.delete(`/sites/${siteId}/mapping`);
}

export async function fetchSiteAttendanceMapping(siteId) {
  const { data } = await apiClient.get(`/sites/${siteId}/attendance-mapping`);
  return data; // null اگر تعریف نشده باشد
}

export async function upsertSiteAttendanceMapping(siteId, payload) {
  const { data } = await apiClient.put(`/sites/${siteId}/attendance-mapping`, payload);
  return data;
}

export async function deleteSiteAttendanceMapping(siteId) {
  await apiClient.delete(`/sites/${siteId}/attendance-mapping`);
}

export async function suggestColumnMapping(columns, concepts) {
  const { data } = await apiClient.post("/mapping-suggestions", { columns, concepts });
  return data;
}

export async function suggestMappingForSite(siteId, tableName, columns, concepts) {
  const { data } = await apiClient.post(`/sites/${siteId}/suggest-mapping`, {
    table_name: tableName,
    columns,
    concepts,
  });
  return data;
}
