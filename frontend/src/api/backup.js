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
