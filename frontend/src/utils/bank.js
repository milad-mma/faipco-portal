// ابزارهای فرم «اطلاعات بانکی» (هم‌سو با backend/app/core/bank_rules.py). اعتبارسنجی اصلی در سرور است.

export const BANK_FIELDS = [
  { key: "account_number", label: "شماره حساب", placeholder: "فقط رقم", maxLength: 24 },
  { key: "sheba", label: "شماره شبا", placeholder: "۲۴ رقم (بدون IR)", maxLength: 24 },
  { key: "card_number", label: "شماره کارت", placeholder: "۱۶ رقم", maxLength: 19 },
];

export const MODE_LABELS = { required: "اجباری", optional: "اختیاری", hidden: "نمایش داده نشود" };

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";

// ارقام فارسی/عربی به لاتین و حذف فاصله، خط تیره، نقطه و نیم‌فاصله
export function cleanBankValue(value) {
  return String(value ?? "")
    .replace(/[۰-۹]/g, (d) => String(FA_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(AR_DIGITS.indexOf(d)))
    .replace(/[\s\-_./\u200c\u200e\u200f]/g, "")
    .toUpperCase();
}

// ورودی شبا: کاربر فقط ۲۴ رقم وارد می‌کند و «IR» ثابت کنار فیلد است؛ اگر با IR چسبانده شود، IR حذف می‌شود
export function shebaDigits(value) {
  return cleanBankValue(value).replace(/^IR/, "").replace(/\D/g, "").slice(0, 24);
}

export function normalizeSheba(value) {
  const text = cleanBankValue(value);
  if (/^\d{24}$/.test(text)) return `IR${text}`;
  return text;
}

// رقم کنترل IBAN: چهار نویسه‌ی اول به انتها، حروف به عدد، باقی‌مانده بر ۹۷ = ۱
export function isValidSheba(sheba) {
  if (!/^IR\d{24}$/.test(sheba)) return false;
  const rearranged = sheba.slice(4) + sheba.slice(0, 4);
  const numeric = rearranged.replace(/[A-Z]/g, (ch) => String(ch.charCodeAt(0) - 55));
  let remainder = 0;
  for (const digit of numeric) remainder = (remainder * 10 + Number(digit)) % 97;
  return remainder === 1;
}

export function isValidCard(card) {
  if (!/^\d{16}$/.test(card)) return false;
  let total = 0;
  [...card].reverse().forEach((ch, i) => {
    let d = Number(ch);
    if (i % 2 === 1) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    total += d;
  });
  return total % 10 === 0;
}

// پیام خطای یک فیلد (یا "" اگر درست است)؛ mode: required / optional
export function fieldError(key, rawValue, mode) {
  const value = key === "sheba" ? shebaDigits(rawValue) : cleanBankValue(rawValue);
  if (!value) return mode === "required" ? "الزامی است" : "";
  if (key === "sheba" && value.length !== 24) return `شبا باید ۲۴ رقم باشد (${value.length} رقم وارد شده)`;
  if (key === "sheba" && !isValidSheba(`IR${value}`)) return "شماره شبا نامعتبر است";
  if (key === "card_number" && !isValidCard(value)) return "شماره کارت نامعتبر است";
  if (key === "account_number" && !/^\d{5,20}$/.test(value)) return "فقط رقم، بین ۵ تا ۲۰ رقم";
  return "";
}

// نمایش خواناتر: شبا و کارت در گروه‌های چهارتایی
export function formatBankValue(key, value) {
  if (!value) return "—";
  if (key === "sheba" || key === "card_number") return value.replace(/(.{4})(?=.)/g, "$1 ");
  return value;
}
