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

export async function fetchSentByMe() {
  const { data } = await apiClient.get("/notices/sent-by-me");
  return data;
}

export async function fetchAdminReport() {
  const { data } = await apiClient.get("/notices/admin-report");
  return data;
}

export async function fetchNoticeReaders(noticeId) {
  const { data } = await apiClient.get(`/notices/${noticeId}/readers`);
  return data;
}
