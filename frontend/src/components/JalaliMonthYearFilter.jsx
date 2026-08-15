import { MenuItem, Stack, TextField } from "@mui/material";

const JALALI_MONTHS = [
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

/**
 * فیلتر ماه/سال شمسی — مقدار اولیه از پاسخ سرور (که ماه جاری را پیش‌فرض
 * برمی‌گرداند) پر می‌شود، پس نیازی نیست خودِ مرورگر «امروز شمسی» را حساب کند.
 */
export default function JalaliMonthYearFilter({ year, month, onChange, disabled }) {
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
        {JALALI_MONTHS.map((name, index) => (
          <MenuItem key={index + 1} value={index + 1}>
            {name}
          </MenuItem>
        ))}
      </TextField>
      <TextField
        label="سال (شمسی)"
        type="number"
        size="small"
        value={year ?? ""}
        onChange={(e) => onChange({ year: Number(e.target.value), month })}
        disabled={disabled}
        sx={{ width: 110 }}
      />
    </Stack>
  );
}
