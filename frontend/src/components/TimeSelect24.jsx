import { MenuItem, Stack, TextField } from "@mui/material";

const HOURS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0"));
const MINUTES = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, "0"));

/**
 * ⚠️ طبق درخواست صریح کاربر: ورودی ساعت باید همیشه ۲۴ ساعته باشد -
 * ورودی بومی مرورگر (<input type="time">) به زبان/سیستم‌عامل کاربر
 * وابسته است و گاهی به‌صورت ۱۲ ساعته (AM/PM) نمایش داده می‌شود؛ این
 * کامپوننت با دو Dropdown مستقل (ساعت ۰۰ تا ۲۳، دقیقه ۰۰ تا ۵۹) این
 * وابستگی را کاملاً حذف می‌کند. مقدار ورودی/خروجی همان رشته "HH:MM"ی
 * است که کد بقیه پروژه (timeStringToCompact) از قبل انتظار دارد - تا
 * جایگزینی بدون تغییر منطق اطراف ممکن باشد.
 */
export default function TimeSelect24({ value, onChange, label, size = "small", sx }) {
  const [hourStr, minuteStr] = (value || "00:00").split(":");

  function handleHourChange(newHour) {
    onChange(`${newHour}:${minuteStr}`);
  }

  function handleMinuteChange(newMinute) {
    onChange(`${hourStr}:${newMinute}`);
  }

  return (
    <Stack spacing={0.5} sx={sx}>
      {label && (
        <Stack direction="row" sx={{ color: "text.secondary", fontSize: 13 }}>
          {label}
        </Stack>
      )}
      <Stack direction="row" spacing={1}>
        {/* ⚠️ طبق درخواست صریح کاربر: ساعت سمت چپ، دقیقه سمت راست. چون
            صفحه RTL است، اولین عنصر در DOM سمت راست رندر می‌شود - پس
            «دقیقه» عمداً اول آمده تا «ساعت» سمت چپ بیفتد. */}
        <TextField
          select
          size={size}
          label="دقیقه"
          value={minuteStr}
          onChange={(e) => handleMinuteChange(e.target.value)}
          sx={{ minWidth: 90 }}
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
          sx={{ minWidth: 90 }}
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
