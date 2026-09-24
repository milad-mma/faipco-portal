import { useState } from "react";
import { IconButton, Stack, TextField, Typography } from "@mui/material";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import CheckOutlinedIcon from "@mui/icons-material/CheckOutlined";
import CloseOutlinedIcon from "@mui/icons-material/CloseOutlined";

/**
 * ویرایش درجای عنوان: کلیک روی آیکون مداد، عنوان را به TextField تبدیل می‌کند (ذخیره با Enter یا تیک،
 * انصراف با Escape یا ضربدر). برای عنوان «دوره‌های ارزیابی» و «فرم‌های ارزیابی» استفاده می‌شود.
 * ورودی: title، onSave (async، با عنوان trim‌شده صدا زده می‌شود)، variant و fontWeight متن.
 * این کامپوننت محدودیتی اعمال نمی‌کند؛ مجاز بودن ویرایش سمت Backend بررسی می‌شود.
 */
export default function InlineTitleEdit({ title, onSave, variant = "body1", fontWeight }) {
  const [isEditing, setIsEditing] = useState(false);
  const [value, setValue] = useState(title); // مقدار در حال ویرایش
  const [isSaving, setIsSaving] = useState(false);

  // ورود به حالت ویرایش با مقدار فعلی عنوان
  function startEdit() {
    setValue(title);
    setIsEditing(true);
  }

  // ذخیره‌ی عنوان؛ مقدار خالی یا بدون تغییر فقط حالت ویرایش را می‌بندد.
  // در صورت خطای onSave حالت ویرایش باز می‌ماند
  async function handleSave() {
    if (!value.trim() || value === title) {
      setIsEditing(false);
      return;
    }
    setIsSaving(true);
    try {
      await onSave(value.trim());
      setIsEditing(false);
    } finally {
      setIsSaving(false);
    }
  }

  // حالت ویرایش: فیلد متن و دکمه‌های تأیید/انصراف
  if (isEditing) {
    return (
      <Stack direction="row" spacing={0.5} alignItems="center">
        <TextField
          size="small"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSave();
            if (e.key === "Escape") setIsEditing(false);
          }}
          autoFocus
          disabled={isSaving}
        />
        <IconButton size="small" color="primary" onClick={handleSave} disabled={isSaving}>
          <CheckOutlinedIcon fontSize="small" />
        </IconButton>
        <IconButton size="small" onClick={() => setIsEditing(false)} disabled={isSaving}>
          <CloseOutlinedIcon fontSize="small" />
        </IconButton>
      </Stack>
    );
  }

  // حالت نمایش: عنوان و آیکون مداد
  return (
    <Stack direction="row" spacing={0.5} alignItems="center">
      <Typography variant={variant} fontWeight={fontWeight}>
        {title}
      </Typography>
      <IconButton size="small" onClick={startEdit}>
        <EditOutlinedIcon fontSize="inherit" />
      </IconButton>
    </Stack>
  );
}
