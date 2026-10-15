/**
 * API «امنیت ورود» (مجوز system.login_security): تنظیمات، قفل‌های فعال، رفع قفل، گزارش رویدادها و خلاصه.
 */
import { apiClient } from "./client";

// GET /login-security/settings؛ خروجی: تنظیمات فعلی
export async function fetchLoginSecuritySettings() {
  const { data } = await apiClient.get("/login-security/settings");
  return data;
}

// PUT /login-security/settings؛ ذخیره‌ی تنظیمات؛ خروجی: تنظیمات ذخیره‌شده
export async function saveLoginSecuritySettings(settings) {
  const { data } = await apiClient.put("/login-security/settings", settings);
  return data;
}

// GET /login-security/locks؛ خروجی: [{ key, kind, value, fail_count, locked_until }]
export async function fetchActiveLocks() {
  const { data } = await apiClient.get("/login-security/locks");
  return data;
}

// POST /login-security/unlock؛ رفع یک قفل با key
export async function unlockKey(key) {
  await apiClient.post("/login-security/unlock", { key });
}

// GET /login-security/events؛ خروجی: { items, total, labels }
export async function fetchSecurityEvents({
  kind,
  search,
  hours = 24,
  limit = 50,
  offset = 0,
} = {}) {
  const params = { hours, limit, offset };
  if (kind) params.kind = kind;
  if (search) params.search = search;
  const { data } = await apiClient.get("/login-security/events", { params });
  return data;
}

// GET /login-security/sessions؛ نشست‌های (دستگاه‌های) همه‌ی کاربران؛ خروجی: { items, total }
// هر item: { id, user_id, username, employee, device, client_app, ip, created_at, last_seen_at,
// revoked_at, revoked_reason, max_sessions }
export async function fetchSessions({
  search,
  onlyActive = true,
  page = 0,
  pageSize = 20,
} = {}) {
  const params = {
    only_active: onlyActive,
    page: page + 1,
    page_size: pageSize,
  };
  if (search) params.search = search;
  const { data } = await apiClient.get("/login-security/sessions", { params });
  return data;
}

// DELETE /login-security/sessions/{id}؛ خروج اجباری یک نشست توسط ادمین (204)
export async function revokeSession(id) {
  await apiClient.delete(`/login-security/sessions/${id}`);
}

// PUT /login-security/users/{user_id}/max-sessions؛ سقف اختصاصی دستگاه‌های هم‌زمان یک کاربر
// (1..3؛ null = پیش‌فرض تنظیمات)
export async function setUserMaxSessions(userId, maxSessions) {
  await apiClient.put(`/login-security/users/${userId}/max-sessions`, {
    max_sessions: maxSessions,
  });
}

// GET /login-security/summary؛ خروجی: شمارش‌ها، پرتکرارترین IPها/شناسه‌ها و قفل‌های فعال
export async function fetchSecuritySummary(hours = 24) {
  const { data } = await apiClient.get("/login-security/summary", {
    params: { hours },
  });
  return data;
}
