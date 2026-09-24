import { MenuItem, Stack, TextField } from "@mui/material";

const HOURS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));  // گزینه‌های ساعت ۰۰ تا ۲۳
const MINUTES = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, "0"));  // گزینه‌های دقیقه ۰۰ تا ۵۹

/**
 * ورودی ساعت همیشه ۲۴ ساعته با دو Dropdown مستقل (ساعت و دقیقه)، مستقل از زبان/سیستم‌عامل کاربر
 * (برخلاف <input type="time"> که ممکن است ۱۲ ساعته نمایش داده شود).
 * ورودی: value و onChange با رشته‌ی "HH:MM" (همان قالبی که timeStringToCompact انتظار دارد)، label، size، sx
 * و align ("center" برای وسط‌چین).
 */
export default function TimeSelect24({ value, onChange, label, size = "small", sx, align }) {
  const [hourStr, minuteStr] = (value || "00:00").split(":");  // مقدار خالی معادل 00:00

  // تغییر ساعت با حفظ دقیقه‌ی فعلی
  function handleHourChange(newHour) {
    onChange(`${newHour}:${minuteStr}`);
  }

  // تغییر دقیقه با حفظ ساعت فعلی
  function handleMinuteChange(newMinute) {
    onChange(`${hourStr}:${newMinute}`);
  }

  // align="center": برچسب و فیلدها وسط‌چین می‌شوند
  const centered = align === "center";
  return (
    <Stack
      spacing={0.5}
      alignItems={centered ? "center" : undefined}
      sx={centered ? { "& .MuiSelect-select": { textAlign: "center" }, ...sx } : sx}
    >
      {label && (
        <Stack direction="row" sx={{ color: "text.secondary", fontSize: 13 }}>
          {label}
        </Stack>
      )}
      <Stack direction="row" spacing={1} sx={{ width: "100%" }}>
        {/* ساعت سمت چپ و دقیقه سمت راست: چون صفحه RTL است و اولین عنصر DOM سمت راست رندر می‌شود،
            «دقیقه» اول آمده است. */}
        <TextField
          select
          size={size}
          label="دقیقه"
          value={minuteStr}
          onChange={(e) => handleMinuteChange(e.target.value)}
          sx={{ flex: 1, minWidth: 72 }}
        >
          {MINUTES.map((m) => (
            <MenuItem key={m} value={m}>
              {m}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size={size}
          label="ساعت"
          value={hourStr}
          onChange={(e) => handleHourChange(e.target.value)}
          sx={{ flex: 1, minWidth: 72 }}
        >
          {HOURS.map((h) => (
            <MenuItem key={h} value={h}>
              {h}
            </MenuItem>
          ))}
        </TextField>
      </Stack>
    </Stack>
  );
}
