/**
 * توابع فراخوانی API «دروازه‌ی دسترسی» (Access Gate).
 * وضعیت دسترسی کاربر جاری به قابلیت‌ها و خواندن/تغییر تنظیمات دروازه‌ها توسط مدیر.
 */
import { apiClient } from "./client";

// GET /access-gate/my-status؛ خروجی: وضعیت باز/بسته بودن قابلیت‌ها برای کاربر جاری
export async function fetchMyAccessGateStatus() {
  const { data } = await apiClient.get("/access-gate/my-status");
  return data;
}

// GET /access-gate/settings؛ خروجی: تنظیمات همه‌ی دروازه‌ها و قابلیت‌ها (مدیر)
export async function fetchAccessGateSettings() {
  const { data } = await apiClient.get("/access-gate/settings");
  return data;
}

// PUT /access-gate/settings؛ فعال/غیرفعال کردن یک قابلیت در یک دروازه؛ خروجی: تنظیم به‌روزشده
export async function updateAccessGateSetting(gate, feature, enabled) {
  const { data } = await apiClient.put("/access-gate/settings", { gate, feature, enabled });
  return data;
}
