import { apiClient } from "./client";

export async function fetchAppVersion() {
  const { data } = await apiClient.get("/system/version", { timeout: 5000 });
  return data.version;
}

export async function checkForUpdate() {
  const { data } = await apiClient.get("/system/check-update", { timeout: 15000 });
  return data; // { checked, current_version, latest_version, has_update, release_url }
}

export async function applyUpdate(confirmPhrase, password) {
  const formData = new FormData();
  formData.append("confirm", confirmPhrase);
  formData.append("password", password);
  const { data } = await apiClient.post("/system/apply-update", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function fetchUpdateStatus() {
  // Timeout کوتاه عمدی — دقیقاً همان چند ثانیه‌ای که سرویس Stop/Start
  // می‌شود، این درخواست باید سریع Fail شود تا فوراً دوباره امتحان کنیم.
  const { data } = await apiClient.get("/system/update-status", { timeout: 5000 });
  return data; // { log, is_running, is_finished, is_failed }
}

export async function bustAppCache() {
  const { data } = await apiClient.post("/system/cache-bust");
  return data; // { success, version, message }
}

export async function fetchIpAllowlistState() {
  const { data } = await apiClient.get("/system/ip-allowlist", { timeout: 60_000 });
  return data; // { enabled, text, count }
}

export async function saveIpAllowlistState({ enabled, text }) {
  const { data } = await apiClient.put(
    "/system/ip-allowlist",
    { enabled, text },
    { timeout: 60_000 } // فهرست‌های خیلی بزرگ (مثلاً فایروال با هزاران رنج) ممکن است بیشتر طول بکشد
  );
  return data; // { enabled, text, count }
}

export async function fetchIpBlockedMessage() {
  const { data } = await apiClient.get("/system/ip-blocked-message");
  return data.message;
}

export async function updateIpBlockedMessage(message) {
  const { data } = await apiClient.put("/system/ip-blocked-message", { message });
  return data.message;
}
