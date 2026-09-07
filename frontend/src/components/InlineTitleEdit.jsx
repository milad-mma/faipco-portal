import { useState } from "react";
import { IconButton, Stack, TextField, Typography } from "@mui/material";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import CheckOutlinedIcon from "@mui/icons-material/CheckOutlined";
import CloseOutlinedIcon from "@mui/icons-material/CloseOutlined";

/**
 * ویرایش inline عنوان (کلیک روی آیکون مداد → تبدیل به TextField → ذخیره
 * یا انصراف) - برای «دوره‌های ارزیابی»/«فرم‌های ارزیابی»، طبق تصمیم صریح
 * پروژه، عنوان صرف‌نظر از وضعیت (حتی بعد از فعال‌شدن) همیشه قابل‌ویرایش
 * است - این کامپوننت هیچ محدودیتی خودش اعمال نمی‌کند، فقط UI ویرایش را
 * فراهم می‌کند؛ منطق مجاز/غیرمجاز بودن کاملاً سمت Backend است.
 */
export default function InlineTitleEdit({ title, onSave, variant = "body1", fontWeight }) {
  const [isEditing, setIsEditing] = useState(false);
  const [value, setValue] = useState(title);
  const [isSaving, setIsSaving] = useState(false);

  function startEdit() {
    setValue(title);
    setIsEditing(true);
  }

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
