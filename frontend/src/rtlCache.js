import createCache from "@emotion/cache";
import { prefixer } from "stylis";
import rtlPlugin from "@mui/stylis-plugin-rtl";

/**
 * MUI به‌طور پیش‌فرض استایل‌ها را LTR تولید می‌کند.
 * این Cache با @mui/stylis-plugin-rtl (فورک نگهداری‌شده و سازگار با Stylis v4)
 * باعث می‌شود همه استایل‌ها (margin/padding/position و ...) به‌درستی
 * برای چیدمان راست‌به‌چپ تولید شوند.
 *
 * نکته: پکیج قدیمی «stylis-plugin-rtl» از سال ۲۰۲۱ به‌روزرسانی نشده و با
 * نسخه‌های جدید Stylis سازگار نیست؛ به همین دلیل از فورک رسمی MUI استفاده شده.
 */
export const rtlCache = createCache({
  key: "muirtl",
  stylisPlugins: [prefixer, rtlPlugin],
});
