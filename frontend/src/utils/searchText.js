/**
 * یکسان‌سازی متن جست‌وجو: کاربر با کیبورد فارسی یا عربی هم مقادیری را که با ارقام لاتین
 * (و حروف فارسی) ذخیره شده‌اند پیدا کند. هم‌تای backend/app/core/text_normalize.py.
 * - ارقام فارسی (۰-۹) و عربی (٠-٩) ← لاتین
 * - «ي»، «ى» و «ك» عربی ← «ی» و «ک» فارسی
 * - حذف کاراکترهای نامرئی (به جز نیم‌فاصله)
 * برای رمز عبور استفاده نمی‌شود.
 */
const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";

// متن یکسان‌شده (بدون تغییر حروف بزرگ/کوچک و فاصله‌ها)
export function normalizeSearchText(value) {
  return String(value ?? "")
    .replace(/[۰-۹]/g, (d) => String(FA_DIGITS.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String(AR_DIGITS.indexOf(d)))
    .replace(/[يى]/g, "ی")
    .replace(/ك/g, "ک")
    .replace(/[​‍‎‏﻿]/g, "");
}

// کلید مقایسه برای جست‌وجوی سمت کلاینت: یکسان‌شده، بدون فاصله‌ی ابتدا/انتها و با حروف کوچک
export function searchKey(value) {
  return normalizeSearchText(value).trim().toLowerCase();
}

// آیا یکی از فیلدها عبارت جست‌وجو را دارد؟ (term خالی = همه)
export function matchesSearch(term, fields) {
  const key = searchKey(term);
  if (!key) return true;
  return fields.some((field) => field !== null && field !== undefined && searchKey(field).includes(key));
}

/**
 * جایگزین filterOptions پیش‌فرض MUI Autocomplete؛ پیش‌فرض MUI متن تایپ‌شده را خام با برچسب گزینه
 * مقایسه می‌کند و «۱۲۳» گزینه‌ی «(123)» را حذف می‌کرد. برای کادرهایی که نتیجه را از سرور می‌گیرند هم
 * لازم است، چون MUI نتایج سرور را دوباره فیلتر می‌کند.
 */
export function searchFilterOptions(options, { inputValue, getOptionLabel }) {
  const key = searchKey(inputValue);
  if (!key) return options;
  return options.filter((option) => searchKey(getOptionLabel(option)).includes(key));
}

// ارقام لاتین (و عربی) را برای نمایش به ارقام فارسی تبدیل می‌کند؛ مقدار ذخیره‌شده لاتین می‌ماند
export function toPersianDigits(value) {
  return normalizeSearchText(value).replace(/[0-9]/g, (d) => FA_DIGITS[Number(d)]);
}
