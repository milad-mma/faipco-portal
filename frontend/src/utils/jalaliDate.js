/**
 * تبدیل تاریخ شمسی (جلالی) <-> میلادی — بدون نیاز به هیچ کتابخانه خارجی.
 * الگوریتم استاندارد و شناخته‌شده (مبتنی بر همان الگوریتمی که در پروژه‌های
 * متن‌باز رایج مثل jalaali-js استفاده می‌شود).
 */

const JALALI_BREAKS = [
  -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192,
  2262, 2324, 2394, 2456, 3178,
];

function div(a, b) {
  return ~~(a / b);
}

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
  // روز‌شمار از ابتدای سال شمسی (۰-پایه) — ماه‌های ۱ تا ۶ هرکدام ۳۱ روز،
  // ماه‌های ۷ تا ۱۲ هرکدام ۳۰ روز (اسفند در سال کبیسه هم همینجا حساب می‌شود)
  const jdays = jm <= 6 ? (jm - 1) * 31 + (jd - 1) : 186 + (jm - 7) * 30 + (jd - 1);
  const gDate = new Date(gy, 2, march); // نوروز همان سال شمسی (حوالی ۲۰-۲۱ مارس میلادی)
  gDate.setDate(gDate.getDate() + jdays);
  gDate.setHours(hour, minute, 0, 0);
  return gDate;
}

/** شیء Date میلادی → {jy, jm, jd} شمسی */
export function gregorianToJalali(date) {
  const gy = date.getFullYear();
  // برای پیداکردن سال شمسی، از سال میلادی فعلی و قبلی هردو march را حساب و مقایسه می‌کنیم
  for (const candidateJy of [gy - 622, gy - 621, gy - 620]) {
    const r = jalCal(candidateJy);
    const march = r.march;
    const marchDate = new Date(r.gy, 2, march);
    const nextR = jalCal(candidateJy + 1);
    const nextMarchDate = new Date(nextR.gy, 2, nextR.march);
    if (date >= marchDate && date < nextMarchDate) {
      const diffDays = Math.round((date - marchDate) / 86400000);
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
  // نباید هرگز به اینجا برسد؛ Fallback ایمن
  return { jy: gy - 621, jm: 1, jd: 1 };
}

export function jalaliMonthLength(jy, jm) {
  if (jm <= 6) return 31;
  if (jm <= 11) return 30;
  // به‌جای تکیه بر فرمول جداگانه‌ی «سال کبیسه» (که می‌تواند با محاسبه march
  // ناهم‌خوان شود)، مستقیماً فاصله واقعی نوروز این سال تا نوروز سال بعد را
  // حساب می‌کنیم — همیشه با باقی محاسبات این فایل سازگار می‌ماند.
  const thisNowruz = new Date(jalCal(jy).gy, 2, jalCal(jy).march);
  const nextNowruz = new Date(jalCal(jy + 1).gy, 2, jalCal(jy + 1).march);
  const daysInYear = Math.round((nextNowruz - thisNowruz) / 86400000);
  return daysInYear === 366 ? 30 : 29;
}

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
