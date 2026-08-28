import { apiClient } from "./client";

export async function fetchEmployees({
  siteId,
  departmentIds,
  search,
  includeInactive,
  includePortalDisabled,
  hasRole,
  page,
  pageSize,
  sortBy,
  sortDir,
} = {}) {
  // از URLSearchParams مستقیم استفاده می‌شود (به‌جای Object ساده) تا department_id
  // وقتی چند مقدار دارد، حتماً به‌صورت چندین پارامتر تکراری (department_id=1&department_id=2)
  // سریالایز شود — دقیقاً همان چیزی که FastAPI با list[int] = Query(...) انتظار دارد.
  const params = new URLSearchParams();
  if (siteId) params.append("site_id", siteId);
  if (departmentIds && departmentIds.length > 0) {
    departmentIds.forEach((id) => params.append("department_id", id));
  }
  if (search) params.append("search", search);
  if (includeInactive) params.append("include_inactive", "true");
  if (includePortalDisabled) params.append("include_portal_disabled", "true");
  if (hasRole) params.append("has_role", hasRole);
  if (page) params.append("page", page);
  if (pageSize) params.append("page_size", pageSize);
  if (sortBy) params.append("sort_by", sortBy);
  if (sortDir) params.append("sort_dir", sortDir);
  const { data } = await apiClient.get("/employees", { params });
  return data; // { items, total }
}

export async function createEmployee(payload) {
  const { data } = await apiClient.post("/employees", payload);
  return data;
}

export async function fetchEmployeeCount(siteId) {
  const { data } = await apiClient.get("/employees/count", {
    params: siteId ? { site_id: siteId } : {},
  });
  return data.count;
}

export async function fetchPortalDisabledCount() {
  const { data } = await apiClient.get("/employees/portal-disabled-count");
  return data.count;
}

export async function fetchTodayBirthdays({ respectPrivacy = false } = {}) {
  const { data } = await apiClient.get("/employees/birthdays-today", {
    params: { respect_privacy: respectPrivacy || undefined },
  });
  return data;
}

export async function updateMyBirthdayVisibility(hideBirthdayInDashboard) {
  const { data } = await apiClient.patch("/employees/me/birthday-visibility", {
    hide_birthday_in_dashboard: hideBirthdayInDashboard,
  });
  return data;
}

export async function fetchEmployeePhotoThumbnailBlob(employeeId) {
  const { data } = await apiClient.get(`/employees/${employeeId}/photo-thumbnail`, {
    responseType: "blob",
  });
  return data; // Blob از نوع image/gif
}

export async function fetchEmployeeRoles(employeeId) {
  const { data } = await apiClient.get(`/employees/${employeeId}/roles`);
  return data;
}

export async function assignRoleToEmployee(employeeId, roleId, siteIds) {
  const { data } = await apiClient.post(`/employees/${employeeId}/roles`, {
    role_id: roleId,
    site_ids: siteIds,
  });
  return data; // فهرست انتصاب‌های واقعاً تازه‌ساخته‌شده (سایت‌هایی که از قبل داشت، نادیده گرفته می‌شوند)
}

export async function fetchSupervisedDepartments(employeeId) {
  const { data } = await apiClient.get(`/employees/${employeeId}/supervised-departments`);
  return data; // آرایه‌ای از شناسه واحدهایی که این پرسنل سرپرست آن‌هاست
}

export async function setEmployeeEnabled(employeeId, isEnabled) {
  const { data } = await apiClient.patch(`/employees/${employeeId}`, { is_enabled: isEnabled });
  return data;
}

export async function setEmployeePassword(employeeId, newPassword) {
  await apiClient.put(`/employees/${employeeId}/password`, { new_password: newPassword });
}

export async function resetEmployeePassword(employeeId) {
  await apiClient.delete(`/employees/${employeeId}/password`);
}

export async function previewOrphanedInactiveCleanup() {
  const { data } = await apiClient.get("/employees/cleanup-orphaned-inactive/preview");
  return data; // { count, items }
}

export async function executeOrphanedInactiveCleanup() {
  const { data } = await apiClient.post("/employees/cleanup-orphaned-inactive/execute", null, {
    params: { confirm: true },
  });
  return data; // { deleted_count }
}
