/**
 * نگاشت نام فنی نقش (Role.name در دیتابیس) به برچسب فارسی قابل نمایش در UI.
 * نقش‌هایی که اینجا نیستند (مثل superadmin که از UI قابل انتصاب نیست) با همان نام خام نمایش داده می‌شوند.
 */
export const ROLE_DISPLAY_NAMES = {
  site_manager: "مدیر سایت",
  middle_manager: "مدیر میانی",
  acc_manager: "مدیر حسابداری",
  "hr-manager": "مدیر منابع انسانی",
};

// ورودی: نام فنی نقش؛ خروجی: برچسب فارسی یا همان نام خام
export function roleDisplayName(roleName) {
  return ROLE_DISPLAY_NAMES[roleName] || roleName;
}
