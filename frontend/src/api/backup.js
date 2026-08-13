import { apiClient } from "./client";

export async function downloadBackupArchive() {
  const { data } = await apiClient.get("/backup/export", { responseType: "blob" });
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
