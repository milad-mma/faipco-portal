/**
 * توابع فراخوانی API کاربران، نقش‌ها و مجوزها.
 * فهرست و انتصاب نقش‌ها، نمای کلی دسترسی‌ها، کاتالوگ نقش‌ها (ایجاد/ویرایش/حذف) و انتصاب گروهی نقش.
 */
import { apiClient } from "./client";

// GET /users/roles؛ خروجی: فهرست نقش‌ها
export async function fetchRoles() {
  const { data } = await apiClient.get("/users/roles");
  return data;
}

// DELETE /users/roles/{id}؛ حذف یک انتصاب نقش
export async function removeRoleAssignment(userRoleId) {
  await apiClient.delete(`/users/roles/${userRoleId}`);
}

// GET /users/access-overview؛ خروجی: نمای کلی انتصاب نقش‌ها به پرسنل
// GET /users/site-transfers؛ جابه‌جایی‌های بین سایت‌ها که نقش‌هایشان بازبینی نشده (با نقش‌ها و سرپرستی‌های فعلی)
export async function fetchPendingSiteTransfers() {
  const { data } = await apiClient.get("/users/site-transfers");
  return data;
}

// POST /users/site-transfers/{id}/review؛ علامت «بازبینی‌شده» برای یک جابه‌جایی
export async function markSiteTransferReviewed(transferId) {
  await apiClient.post(`/users/site-transfers/${transferId}/review`);
}

export async function fetchAccessOverview() {
  const { data } = await apiClient.get("/users/access-overview");
  return data;
}

// GET /users/permissions؛ خروجی: فهرست همه‌ی مجوزهای قابل تخصیص
export async function fetchPermissions() {
  const { data } = await apiClient.get("/users/permissions");
  return data;
}

// GET /users/role-catalog/{id}؛ خروجی: جزئیات نقش و مجوزهای آن
export async function fetchRoleDetail(roleId) {
  const { data } = await apiClient.get(`/users/role-catalog/${roleId}`);
  return data;
}

// POST /users/role-catalog؛ ایجاد نقش جدید؛ خروجی: نقش ساخته‌شده
export async function createRole(payload) {
  const { data } = await apiClient.post("/users/role-catalog", payload);
  return data;
}

// PATCH /users/role-catalog/{id}؛ ویرایش نقش؛ خروجی: نقش به‌روزشده
export async function updateRole(roleId, payload) {
  const { data } = await apiClient.patch(`/users/role-catalog/${roleId}`, payload);
  return data;
}

// DELETE /users/role-catalog/{id}؛ حذف نقش
export async function deleteRole(roleId) {
  await apiClient.delete(`/users/role-catalog/${roleId}`);
}

// POST /users/bulk-assign-role؛ انتصاب گروهی نقش به پرسنل انتخابی یا همه‌ی پرسنل یک سایت/واحد؛ خروجی: آمار انتصاب
export async function bulkAssignRole({ roleId, employeeIds, siteId, departmentId }) {
  const { data } = await apiClient.post("/users/bulk-assign-role", {
    role_id: roleId,
    employee_ids: employeeIds || undefined,
    site_id: siteId || undefined,
    department_id: departmentId || undefined,
  });
  return data; // { assigned_count, already_had_count, not_found_count, total_matched }
}
