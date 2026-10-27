// توابع API ماژول «درخواست وام» (پیشوند /loans در بک‌اند؛ docs/loans.md)
import { apiClient } from "./client";

// ---------- پرسنل ----------

// { enabled, policy: {title, rules_text, types[]}, service, block_reason, requests[] }
export async function fetchMyLoans() {
  const { data } = await apiClient.get("/loans/me");
  return data;
}

// همکاران قابل انتخاب به‌عنوان ضامن؛ loanTypeId: قواعد ضامنِ همان نوع وام اعمال می‌شود
export async function searchGuarantors(q, loanTypeId) {
  const { data } = await apiClient.get("/loans/guarantor-candidates", { params: { q, loan_type_id: loanTypeId || undefined } });
  return data; // [{ id, label }]
}

export async function submitLoan(payload) {
  const { data } = await apiClient.post("/loans", payload);
  return data;
}

export async function cancelLoan(id) {
  const { data } = await apiClient.post(`/loans/${id}/cancel`);
  return data;
}

export async function replaceGuarantor(id, guarantorId, employeeId) {
  const { data } = await apiClient.post(`/loans/${id}/guarantors/${guarantorId}/replace`, { employee_id: employeeId });
  return data;
}

export async function fetchLoanInbox() {
  const { data } = await apiClient.get("/loans/inbox");
  return data; // { guarantee[], approvals[] }
}

export async function fetchLoanInboxCount() {
  const { data } = await apiClient.get("/loans/inbox/count");
  return data; // { count }
}

// agreed: تیک «قوانین و مقررات ضمانت را خوانده‌ام و قبول دارم» (برای قبول ضمانت لازم است)
export async function decideGuarantee(id, approve, note, agreed = false) {
  const { data } = await apiClient.post(`/loans/${id}/guarantee`, { approve, note, agreed });
  return data;
}

export async function decideLoan(id, approve, note) {
  const { data } = await apiClient.post(`/loans/${id}/decide`, { approve, note });
  return data;
}

// ---------- مدیریت ----------

export async function fetchLoanAdminSites() {
  const { data } = await apiClient.get("/loans/admin/sites");
  return data; // [{ site_id, site_name, is_enabled, site_manager_employee_id, site_manager, can_policy, can_finance, can_view }]
}

// خروجی: { ok, reassigned, unresolved } — reassigned: درخواست‌های باز منتقل‌شده به تأییدکننده‌ی جدید
export async function updateLoanSite(siteId, payload) {
  const { data } = await apiClient.put(`/loans/admin/sites/${siteId}`, payload);
  return data;
}

// انتقال درخواست‌های در حال تأیید به تأییدکننده‌های امروز (مدیر واحد از زنجیره‌ی مرخصی)؛ خروجی { changed, unresolved }
export async function reassignLoanApprovers(siteId) {
  const { data } = await apiClient.post(`/loans/admin/sites/${siteId}/reassign-approvers`);
  return data;
}

export async function searchLoanSiteEmployees(siteId, q) {
  const { data } = await apiClient.get(`/loans/admin/sites/${siteId}/employees`, { params: { q } });
  return data;
}

export async function fetchLoanPolicies(siteId) {
  const { data } = await apiClient.get(`/loans/admin/sites/${siteId}/policies`);
  return data;
}

export async function createLoanPolicy(siteId, payload) {
  const { data } = await apiClient.post(`/loans/admin/sites/${siteId}/policies`, payload);
  return data;
}

export async function updateLoanPolicy(policyId, payload) {
  const { data } = await apiClient.put(`/loans/admin/policies/${policyId}`, payload);
  return data;
}

export async function deleteLoanPolicy(policyId) {
  await apiClient.delete(`/loans/admin/policies/${policyId}`);
}

export async function fetchLoanRequests(siteId, status) {
  const { data } = await apiClient.get(`/loans/admin/sites/${siteId}/requests`, { params: { status: status || undefined } });
  return data;
}

export async function fetchLoanRequest(id) {
  const { data } = await apiClient.get(`/loans/admin/requests/${id}`);
  return data;
}

export async function payLoan(id, payload) {
  const { data } = await apiClient.post(`/loans/admin/requests/${id}/pay`, payload);
  return data;
}

export async function rejectLoan(id, note) {
  const { data } = await apiClient.post(`/loans/admin/requests/${id}/reject`, { note });
  return data;
}

export async function setLoanQueue(id, queueSeq) {
  const { data } = await apiClient.post(`/loans/admin/requests/${id}/queue`, { queue_seq: queueSeq });
  return data;
}

export async function settleLoan(id, note) {
  const { data } = await apiClient.post(`/loans/admin/requests/${id}/settle`, { note });
  return data;
}

export async function toggleInstallment(installmentId) {
  const { data } = await apiClient.post(`/loans/admin/installments/${installmentId}/toggle`);
  return data;
}

export async function createManualLoan(siteId, payload) {
  const { data } = await apiClient.post(`/loans/admin/sites/${siteId}/manual`, payload);
  return data;
}

export async function fetchServiceOverrides(siteId) {
  const { data } = await apiClient.get(`/loans/admin/sites/${siteId}/service-overrides`);
  return data;
}

export async function fetchEmployeeService(employeeId) {
  const { data } = await apiClient.get(`/loans/admin/employees/${employeeId}/service`);
  return data;
}

export async function setServiceOverride(employeeId, startDate, note) {
  await apiClient.put(`/loans/admin/employees/${employeeId}/service`, { start_date: startDate, note });
}

export async function deleteServiceOverride(employeeId) {
  await apiClient.delete(`/loans/admin/employees/${employeeId}/service`);
}

// متن اعلان‌های وام این سایت (قابل‌ویرایش)
export async function fetchLoanNotificationTemplates(siteId) {
  const { data } = await apiClient.get(`/loans/admin/sites/${siteId}/notification-templates`);
  return data;
}

export async function saveLoanNotificationTemplates(siteId, texts) {
  const { data } = await apiClient.put(`/loans/admin/sites/${siteId}/notification-templates`, { texts });
  return data;
}

// سوابق کارتابل: kind = "decisions" (تأییدها/ردهای من) | "guarantees" (ضمانت‌های من)؛ خروجی { items, total }
export async function fetchLoanInboxHistory(kind, { q, page = 1, pageSize = 10 } = {}) {
  const { data } = await apiClient.get("/loans/inbox/history", {
    params: { kind, q: q || undefined, page, page_size: pageSize },
  });
  return data;
}
