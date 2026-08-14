import { apiClient } from "./client";

export async function bustAppCache() {
  const { data } = await apiClient.post("/system/cache-bust");
  return data; // { success, version, message }
}

export async function fetchIpAllowlist() {
  const { data } = await apiClient.get("/system/ip-allowlist");
  return data;
}

export async function addIpAllowlistEntry({ cidr, label }) {
  const { data } = await apiClient.post("/system/ip-allowlist", { cidr, label: label || null });
  return data;
}

export async function deleteIpAllowlistEntry(entryId) {
  await apiClient.delete(`/system/ip-allowlist/${entryId}`);
}

export async function extractIpAllowlistCandidates(text) {
  const { data } = await apiClient.post(
    "/system/ip-allowlist/extract",
    { text },
    { timeout: 60_000 } // متن‌های خیلی بزرگ (مثلاً فایروال با هزاران رنج) ممکن است بیشتر طول بکشد
  );
  return data.candidates; // [{ cidr, already_exists }]
}

export async function bulkAddIpAllowlist({ cidrs, label }) {
  const { data } = await apiClient.post(
    "/system/ip-allowlist/bulk-add",
    { cidrs, label: label || null },
    { timeout: 60_000 }
  );
  return data; // { added, added_count, duplicate_count }
}

export async function fetchIpBlockedMessage() {
  const { data } = await apiClient.get("/system/ip-blocked-message");
  return data.message;
}

export async function updateIpBlockedMessage(message) {
  const { data } = await apiClient.put("/system/ip-blocked-message", { message });
  return data.message;
}
