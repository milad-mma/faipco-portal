import { apiClient } from "./client";

export async function downloadBackupArchive() {
  const { data } = await apiClient.get("/backup/export", {
    responseType: "blob",
    timeout: 5 * 60 * 1000, // دیتابیس‌های بزرگ ممکن است چند دقیقه طول بکشد
  });
  return data; // Blob از نوع application/zip
}

export async function restoreBackupArchive(file, confirmPhrase) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("confirm", confirmPhrase);
  const { data } = await apiClient.post("/backup/restore", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 5 * 60 * 1000, // بازیابی دیتابیس‌های بزرگ ممکن است چند دقیقه طول بکشد
  });
  return data;
}

export async function fetchRestoreStatus() {
  // Timeout کوتاه عمدی است: دقیقاً همان چند ثانیه‌ای که خودِ سرویس Stop/Start
  // می‌شود، این درخواست باید سریع Fail شود تا فرانت‌اند فوراً دوباره امتحان
  // کند، نه این‌که طولانی معطل یک Timeout بزرگ بماند.
  const { data } = await apiClient.get("/backup/restore-status", { timeout: 5000 });
  return data; // { log, is_running, is_finished, is_failed }
}

export async function fetchBackupSettings() {
  const { data } = await apiClient.get("/backup/settings");
  return data;
}

export async function updateBackupSettings(payload) {
  const { data } = await apiClient.put("/backup/settings", payload);
  return data;
}

export async function testSmbConnection(payload) {
  const { data } = await apiClient.post("/backup/test-smb", payload, { timeout: 30000 });
  return data;
}

export async function testFtpConnection(payload) {
  const { data } = await apiClient.post("/backup/test-ftp", payload, { timeout: 30000 });
  return data;
}

export async function runBackupNow() {
  // شامل ساخت بکاپ + آپلود به هدف(های) راه‌دور فعال - می‌تواند برای
  // دیتابیس‌های بزرگ چند دقیقه طول بکشد.
  const { data } = await apiClient.post("/backup/run-now", null, { timeout: 5 * 60 * 1000 });
  return data;
}
