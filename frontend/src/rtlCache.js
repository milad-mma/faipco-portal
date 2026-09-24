import createCache from "@emotion/cache";
import { prefixer } from "stylis";
import rtlPlugin from "@mui/stylis-plugin-rtl";

/**
 * کش Emotion برای چیدمان راست‌به‌چپ (RTL).
 * MUI به‌طور پیش‌فرض استایل‌ها را LTR تولید می‌کند؛ این کش با @mui/stylis-plugin-rtl (سازگار با Stylis v4)
 * همه‌ی استایل‌ها (margin/padding/position و ...) را برای RTL برعکس می‌کند.
 * پکیج stylis-plugin-rtl با نسخه‌های جدید Stylis سازگار نیست و به همین دلیل از فورک MUI استفاده شده است.
 */
export const rtlCache = createCache({
  key: "muirtl", // پیشوند نام کلاس‌های CSS تولیدشده
  stylisPlugins: [prefixer, rtlPlugin], // افزودن vendor prefix و سپس تبدیل RTL
});
