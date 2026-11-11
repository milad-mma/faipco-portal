/** One shared set of Persian update messages for releases and admin-triggered refreshes. */
export const UPDATE_TITLE = "سامانه آماده به روزرسانی است";
export const UPDATE_ACTION = "به روزرسانی";
export const UPDATE_ACTIVATING_TEXT = "در حال آماده‌سازی و فعال‌کردن نسخه جدید...";
export const UPDATE_ACTIVATING_ACTION = "در حال به‌روزرسانی...";
export const UPDATE_RELOADING_TEXT = "سامانه به روزرسانی شد.";
export const UPDATE_RELOADING_ACTION = "در حال بارگذاری ...";
export const UPDATE_RETRY_ACTION = "تلاش دوباره";

export function updateReadyDescription(_kind) {
  return "برای استفاده از آخرین نسخه پرتال، «به روزرسانی» را انتخاب کنید.";
}

export function updateSuccessMessage(kind) {
  return kind === "cache_refresh"
    ? "سامانه با موفقیت بارگذاری شد."
    : "نسخه جدید سامانه با موفقیت بارگذاری شد.";
}

export function updateErrorMessage(reason) {
  switch (reason) {
    case "not-ready": return "فایل‌های به‌روزرسانی آماده نیستند. کمی بعد دوباره تلاش کنید.";
    case "activation-timeout": return "بارگذاری نسخه جدید طولانی شد. لطفا دوباره تلاش کنید.";
    case "unsupported": return "به‌روزرسانی خودکار در این مرورگر پشتیبانی نمی‌شود. صفحه را دوباره باز کنید.";
    default: return "به‌روزرسانی انجام نشد. دوباره تلاش کنید.";
  }
}
