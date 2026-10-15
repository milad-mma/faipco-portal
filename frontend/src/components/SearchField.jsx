import { IconButton, InputAdornment, TextField } from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import CloseIcon from "@mui/icons-material/Close";

/**
 * فیلد جست‌وجوی زنده‌ی یک‌شکل برای فهرست‌ها (پرسنل، درخواست‌ها، لاگ‌ها و ...).
 * ورودی: value، onChange(text)، placeholder (پیش‌فرض «جست‌وجوی نام یا کد پرسنلی…»)، label اختیاری، size، sx، autoFocus.
 * آیکون ذره‌بین در ابتدای فیلد و دکمه‌ی پاک‌کردن وقتی متنی هست. تأخیر ارسال به سرور با useDebounced در والد انجام می‌شود.
 */
export const EMPLOYEE_SEARCH_PLACEHOLDER = "جست‌وجوی نام یا کد پرسنلی…";

export default function SearchField({
  value,
  onChange,
  placeholder = EMPLOYEE_SEARCH_PLACEHOLDER,
  label,
  size = "small",
  sx,
  autoFocus = false,
  fullWidth = true,
  ...props
}) {
  return (
    <TextField
      {...props}
      size={size}
      fullWidth={fullWidth}
      label={label}
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      autoFocus={autoFocus}
      sx={sx}
      InputProps={{
        startAdornment: (
          <InputAdornment position="start">
            <SearchIcon fontSize="small" color="action" />
          </InputAdornment>
        ),
        endAdornment: value ? (
          <InputAdornment position="end">
            <IconButton
              size="small"
              aria-label="پاک کردن جست‌وجو"
              onClick={() => onChange("")}
              edge="end"
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          </InputAdornment>
        ) : undefined,
      }}
    />
  );
}
