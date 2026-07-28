import createCache from "@emotion/cache";
import { prefixer } from "stylis";
import rtlPlugin from "stylis-plugin-rtl";

/**
 * MUI به‌طور پیش‌فرض استایل‌ها را LTR تولید می‌کند.
 * این Cache با stylis-plugin-rtl باعث می‌شود همه استایل‌ها (margin/padding/position و ...)
 * به‌درستی برای چیدمان راست‌به‌چپ تولید شوند.
 */
export const rtlCache = createCache({
  key: "muirtl",
  stylisPlugins: [prefixer, rtlPlugin],
});
