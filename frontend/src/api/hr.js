import { apiClient } from "./client";

export async function fetchBirthdayTemplates() {
  const { data } = await apiClient.get("/hr/birthday-templates");
  return data;
}

export async function addBirthdayTemplate(text) {
  const { data } = await apiClient.post("/hr/birthday-templates", { text });
  return data;
}

export async function deleteBirthdayTemplate(templateId) {
  await apiClient.delete(`/hr/birthday-templates/${templateId}`);
}

export async function fetchBirthdaySendTime() {
  const { data } = await apiClient.get("/hr/birthday-send-time");
  return data; // { hour, minute }
}

export async function updateBirthdaySendTime({ hour, minute }) {
  const { data } = await apiClient.put("/hr/birthday-send-time", { hour, minute });
  return data;
}

export async function fetchBirthdayEnabled() {
  const { data } = await apiClient.get("/hr/birthday-enabled");
  return data.enabled;
}

export async function updateBirthdayEnabled(enabled) {
  const { data } = await apiClient.put("/hr/birthday-enabled", { enabled });
  return data.enabled;
}
