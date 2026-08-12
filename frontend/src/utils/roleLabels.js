// نگاشت نام فنی نقش (Role.name در دیتابیس) به برچسب فارسی قابل‌نمایش در UI.
// نقش‌هایی که اینجا نیستند (مثل superadmin که اصلاً قابل‌انتصاب از UI نیست)
// همان نام خام‌شان نمایش داده می‌شود.
export const ROLE_DISPLAY_NAMES = {
  site_manager: "مدیر سایت",
  middle_manager: "مدیر میانی",
  acc_manager: "مدیر حسابداری",
  "hr-manager": "مدیر منابع انسانی",
};

export function roleDisplayName(roleName) {
  return ROLE_DISPLAY_NAMES[roleName] || roleName;
}
