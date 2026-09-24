/**
 * توابع فراخوانی API اعلان سراسری (Announcement).
 * گرفتن اعلان فعلی، بستن آن توسط کاربر و خواندن/ذخیره‌ی تنظیمات اعلان توسط مدیر.
 */
import { apiClient } from "./client";

// GET /announcement/current؛ خروجی: اعلان فعال فعلی برای کاربر جاری (در صورت وجود)
export async function fetchCurrentAnnouncement() {
  const { data } = await apiClient.get("/announcement/current");
  return data;
}

// POST /announcement/dismiss؛ اعلان فعلی را برای کاربر جاری بسته‌شده ثبت می‌کند
export async function dismissAnnouncement() {
  const { data } = await apiClient.post("/announcement/dismiss");
  return data;
}

// GET /announcement/settings؛ خروجی: تنظیمات اعلان (فعال بودن، عنوان، متن)
export async function fetchAnnouncementSettings() {
  const { data } = await apiClient.get("/announcement/settings");
  return data;
}

// PUT /announcement/settings؛ ذخیره‌ی فعال بودن، عنوان و متن اعلان؛ خروجی: تنظیمات ذخیره‌شده
export async function updateAnnouncementSettings({ enabled, title, body }) {
  const { data } = await apiClient.put("/announcement/settings", { enabled, title, body });
  return data;
}
