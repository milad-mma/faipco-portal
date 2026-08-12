import { apiClient } from "./client";

export async function fetchAllNotices() {
  const { data } = await apiClient.get("/notices");
  return data;
}

export async function fetchMyNotices() {
  const { data } = await apiClient.get("/notices/me");
  return data;
}

export async function createNotice(payload) {
  const { data } = await apiClient.post("/notices", payload);
  return data;
}

export async function publishNotice(noticeId) {
  const { data } = await apiClient.post(`/notices/${noticeId}/publish`);
  return data;
}

export async function fetchAvailableTargets() {
  const { data } = await apiClient.get("/notices/available-targets");
  return data;
}

export async function markNoticeRead(noticeId) {
  await apiClient.post(`/notices/${noticeId}/read`);
}

export async function fetchSentByMe(page = 1, pageSize = 10) {
  const { data } = await apiClient.get("/notices/sent-by-me", { params: { page, page_size: pageSize } });
  return data; // { items, total }
}

export async function fetchAdminReport(page = 1, pageSize = 10) {
  const { data } = await apiClient.get("/notices/admin-report", { params: { page, page_size: pageSize } });
  return data; // { items, total }
}

export async function fetchNoticeStatsSummary() {
  const { data } = await apiClient.get("/notices/stats-summary");
  return data; // { published_this_week }
}

export async function fetchNoticeReaders(noticeId) {
  const { data } = await apiClient.get(`/notices/${noticeId}/readers`);
  return data;
}

export async function deleteNotice(noticeId) {
  await apiClient.delete(`/notices/${noticeId}`);
}

export async function createPayrollNotice({ title, body, priority, file }) {
  const formData = new FormData();
  formData.append("title", title);
  formData.append("body", body || "");
  formData.append("priority", priority);
  formData.append("file", file);
  const { data } = await apiClient.post("/notices/payroll", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function fetchMyPayrollReceiptBlob(noticeId) {
  const { data } = await apiClient.get(`/notices/${noticeId}/payroll/mine`, {
    responseType: "blob",
  });
  return data; // Blob از نوع application/pdf — فقط فیش خودِ کاربر جاری
}

export async function createAttendanceCardNotice({ title, body, priority, headerRows, file }) {
  const formData = new FormData();
  formData.append("title", title);
  formData.append("body", body || "");
  formData.append("priority", priority);
  formData.append("header_rows", headerRows || 4);
  formData.append("file", file);
  const { data } = await apiClient.post("/notices/attendance-card", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function fetchMyAttendanceCardBlob(noticeId) {
  const { data } = await apiClient.get(`/notices/${noticeId}/attendance-card/mine`, {
    responseType: "blob",
  });
  return data; // Blob از نوع application/pdf — فقط کارت خودِ کاربر جاری
}
