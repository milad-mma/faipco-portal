/**
 * توابع فراخوانی API پشتیبان‌گیری و بازیابی.
 * دانلود/بازیابی فایل پشتیبان، وضعیت بازیابی، تنظیمات پشتیبان‌گیری،
 * تست اتصال SMB/FTP و اجرای فوری پشتیبان‌گیری.
 */
import { apiClient } from "./client";

// GET /backup/export؛ خروجی: فایل پشتیبان کامل به صورت Blob (zip)
export async function downloadBackupArchive() {
  const { data } = await apiClient.get("/backup/export", {
    responseType: "blob",
    timeout: 5 * 60 * 1000, // دیتابیس‌های بزرگ ممکن است چند دقیقه طول بکشد
  });
  return data; // Blob از نوع application/zip
}

// POST /backup/restore؛ آپلود فایل پشتیبان همراه عبارت تأیید و شروع بازیابی؛ خروجی: پاسخ سرور
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

// GET /backup/restore-status؛ خروجی: لاگ و وضعیت اجرای بازیابی
export async function fetchRestoreStatus() {
  // Timeout کوتاه تا در زمان Stop/Start سرویس، درخواست سریع خطا دهد و فرانت‌اند فوراً دوباره تلاش کند
  const { data } = await apiClient.get("/backup/restore-status", { timeout: 5000 });
  return data; // { log, is_running, is_finished, is_failed }
}

// GET /backup/settings؛ خروجی: تنظیمات پشتیبان‌گیری (زمان‌بندی و مقصدهای راه‌دور)
export async function fetchBackupSettings() {
  const { data } = await apiClient.get("/backup/settings");
  return data;
}

// PUT /backup/settings؛ ذخیره‌ی تنظیمات پشتیبان‌گیری؛ خروجی: تنظیمات ذخیره‌شده
export async function updateBackupSettings(payload) {
  const { data } = await apiClient.put("/backup/settings", payload);
  return data;
}

// POST /backup/test-smb؛ تست اتصال به پوشه‌ی اشتراکی SMB؛ خروجی: نتیجه‌ی تست
export async function testSmbConnection(payload) {
  const { data } = await apiClient.post("/backup/test-smb", payload, { timeout: 30000 });
  return data;
}

// POST /backup/test-ftp؛ تست اتصال به سرور FTP؛ خروجی: نتیجه‌ی تست
export async function testFtpConnection(payload) {
  const { data } = await apiClient.post("/backup/test-ftp", payload, { timeout: 30000 });
  return data;
}

// POST /backup/run-now؛ ساخت فوری پشتیبان و آپلود به مقصدهای راه‌دور فعال؛ خروجی: نتیجه‌ی اجرا
export async function runBackupNow() {
  // Timeout پنج دقیقه‌ای چون برای دیتابیس‌های بزرگ چند دقیقه طول می‌کشد
  const { data } = await apiClient.post("/backup/run-now", null, { timeout: 5 * 60 * 1000 });
  return data;
}
