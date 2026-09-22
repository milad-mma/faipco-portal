/**
 * کمک‌تابع‌های مشترک نمودارهای پنل ادمین (UsageLineChart / UsageBarChart).
 *
 * ⚠️ RTL: پروژه از stylis-plugin-rtl استفاده می‌کند که left/right/textAlign
 * داخل sx را قرینه می‌کند؛ همه موقعیت‌های افقی نمودارها در style خطی نوشته
 * می‌شوند (نه sx) و ریشه نمودار dir="ltr" دارد تا محور زمان همیشه چپ‌به‌راست
 * و برچسب‌ها دقیقاً زیر نقطه/میله خودشان باشند.
 */

export const AXIS_WIDTH = 40; // ستون اعداد محور عمودی
export const PLOT_HEIGHT = 150;

/** سقف «گرد» محور عمودی: ۱، ۲ یا ۵ ضربدر توان ۱۰ (مثلاً ۳۷ ← ۵۰، ۱۲۰ ← ۲۰۰) */
export function niceMax(value) {
  if (!value || value <= 0) return 1;
  const exponent = Math.pow(10, Math.floor(Math.log10(value)));
  const fraction = value / exponent;
  const nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10;
  return nice * exponent;
}

export function formatNumber(value) {
  return Number(value).toLocaleString("fa-IR");
}

/** برچسب محور افقی: وقتی نقاط زیادند، فقط هر چندتا یکی (به‌علاوه آخری) */
export function labelStepFor(count, maxLabels = 8) {
  return Math.max(1, Math.ceil(count / maxLabels));
}

/** جابه‌جایی افقی Tooltip/برچسب لبه‌ها تا از کادر بیرون نزند (fraction بین ۰ و ۱) */
export function edgeAwareTranslate(fraction) {
  if (fraction < 0.12) return "translateX(0)";
  if (fraction > 0.88) return "translateX(-100%)";
  return "translateX(-50%)";
}
