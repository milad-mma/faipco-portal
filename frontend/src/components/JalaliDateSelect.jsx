import { MenuItem, Stack, TextField } from "@mui/material";
import { gregorianToJalali, jalaliMonthLength, JALALI_MONTH_NAMES } from "../utils/jalaliDate";

// چند سال اخیر تا سال جاری شمسی - همان بازه استفاده‌شده در JalaliMonthYearFilter.jsx
const YEARS_BACK = 3;
const { jy: CURRENT_JALALI_YEAR } = gregorianToJalali(new Date());
const YEAR_OPTIONS = Array.from({ length: YEARS_BACK + 1 }, (_, i) => CURRENT_JALALI_YEAR - YEARS_BACK + i);

/**
 * انتخاب تاریخ شمسی با سه دراپ‌داون مستقل (روز/ماه/سال) - برای فیلترهای
 * گزارش که یک تاریخ کامل (نه فقط ماه/سال) لازم دارند. مقدار خروجی
 * ({year, month, day}) فقط وقتی هر سه مقدار پر باشند «کامل» تلقی می‌شود؛
 * فراخوان مسئول تصمیم‌گیری درباره مقادیر ناقص است.
 */
export default function JalaliDateSelect({ year, month, day, onChange, disabled }) {
  const dayCount = year && month ? jalaliMonthLength(year, month) : 31;
  const dayOptions = Array.from({ length: dayCount }, (_, i) => i + 1);

  function handleYearChange(newYear) {
    onChange({ year: newYear, month, day });
  }

  function handleMonthChange(newMonth) {
    // اگر روز انتخاب‌شده از تعداد روزهای ماه جدید بیشتر باشد (مثلاً ۳۱ در
    // ماهی که فقط ۳۰ روز دارد)، به آخرین روز معتبر همان ماه محدود می‌شود.
    const maxDay = year ? jalaliMonthLength(year, newMonth) : 31;
    onChange({ year, month: newMonth, day: day && day > maxDay ? maxDay : day });
  }

  function handleDayChange(newDay) {
    onChange({ year, month, day: newDay });
  }

  return (
    <Stack direction="row" spacing={1}>
      <TextField
        select
        size="small"
        label="روز"
        value={day ?? ""}
        onChange={(e) => handleDayChange(e.target.value ? Number(e.target.value) : null)}
        disabled={disabled}
        sx={{ width: 80 }}
      >
        <MenuItem value="">—</MenuItem>
        {dayOptions.map((d) => (
          <MenuItem key={d} value={d}>
            {d}
          </MenuItem>
        ))}
      </TextField>
      <TextField
        select
        size="small"
        label="ماه"
        value={month ?? ""}
        onChange={(e) => handleMonthChange(e.target.value ? Number(e.target.value) : null)}
        disabled={disabled}
        sx={{ minWidth: 110 }}
      >
        <MenuItem value="">—</MenuItem>
        {JALALI_MONTH_NAMES.map((name, idx) => (
          <MenuItem key={idx + 1} value={idx + 1}>
            {name}
          </MenuItem>
        ))}
      </TextField>
      <TextField
        select
        size="small"
        label="سال"
        value={year ?? ""}
        onChange={(e) => handleYearChange(e.target.value ? Number(e.target.value) : null)}
        disabled={disabled}
        sx={{ width: 100 }}
      >
        <MenuItem value="">—</MenuItem>
        {YEAR_OPTIONS.map((y) => (
          <MenuItem key={y} value={y}>
            {y}
          </MenuItem>
        ))}
      </TextField>
    </Stack>
  );
}
