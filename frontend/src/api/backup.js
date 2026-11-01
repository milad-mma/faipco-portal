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

// ---------- بکاپ نسخه‌ی ۴ (docs/backup.md) ----------

// { runs, local, active_key, age_available, disk, last_success_at, warnings }
export async function fetchBackupOverview() {
  const { data } = await apiClient.get("/backup/overview");
  return data;
}

// ساخت بکاپ در پس‌زمینه؛ sendToDestinations=false فقط نسخه‌ی روی سرور
export async function startBackup(sendToDestinations) {
  const { data } = await apiClient.post("/backup/run-now", null, { params: { send_to_destinations: sendToDestinations } });
  return data;
}

// دانلود یک نسخه‌ی روی سرور (Blob)
export async function downloadLocalBackup(filename) {
  const { data } = await apiClient.get(`/backup/local/${encodeURIComponent(filename)}/download`, {
    responseType: "blob",
    timeout: 30 * 60 * 1000,
  });
  return data;
}

// بازیابی از نسخه‌ی روی سرور (privateKey برای بکاپ رمزنگاری‌شده با کلید بیرون از سرور)
export async function restoreLocalBackup(filename, confirm, privateKey) {
  const { data } = await apiClient.post("/backup/restore-local", {
    filename,
    confirm,
    private_key: privateKey || null,
  });
  return data;
}

export async function fetchBackupKeys() {
  const { data } = await apiClient.get("/backup/keys");
  return data;
}

// mode: external | server_protected؛ privateKey اختیاری (وارد کردن کلید موجود). در حالت external پاسخ private_key_once دارد.
export async function createBackupKey(mode, privateKey) {
  const { data } = await apiClient.post("/backup/keys", { mode, private_key: privateKey || null });
  return data;
}

export async function exportKeyPackage(passphrase) {
  const { data } = await apiClient.post("/backup/keys/package", { passphrase }, { responseType: "blob" });
  return data;
}

export async function importKeyPackage(file, passphrase, mode) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("passphrase", passphrase);
  formData.append("mode", mode);
  const { data } = await apiClient.post("/backup/keys/import-package", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
