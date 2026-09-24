/**
 * توابع فراخوانی API پرسنل.
 * فهرست و شمارش پرسنل، ایجاد، فعال/غیرفعال‌سازی و رمز عبور، نقش‌ها و واحدهای تحت سرپرستی،
 * عکس‌ها، تولدهای امروز و پاک‌سازی پرسنل غیرفعالِ بی‌استفاده.
 */
import { apiClient } from "./client";

// GET /employees با فیلتر سایت/واحد/جستجو/نقش، صفحه‌بندی و مرتب‌سازی؛ خروجی: { items, total }
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
  // URLSearchParams تا department_id چندمقداری به صورت پارامترهای تکراری (department_id=1&department_id=2)
  // سریالایز شود؛ همان قالبی که FastAPI برای list[int] = Query(...) انتظار دارد
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

// POST /employees؛ ایجاد پرسنل جدید؛ خروجی: پرسنل ساخته‌شده
export async function createEmployee(payload) {
  const { data } = await apiClient.post("/employees", payload);
  return data;
}

// GET /employees/count (اختیاری به تفکیک سایت)؛ خروجی: تعداد پرسنل
export async function fetchEmployeeCount(siteId) {
  const { data } = await apiClient.get("/employees/count", {
    params: siteId ? { site_id: siteId } : {},
  });
  return data.count;
}

// GET /employees/portal-disabled-count؛ خروجی: تعداد پرسنلی که دسترسی پورتال‌شان غیرفعال است
export async function fetchPortalDisabledCount() {
  const { data } = await apiClient.get("/employees/portal-disabled-count");
  return data.count;
}

// GET /employees/birthdays-today (با گزینه‌ی رعایت حریم خصوصی)؛ خروجی: فهرست متولدین امروز
export async function fetchTodayBirthdays({ respectPrivacy = false } = {}) {
  const { data } = await apiClient.get("/employees/birthdays-today", {
    params: { respect_privacy: respectPrivacy || undefined },
  });
  return data;
}

// PATCH /employees/me/birthday-visibility؛ پنهان/نمایش تولد کاربر جاری در داشبورد؛ خروجی: نتیجه
export async function updateMyBirthdayVisibility(hideBirthdayInDashboard) {
  const { data } = await apiClient.patch("/employees/me/birthday-visibility", {
    hide_birthday_in_dashboard: hideBirthdayInDashboard,
  });
  return data;
}

// GET /employees/{id}/photo-thumbnail؛ خروجی: تصویر کوچک پرسنل به صورت Blob
export async function fetchEmployeePhotoThumbnailBlob(employeeId) {
  const { data } = await apiClient.get(`/employees/${employeeId}/photo-thumbnail`, {
    responseType: "blob",
  });
  return data; // Blob از نوع image/gif
}

// GET /employees/{id}/roles؛ خروجی: نقش‌های انتصاب‌یافته به پرسنل
export async function fetchEmployeeRoles(employeeId) {
  const { data } = await apiClient.get(`/employees/${employeeId}/roles`);
  return data;
}

// POST /employees/{id}/roles؛ انتصاب یک نقش در سایت‌های داده‌شده؛ خروجی: انتصاب‌های تازه ساخته‌شده
export async function assignRoleToEmployee(employeeId, roleId, siteIds) {
  const { data } = await apiClient.post(`/employees/${employeeId}/roles`, {
    role_id: roleId,
    site_ids: siteIds,
  });
  return data; // فهرست انتصاب‌های واقعاً تازه‌ساخته‌شده (سایت‌هایی که از قبل داشت، نادیده گرفته می‌شوند)
}

// GET /employees/{id}/supervised-departments؛ خروجی: شناسه‌ی واحدهای تحت سرپرستی
export async function fetchSupervisedDepartments(employeeId) {
  const { data } = await apiClient.get(`/employees/${employeeId}/supervised-departments`);
  return data; // آرایه‌ای از شناسه واحدهایی که این پرسنل سرپرست آن‌هاست
}

// PATCH /employees/{id}؛ فعال/غیرفعال کردن حساب پورتال پرسنل؛ خروجی: پرسنل به‌روزشده
export async function setEmployeeEnabled(employeeId, isEnabled) {
  const { data } = await apiClient.patch(`/employees/${employeeId}`, { is_enabled: isEnabled });
  return data;
}

// PUT /employees/{id}/password؛ تنظیم رمز جدید برای پرسنل توسط مدیر
export async function setEmployeePassword(employeeId, newPassword) {
  await apiClient.put(`/employees/${employeeId}/password`, { new_password: newPassword });
}

// DELETE /employees/{id}/password؛ حذف رمز تنظیم‌شده‌ی پرسنل (بازنشانی رمز)
export async function resetEmployeePassword(employeeId) {
  await apiClient.delete(`/employees/${employeeId}/password`);
}

// GET /employees/cleanup-orphaned-inactive/preview؛ خروجی: پرسنل غیرفعالی که قابل حذف‌اند
export async function previewOrphanedInactiveCleanup() {
  const { data } = await apiClient.get("/employees/cleanup-orphaned-inactive/preview");
  return data; // { count, items }
}

// POST /employees/cleanup-orphaned-inactive/execute با تأیید؛ حذف همان پرسنل؛ خروجی: تعداد حذف‌شده
export async function executeOrphanedInactiveCleanup() {
  const { data } = await apiClient.post("/employees/cleanup-orphaned-inactive/execute", null, {
    params: { confirm: true },
  });
  return data; // { deleted_count }
}

// POST /employees/birthdays/{id}/reaction؛ ثبت واکنش (ایموجی) روی کارت تولد؛ خروجی: نتیجه
export async function setBirthdayReaction(employeeId, emoji) {
  const { data } = await apiClient.post(`/employees/birthdays/${employeeId}/reaction`, { emoji });
  return data;
}

// GET /employees/birthday-photo/{id}؛ خروجی: عکس پرسنل برای آواتار کارت تولد به صورت Blob
export async function fetchBirthdayPhotoThumbnailBlob(employeeId) {
  // مسیر جدا از /photo-thumbnail (که فقط برای خود شخص یا Admin است)؛ این مسیر عکس را فقط
  // در زمینه‌ی تولد (متولد امروز یا تبریک‌گوینده) برای همه‌ی کاربران برمی‌گرداند
  const { data } = await apiClient.get(`/employees/birthday-photo/${employeeId}`, {
    responseType: "blob",
  });
  return data;
}
