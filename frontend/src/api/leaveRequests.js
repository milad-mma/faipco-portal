/**
 * توابع فراخوانی API درخواست‌های مرخصی.
 * شامل گرفتن انواع مرخصی، ثبت درخواست، لیست درخواست‌های خود کاربر،
 * لیست درخواست‌های در انتظار تصمیم مدیر، ثبت تصمیم و حذف درخواست.
 */
import { apiClient } from "./client";

// لیست انواع فعال درخواست مرخصی را برای نمایش در فرم برمی‌گرداند
export async function fetchActiveLeaveRequestTypes() {
  const { data } = await apiClient.get("/leave-requests/types");
  return data;
}

// یک درخواست مرخصی جدید ثبت می‌کند؛ ورودی: payload شامل نوع، بازه و توضیحات؛ خروجی: درخواست ثبت‌شده
export async function submitLeaveRequest(payload) {
  const { data } = await apiClient.post("/leave-requests/submit", payload);
  return data;
}

// درخواست‌های مرخصی خودِ کاربر جاری را برمی‌گرداند
export async function fetchMyLeaveRequests() {
  const { data } = await apiClient.get("/leave-requests/my-requests");
  return data;
}

// درخواست‌های در انتظار تصمیم که کاربر جاری تأییدکننده‌ی آن‌هاست را برمی‌گرداند
export async function fetchPendingLeaveRequestsForMe() {
  const { data } = await apiClient.get("/leave-requests/pending-for-me");
  return data;
}

// درخواست‌هایی که کاربر جاری قبلاً روی آن‌ها تصمیم گرفته را صفحه‌بندی‌شده برمی‌گرداند
export async function fetchDecidedLeaveRequestsByMe(page = 0, pageSize = 10) {
  const { data } = await apiClient.get("/leave-requests/decided-by-me", {
    params: { page, page_size: pageSize },
  });
  return data;
}

// تصمیم مدیر (تأیید/رد) به همراه نظر او را روی یک درخواست ثبت می‌کند
export async function decideLeaveRequest(requestId, approved, managerIdea) {
  const { data } = await apiClient.post(`/leave-requests/${requestId}/decide`, {
    approved,
    manager_idea: managerIdea || "",
  });
  return data;
}

// یک درخواست مرخصی را با شناسه‌ی آن حذف می‌کند
export async function deleteLeaveRequest(requestId) {
  const { data } = await apiClient.delete(`/leave-requests/${requestId}`);
  return data;
}

// تعداد درخواست‌های در انتظار تصمیمِ کاربر جاری را برمی‌گرداند (برای نشانگر منو)
export async function fetchPendingLeaveRequestCount() {
  const { data } = await apiClient.get("/leave-requests/pending-count");
  return data;
}
