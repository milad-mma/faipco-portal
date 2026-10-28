// توابع فراخوانی API ماژول «اطلاعات بانکی» (پیشوند /bank-accounts در بک‌اند؛ docs/bank-accounts.md).
import { apiClient } from "./client";

// بانک‌های فعال سایت + اطلاعات ثبت‌شده‌ی خودم: {banks, missing_required, missing_banks}
export async function fetchMyBankInfo() {
  const { data } = await apiClient.get("/bank-accounts/me");
  return data;
}

// ثبت/تغییر اطلاعات یک بانک برای خودم؛ خروجی همان fetchMyBankInfo
export async function saveMyBankAccount(bankId, payload) {
  const { data } = await apiClient.put(`/bank-accounts/me/${bankId}`, payload);
  return data;
}

export async function fetchMyBankHistory() {
  const { data } = await apiClient.get("/bank-accounts/me/history");
  return data;
}

// ---------- مدیریت ----------

export async function fetchSiteBanks(siteId) {
  const { data } = await apiClient.get(`/bank-accounts/admin/sites/${siteId}/banks`);
  return data;
}

export async function addSiteBank(siteId, payload) {
  const { data } = await apiClient.post(`/bank-accounts/admin/sites/${siteId}/banks`, payload);
  return data;
}

export async function updateBank(bankId, payload) {
  const { data } = await apiClient.put(`/bank-accounts/admin/banks/${bankId}`, payload);
  return data;
}

export async function deleteBank(bankId) {
  await apiClient.delete(`/bank-accounts/admin/banks/${bankId}`);
}

// گزارش پرسنل × بانک‌ها: {banks, items, counts}
export async function fetchBankReport(params) {
  const { data } = await apiClient.get("/bank-accounts/admin/report", { params });
  return data;
}

export async function exportBankReport(params) {
  const { data } = await apiClient.get("/bank-accounts/admin/export", { params, responseType: "blob" });
  return data;
}

export async function fetchEmployeeBankHistory(employeeId) {
  const { data } = await apiClient.get(`/bank-accounts/admin/employees/${employeeId}/history`);
  return data;
}

export async function adminSaveBankAccount(employeeId, bankId, payload) {
  const { data } = await apiClient.put(`/bank-accounts/admin/employees/${employeeId}/banks/${bankId}`, payload);
  return data;
}
