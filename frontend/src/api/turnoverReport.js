// توابع API «گزارش جذب و ترک کار» (پیشوند /reports/turnover در بک‌اند)
import { apiClient } from "./client";

// پارامترهای خالی ارسال نمی‌شوند
const clean = (params) => Object.fromEntries(Object.entries(params || {}).filter(([, v]) => v !== "" && v !== null && v !== undefined));

// گزارش کامل؛ params: site_id، from_month، to_month (مثل 1403/06)، department، gender، refresh
export async function fetchTurnoverReport(params) {
  const { data } = await apiClient.get("/reports/turnover", { params: clean(params), timeout: 90_000 });
  return data;
}

// خروجی Excel همان گزارش به‌صورت Blob
export async function downloadTurnoverExport(params) {
  const { data } = await apiClient.get("/reports/turnover/export", {
    params: clean(params),
    responseType: "blob",
    timeout: 90_000,
  });
  return data;
}

// دسته‌ها و متن‌های علت ترک کار که الان در منبع استفاده می‌شوند (با تعداد)؛ refresh = بدون Cache
export async function fetchTurnoverCategories(refresh = false) {
  const { data } = await apiClient.get("/reports/turnover/categories", {
    params: refresh ? { refresh: true } : {},
    timeout: 90_000,
  });
  return data; // { can_manage, categories, aliases, count_error }
}

export async function createTurnoverCategory(payload) {
  const { data } = await apiClient.post("/reports/turnover/categories", payload);
  return data;
}

export async function updateTurnoverCategory(id, payload) {
  const { data } = await apiClient.put(`/reports/turnover/categories/${id}`, payload);
  return data;
}

export async function deleteTurnoverCategory(id) {
  await apiClient.delete(`/reports/turnover/categories/${id}`);
}

// تعیین دسته‌ی یک متن علت (categoryId خالی = دسته‌بندی نشده)
export async function setTurnoverAliasCategory(aliasId, categoryId) {
  const { data } = await apiClient.put(`/reports/turnover/aliases/${aliasId}`, { category_id: categoryId || null });
  return data;
}
