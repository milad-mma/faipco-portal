/**
 * توابع فراخوانی API خودروهای پرسنل.
 * مدیریت خودروهای کاربر جاری و گزارش/ویرایش/حذف همه‌ی خودروها توسط مدیر.
 */
import { apiClient } from "./client";

// GET /vehicles/me؛ خروجی: خودروهای ثبت‌شده‌ی کاربر جاری
export async function fetchMyVehicles() {
  const { data } = await apiClient.get("/vehicles/me");
  return data;
}

// POST /vehicles/me؛ ثبت خودرو برای کاربر جاری؛ خروجی: خودروی ساخته‌شده
export async function createMyVehicle(payload) {
  const { data } = await apiClient.post("/vehicles/me", payload);
  return data;
}

// DELETE /vehicles/me/{id}؛ حذف خودروی کاربر جاری
export async function deleteMyVehicle(vehicleId) {
  await apiClient.delete(`/vehicles/me/${vehicleId}`);
}

// GET /vehicles (اختیاری به تفکیک سایت)؛ خروجی: همه‌ی خودروهای پرسنل
export async function fetchAllVehicles(siteId) {
  const { data } = await apiClient.get("/vehicles", { params: siteId ? { site_id: siteId } : {} });
  return data;
}

// PATCH /vehicles/{id}؛ ویرایش خودرو توسط مدیر؛ خروجی: خودروی به‌روزشده
export async function updateVehicleAdmin(vehicleId, payload) {
  const { data } = await apiClient.patch(`/vehicles/${vehicleId}`, payload);
  return data;
}

// DELETE /vehicles/{id}؛ حذف خودرو توسط مدیر
export async function deleteVehicleAdmin(vehicleId) {
  await apiClient.delete(`/vehicles/${vehicleId}`);
}
