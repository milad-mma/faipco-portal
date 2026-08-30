import { MenuItem, Stack, TextField } from "@mui/material";
import { gregorianToJalali, JALALI_MONTH_NAMES } from "../utils/jalaliDate";

// چند سال اخیر تا سال جاری شمسی - برای گزارش‌های تردد/حضور، معمولاً
// نیازی به بازه‌ای فراتر از چند سال گذشته نیست؛ دراپ‌داون به‌جای ورودی
// عددی آزاد، از انتخاب سالِ نامعتبر (مثلاً یک رقمی یا خیلی بزرگ) جلوگیری می‌کند.
const YEARS_BACK = 3;
const { jy: CURRENT_JALALI_YEAR } = gregorianToJalali(new Date());
const YEAR_OPTIONS = Array.from({ length: YEARS_BACK + 1 }, (_, i) => CURRENT_JALALI_YEAR - YEARS_BACK + i);

/**
 * فیلتر ماه/سال شمسی - مقدار اولیه از پاسخ سرور (که ماه جاری را پیش‌فرض
 * برمی‌گرداند) پر می‌شود، پس نیازی نیست خودِ مرورگر «امروز شمسی» را حساب کند
 * (فقط برای محاسبه بازه دراپ‌داون سال، که مستقل از مقدار انتخاب‌شده است).
 */
export default function JalaliMonthYearFilter({ year, month, onChange, disabled }) {
  const yearOptions = YEAR_OPTIONS.includes(year)
    ? YEAR_OPTIONS
    : [...YEAR_OPTIONS, year].filter((y) => y != null).sort((a, b) => a - b);

  return (
    <Stack direction="row" spacing={1.5}>
      <TextField
        select
        label="ماه"
        size="small"
        value={month ?? ""}
        onChange={(e) => onChange({ year, month: Number(e.target.value) })}
        disabled={disabled || year == null}
        sx={{ minWidth: 130 }}
      >
        {JALALI_MONTH_NAMES.map((name, index) => (
          <MenuItem key={index + 1} value={index + 1}>
            {name}
          </MenuItem>
        ))}
      </TextField>
      <TextField
        select
        label="سال (شمسی)"
        size="small"
        value={year ?? ""}
        onChange={(e) => onChange({ year: Number(e.target.value), month })}
        disabled={disabled}
        sx={{ width: 120 }}
      >
        {yearOptions.map((y) => (
          <MenuItem key={y} value={y}>
            {y}
          </MenuItem>
        ))}
      </TextField>
    </Stack>
  );
}
