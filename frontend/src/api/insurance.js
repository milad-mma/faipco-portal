// توابع فراخوانی API ماژول بیمه تکمیلی (پیشوند /insurance در بک‌اند).
// هر تابع یک درخواست HTTP می‌فرستد و بدنه‌ی پاسخ (data) را برمی‌گرداند.
import { apiClient } from "./client";

// آدرس کامل دانلود/پیش‌نمایش یک مدرک؛ inline=true برای نمایش در مرورگر به‌جای دانلود
export const INSURANCE_DOCUMENT_URL = (id, inline = false) =>
  `${apiClient.defaults.baseURL}/insurance/documents/${id}${inline ? "?inline=true" : ""}`;

// ---------- پرسنل ----------

// داده‌ی کامل صفحه‌ی بیمه برای کاربر جاری
export async function fetchMyInsurance() {
  const { data } = await apiClient.get("/insurance/me");
  return data; // { enabled, employee, registration, rate_table, notes, bank_codes, account_types, member_types }
}

// ثبت یا ویرایش فرم ثبت‌نام؛ خروجی ثبت‌نام ذخیره‌شده است
export async function saveMyInsurance(payload) {
  const { data } = await apiClient.put("/insurance/me", payload);
  return data;
}

// آپلود یک فایل مدرک به‌صورت multipart؛ onProgress با درصد پیشرفت (۰ تا ۱۰۰) صدا زده می‌شود
export async function uploadInsuranceDocument(file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await apiClient.post("/insurance/me/documents", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 3 * 60 * 1000, // عکس گوشی (چند مگابایت) روی اینترنت همراه بیش از ۲۰ ثانیه‌ی پیش‌فرض طول می‌کشد
    onUploadProgress: (e) => onProgress?.(e.total ? Math.round((e.loaded * 100) / e.total) : 0),
  });
  return data; // { id, file_name, content_type, size_bytes, uploaded_at }
}

// حذف مدرک متعلق به خود کاربر
export async function deleteMyInsuranceDocument(id) {
  await apiClient.delete(`/insurance/me/documents/${id}`);
}

// دریافت محتوای یک مدرک به‌صورت Blob (برای پیش‌نمایش/ذخیره در کلاینت)
export async function downloadInsuranceDocument(id) {
  const { data } = await apiClient.get(`/insurance/documents/${id}`, { responseType: "blob" });
  return data;
}

// ---------- مدیریت ----------

// تنظیمات ماژول برای صفحه‌ی مدیریت
export async function fetchInsuranceSettings() {
  const { data } = await apiClient.get("/insurance/settings");
  return data; // { enabled, rate_table, notes }
}

// تغییر بخشی از تنظیمات؛ فقط کلیدهای موجود در payload اعمال می‌شوند
export async function updateInsuranceSettings(payload) {
  const { data } = await apiClient.put("/insurance/settings", payload);
  return data;
}

// فهرست ثبت‌نام‌ها با پارامترهای search / site_id / page / page_size
export async function fetchInsuranceRegistrations(params = {}) {
  const { data } = await apiClient.get("/insurance/registrations", { params });
  return data; // { items, total, registered, eligible }
}

// جزئیات یک ثبت‌نام همراه اعضا و مدارک
export async function fetchInsuranceRegistration(id) {
  const { data } = await apiClient.get(`/insurance/registrations/${id}`);
  return data;
}

// رد مدرک کفالت یک عضو (حذف فایل + اطلاعیه برای ثبت‌نام‌کننده)؛ خروجی: { member_name, notice_id }
export async function rejectInsuranceDocument(registrationId, memberId) {
  const { data } = await apiClient.post(
    `/insurance/registrations/${registrationId}/members/${memberId}/reject-document`
  );
  return data;
}

// حذف کامل یک ثبت‌نام (نیاز به مجوز insurance.manage)
export async function deleteInsuranceRegistration(id) {
  await apiClient.delete(`/insurance/registrations/${id}`);
}

// دریافت فایل Excel ثبت‌نام‌ها به‌صورت Blob؛ siteId اختیاری برای محدود کردن به یک سایت
export async function downloadInsuranceExport(siteId) {
  const { data } = await apiClient.get("/insurance/export", {
    params: siteId ? { site_id: siteId } : {},
    responseType: "blob",
  });
  return data;
}
