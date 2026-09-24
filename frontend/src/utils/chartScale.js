/**
 * کمک‌تابع‌ها و ثابت‌های مشترک نمودارهای پنل ادمین (UsageLineChart / UsageBarChart):
 * محاسبه‌ی سقف گرد محور، قالب‌بندی اعداد فارسی، فاصله‌ی برچسب‌ها و جابه‌جایی Tooltip در لبه‌ها.
 *
 * نکته‌ی RTL: stylis-plugin-rtl مقادیر left/right/textAlign داخل sx را قرینه می‌کند؛ به همین دلیل موقعیت‌های افقی
 * نمودارها در style خطی نوشته می‌شوند و ریشه‌ی نمودار dir="ltr" دارد تا محور زمان همیشه چپ‌به‌راست باشد.
 */

export const AXIS_WIDTH = 40; // عرض ستون اعداد محور عمودی (پیکسل)
export const PLOT_HEIGHT = 150; // ارتفاع ناحیه‌ی رسم نمودار (پیکسل)

/** سقف «گرد» محور عمودی: ۱، ۲ یا ۵ ضربدر توان ۱۰ (مثلاً ۳۷ ← ۵۰، ۱۲۰ ← ۲۰۰) */
export function niceMax(value) {
  if (!value || value <= 0) return 1;
  const exponent = Math.pow(10, Math.floor(Math.log10(value)));
  const fraction = value / exponent;
  const nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  return nice * exponent;
}

// عدد را با ارقام و جداکننده‌ی فارسی (fa-IR) به رشته تبدیل می‌کند
export function formatNumber(value) {
  return Number(value).toLocaleString("fa-IR");
}

/** گام نمایش برچسب‌های محور افقی؛ وقتی نقاط زیادند فقط هر چند نقطه یکی برچسب می‌گیرد (حداکثر maxLabels) */
export function labelStepFor(count, maxLabels = 8) {
  return Math.max(1, Math.ceil(count / maxLabels));
}

/** جابه‌جایی افقی Tooltip/برچسب لبه‌ها تا از کادر بیرون نزند (fraction بین ۰ و ۱) */
export function edgeAwareTranslate(fraction) {
  if (fraction < 0.12) return "translateX(0)";
  if (fraction > 0.88) return "translateX(-100%)";
  return "translateX(-50%)";
}
