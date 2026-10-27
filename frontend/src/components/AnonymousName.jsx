/**
 * نام فرستنده‌ی «ناشناس» برای کسی که اجازه‌ی دیدن نام را دارد (مثلاً ادمین): ظاهر کاملاً مثل متن عادی «ناشناس» است —
 * بدون راهنمای هاور، بدون نشانگر دست، بدون خط‌چین و آیکون — و نام فقط با کلیک روی همین کلمه آشکار می‌شود؛ کلیک دوباره
 * پنهانش می‌کند. کلیک به والد (باز شدن کارت/گفتگو) نمی‌رسد. ورودی: name (نام واقعی).
 */
import { useState } from "react";
import { Box } from "@mui/material";

export default function AnonymousName({ name }) {
  const [revealed, setRevealed] = useState(false);
  return (
    <Box
      component="span"
      onClick={(e) => {
        e.stopPropagation();
        setRevealed((v) => !v);
      }}
      sx={{ cursor: "text", userSelect: "none" }}
    >
      {revealed ? `${name} (ناشناس)` : "ناشناس"}
    </Box>
  );
}
