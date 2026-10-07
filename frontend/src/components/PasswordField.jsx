/**
 * فیلد رمز عبور با دکمه‌ی «نمایش/پنهان کردن» (چشم) — همان رفتار صفحه‌ی ورود، برای همه‌ی فرم‌های رمز
 * (فراموشی رمز، بازنشانی با لینک، تغییر رمز). بقیه‌ی props مستقیم به TextField می‌رسد.
 *
 * show/onToggle اختیاری: اگر داده شوند، چند فیلد (رمز و تکرارش) با یک دکمه با هم نمایش داده می‌شوند؛
 * وگرنه هر فیلد وضعیت خودش را دارد. hideToggle: فیلد از وضعیت بیرونی پیروی می‌کند ولی خودش دکمه ندارد.
 */
import { useState } from "react";
import { IconButton, InputAdornment, TextField } from "@mui/material";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import VisibilityOffOutlinedIcon from "@mui/icons-material/VisibilityOffOutlined";

export default function PasswordField({ show, onToggle, hideToggle = false, InputProps, ...props }) {
  const [own, setOwn] = useState(false);
  const visible = show ?? own;
  const toggle = onToggle ?? (() => setOwn((v) => !v));
  return (
    <TextField
      {...props}
      type={visible ? "text" : "password"}
      InputProps={{
        ...InputProps,
        endAdornment: hideToggle ? (
          InputProps?.endAdornment
        ) : (
          <InputAdornment position="end">
            <IconButton
              size="small"
              edge="end"
              onClick={toggle}
              aria-label={visible ? "پنهان کردن رمز عبور" : "نمایش رمز عبور"}
              tabIndex={-1}
            >
              {visible ? <VisibilityOffOutlinedIcon fontSize="small" /> : <VisibilityOutlinedIcon fontSize="small" />}
            </IconButton>
          </InputAdornment>
        ),
      }}
    />
  );
}
