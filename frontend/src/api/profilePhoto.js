// عکس پرسنلی: درخواست بارگذاری/حذف و بررسی منابع انسانی (بک‌اند: endpoints/profile_photos.py)
import { apiClient } from "./client";

// { has_photo, enabled, pending: {id, action, created_at} | null, last_decision: {action, status, reason, decided_at} | null }
export async function fetchMyPhotoStatus() {
  const { data } = await apiClient.get("/profile-photo/me");
  return data;
}

export async function requestPhotoUpload(file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post("/profile-photo/me/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 5 * 60 * 1000,
    onUploadProgress: (e) => onProgress?.(e.total ? Math.round((e.loaded * 100) / e.total) : 0),
  });
  return data;
}

export async function requestPhotoDelete() {
  const { data } = await apiClient.post("/profile-photo/me/delete");
  return data;
}

export async function cancelPhotoRequest() {
  const { data } = await apiClient.delete("/profile-photo/me/pending");
  return data;
}

export async function fetchMyPendingPhotoBlob() {
  const { data } = await apiClient.get("/profile-photo/me/pending/image", { responseType: "blob" });
  return data;
}

// ---------- منابع انسانی (photo.approve) ----------

export async function fetchPhotoRequests(box, page) {
  const { data } = await apiClient.get("/profile-photo/requests", { params: { box, page } });
  return data; // { items, total, page, page_size }
}

// kind: image (عکس جدید) | current (عکس فعلی پرسنل)
export async function fetchPhotoRequestBlob(id, kind) {
  const { data } = await apiClient.get(`/profile-photo/requests/${id}/${kind}`, { responseType: "blob" });
  return data;
}

export async function approvePhotoRequest(id) {
  const { data } = await apiClient.post(`/profile-photo/requests/${id}/approve`, null, { timeout: 60 * 1000 });
  return data;
}

export async function rejectPhotoRequest(id, reason) {
  const { data } = await apiClient.post(`/profile-photo/requests/${id}/reject`, { reason });
  return data;
}
