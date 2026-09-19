import { apiClient } from "./client";

export async function fetchCurrentAnnouncement() {
  const { data } = await apiClient.get("/announcement/current");
  return data;
}

export async function dismissAnnouncement() {
  const { data } = await apiClient.post("/announcement/dismiss");
  return data;
}

export async function fetchAnnouncementSettings() {
  const { data } = await apiClient.get("/announcement/settings");
  return data;
}

export async function updateAnnouncementSettings({ enabled, title, body }) {
  const { data } = await apiClient.put("/announcement/settings", { enabled, title, body });
  return data;
}
