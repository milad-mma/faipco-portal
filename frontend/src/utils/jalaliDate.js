/**
 * تبدیل تاریخ شمسی (جلالی) <-> میلادی بدون کتابخانه‌ی خارجی،
 * مبتنی بر الگوریتم استاندارد jalaali-js؛ به همراه طول ماه شمسی و نام ماه‌ها.
 */

// سال‌های شکست چرخه‌ی ۳۳ ساله‌ی کبیسه در تقویم جلالی (جدول الگوریتم jalaali-js)
const JALALI_BREAKS = [
  -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192,
  2262, 2324, 2394, 2456, 3178,
];

// تقسیم صحیح (برش اعشار به سمت صفر)
function div(a, b) {
  return ~~(a / b);
}

/**
 * ورودی: سال شمسی. وضعیت کبیسه را از جدول شکست‌ها محاسبه می‌کند.
 * خروجی: { gy: سال میلادی متناظر، march: روزی از مارس که نوروز در آن است }
 */
function jalCal(jy) {
  const bl = JALALI_BREAKS.length;
  const gy = jy + 621;
  let leapJ = -14;
  let jp = JALALI_BREAKS[0];
  let jump = 0;

  for (let i = 1; i < bl; i += 1) {
    const jm = JALALI_BREAKS[i];
    jump = jm - jp;
    if (jy < jm) break;
    leapJ += div(jump, 33) * 8 + div(jump % 33, 4);
    jp = jm;
  }
  let n = jy - jp;

  leapJ += div(n, 33) * 8 + div((n % 33) + 3, 4);
  if (jump % 33 === 4 && jump - n === 4) leapJ += 1;

  const leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
  const march = 20 + leapJ - leapG;

  return { gy, march };
}

/** تاریخ شمسی → شیء Date میلادی (ساعت آن Date با پارامترهای hour/minute پر می‌شود) */
export function jalaliToGregorian(jy, jm, jd, hour = 0, minute = 0) {
  const r = jalCal(jy);
  const gy = r.gy;
  const march = r.march;
  // روزشمار از ابتدای سال شمسی (۰-پایه): ماه‌های ۱ تا ۶ هرکدام ۳۱ روز و ماه‌های ۷ تا ۱۲ هرکدام ۳۰ روز
  const jdays = jm <= 6 ? (jm - 1) * 31 + (jd - 1) : 186 + (jm - 7) * 30 + (jd - 1);
  const gDate = new Date(gy, 2, march); // نوروز همان سال شمسی (حوالی ۲۰-۲۱ مارس میلادی)
  gDate.setDate(gDate.getDate() + jdays);
  gDate.setHours(hour, minute, 0, 0);
  return gDate;
}

/** شیء Date میلادی → {jy, jm, jd} شمسی */
export function gregorianToJalali(date) {
  // ساعت تاریخ حذف می‌شود تا فاصله‌ی روزها عدد صحیح باشد؛ در غیر این صورت Math.round
  // ساعات بعدازظهر را به روز بعد گرد می‌کند. این تابع فقط با روز تقویمی کار دارد
  const dateOnly = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const gy = dateOnly.getFullYear();
  // سال شمسی‌ای پیدا می‌شود که تاریخ بین نوروز آن و نوروز سال بعدش باشد؛ سپس ماه و روز از روزشمار محاسبه می‌شود
  for (const candidateJy of [gy - 622, gy - 621, gy - 620]) {
    const r = jalCal(candidateJy);
    const march = r.march;
    const marchDate = new Date(r.gy, 2, march);
    const nextR = jalCal(candidateJy + 1);
    const nextMarchDate = new Date(nextR.gy, 2, nextR.march);
    if (dateOnly >= marchDate && dateOnly < nextMarchDate) {
      const diffDays = Math.round((dateOnly - marchDate) / 86400000);
      let jm;
      let jd;
      if (diffDays < 186) {
        jm = 1 + Math.floor(diffDays / 31);
        jd = 1 + (diffDays % 31);
      } else {
        const d2 = diffDays - 186;
        jm = 7 + Math.floor(d2 / 30);
        jd = 1 + (d2 % 30);
      }
      return { jy: candidateJy, jm, jd };
    }
  }
  // مقدار ایمن در صورتی که هیچ سال کاندیدی منطبق نباشد (در عمل رخ نمی‌دهد)
  return { jy: gy - 621, jm: 1, jd: 1 };
}

// ورودی: سال و ماه شمسی؛ خروجی: تعداد روزهای آن ماه (اسفند در سال کبیسه ۳۰ روز)
export function jalaliMonthLength(jy, jm) {
  if (jm <= 6) return 31;
  if (jm <= 11) return 30;
  // طول اسفند از فاصله‌ی واقعی نوروز این سال تا نوروز سال بعد (۳۶۵ یا ۳۶۶ روز) به دست می‌آید
  // تا با محاسبه‌ی march در بقیه‌ی توابع این فایل هم‌خوان باشد
  const thisNowruz = new Date(jalCal(jy).gy, 2, jalCal(jy).march);
  const nextNowruz = new Date(jalCal(jy + 1).gy, 2, jalCal(jy + 1).march);
  const daysInYear = Math.round((nextNowruz - thisNowruz) / 86400000);
  return daysInYear === 366 ? 30 : 29;
}

// نام ماه‌های شمسی به ترتیب (اندیس ۰ = فروردین)
export const JALALI_MONTH_NAMES = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
];
