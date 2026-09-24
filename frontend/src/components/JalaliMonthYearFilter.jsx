import { MenuItem, Stack, TextField } from "@mui/material";
import { gregorianToJalali, JALALI_MONTH_NAMES } from "../utils/jalaliDate";

// گزینه‌های سال: چند سال اخیر تا سال جاری شمسی (برای گزارش‌های تردد/حضور)؛
// دراپ‌داون به‌جای ورودی عددی آزاد از انتخاب سال نامعتبر جلوگیری می‌کند.
const YEARS_BACK = 3;
const { jy: CURRENT_JALALI_YEAR } = gregorianToJalali(new Date());
const YEAR_OPTIONS = Array.from({ length: YEARS_BACK + 1 }, (_, i) => CURRENT_JALALI_YEAR - YEARS_BACK + i);

/**
 * فیلتر ماه/سال شمسی با دو دراپ‌داون.
 * ورودی: year و month (مقدار اولیه از پاسخ سرور که ماه جاری را پیش‌فرض برمی‌گرداند)، onChange و disabled.
 * خروجی از طریق onChange: شیء {year, month}. تا مشخص نبودن سال، انتخاب ماه غیرفعال است.
 */
export default function JalaliMonthYearFilter({ year, month, onChange, disabled }) {
  // اگر سال فعلی خارج از بازه‌ی پیش‌فرض باشد، به گزینه‌ها اضافه و مرتب می‌شود
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
