/**
 * نام فرستنده‌ی «ناشناس» برای کسی که اجازه‌ی دیدن نام را دارد (مثلاً ادمین): پیش‌فرض فقط «ناشناس» با آیکون قفل نمایش
 * داده می‌شود و نام فقط با کلیک (عمدی) آشکار می‌شود؛ کلیک دوباره دوباره پنهانش می‌کند. کلیک به والد (باز شدن کارت/گفتگو)
 * نمی‌رسد. ورودی: name (نام واقعی)، variant/fontWeight تایپوگرافی.
 */
import { useState } from "react";
import { Box, Tooltip } from "@mui/material";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import LockOpenOutlinedIcon from "@mui/icons-material/LockOpenOutlined";

export default function AnonymousName({ name }) {
  const [revealed, setRevealed] = useState(false);
  return (
    <Tooltip title={revealed ? "پنهان کردن نام" : "فرستنده درخواست ناشناس ماندن داشته؛ برای دیدن نام کلیک کنید"}>
      <Box
        component="span"
        role="button"
        tabIndex={0}
        onClick={(e) => {
          e.stopPropagation();
          setRevealed((v) => !v);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            e.stopPropagation();
            setRevealed((v) => !v);
          }
        }}
        sx={{
          display: "inline-flex",
          alignItems: "center",
          gap: 0.4,
          cursor: "pointer",
          borderBottom: "1px dashed",
          borderColor: "text.disabled",
          "& svg": { fontSize: "1em", opacity: 0.7 },
        }}
      >
        {revealed ? <LockOpenOutlinedIcon /> : <LockOutlinedIcon />}
        {revealed ? `${name} (ناشناس)` : "ناشناس"}
      </Box>
    </Tooltip>
  );
}
