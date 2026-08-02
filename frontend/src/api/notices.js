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
