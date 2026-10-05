/**
 * انتخاب پیوست برای فرم «اطلاعیه‌ی جدید» (فقط برای دارنده‌ی مجوز notices.attachments).
 * فایل‌ها در مرورگر نگه داشته می‌شوند و بعد از ساخت پیش‌نویس، پیش از انتشار آپلود می‌شوند.
 * اعتبارسنجی اولیه سمت مرورگر (نوع، حجم، تعداد)؛ بررسی اصلی و پاک‌سازی در سرور انجام می‌شود.
 * ورودی: files (آرایه‌ی File)، onChange(files)، disabled.
 */
import { useRef, useState } from "react";
import { Alert, Box, Button, Chip, Stack, Typography } from "@mui/material";
import AttachFileOutlinedIcon from "@mui/icons-material/AttachFileOutlined";
import PictureAsPdfOutlinedIcon from "@mui/icons-material/PictureAsPdfOutlined";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";

export const NOTICE_ATTACHMENT_MAX_COUNT = 5;
export const NOTICE_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024;
const ACCEPT = "image/jpeg,image/png,image/webp,image/gif,application/pdf,.pdf,.jpg,.jpeg,.png,.webp,.gif";
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"]);
const ALLOWED_EXT = /\.(pdf|jpe?g|png|webp|gif)$/i;

// بعضی مرورگرها/سیستم‌عامل‌ها برای PDF نوع خالی یا application/x-pdf می‌دهند؛ پسوند هم پذیرفته می‌شود (بررسی اصلی در سرور)
const isAllowedFile = (file) => ALLOWED_TYPES.has(file.type) || ALLOWED_EXT.test(file.name || "");
const isPdfFile = (file) => file.type === "application/pdf" || /\.pdf$/i.test(file.name || "");

export function formatFileSize(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024)).toLocaleString("fa-IR")} کیلوبایت`;
  return `${(bytes / (1024 * 1024)).toLocaleString("fa-IR", { maximumFractionDigits: 1 })} مگابایت`;
}

export default function NoticeAttachmentPicker({ files, onChange, disabled }) {
  const inputRef = useRef(null);
  const [error, setError] = useState("");

  function handleSelect(e) {
    const picked = Array.from(e.target.files || []);
    e.target.value = ""; // انتخاب دوباره‌ی همان فایل هم کار کند
    setError("");
    const next = [...files];
    for (const file of picked) {
      if (next.length >= NOTICE_ATTACHMENT_MAX_COUNT) {
        setError(`حداکثر ${NOTICE_ATTACHMENT_MAX_COUNT.toLocaleString("fa-IR")} فایل مجاز است.`);
        break;
      }
      if (!isAllowedFile(file)) {
        setError(`«${file.name}» پذیرفته نیست؛ فقط تصویر (JPG، PNG، WEBP، GIF) یا PDF.`);
        continue;
      }
      if (file.size > NOTICE_ATTACHMENT_MAX_BYTES) {
        setError(`حجم «${file.name}» بیشتر از ۱۰ مگابایت است.`);
        continue;
      }
      next.push(file);
    }
    onChange(next);
  }

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
        <Button
          variant="outlined"
          size="small"
          startIcon={<AttachFileOutlinedIcon />}
          onClick={() => inputRef.current?.click()}
          disabled={disabled || files.length >= NOTICE_ATTACHMENT_MAX_COUNT}
        >
          افزودن تصویر یا PDF
        </Button>
        <Typography variant="caption" color="text.secondary">
          حداکثر {NOTICE_ATTACHMENT_MAX_COUNT.toLocaleString("fa-IR")} فایل، هر کدام تا ۱۰ مگابایت
        </Typography>
        <input ref={inputRef} type="file" hidden multiple accept={ACCEPT} onChange={handleSelect} />
      </Stack>
      {files.length > 0 && (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
          {files.map((file, i) => (
            <Chip
              key={`${file.name}-${i}`}
              icon={isPdfFile(file) ? <PictureAsPdfOutlinedIcon /> : <ImageOutlinedIcon />}
              label={`${file.name} — ${formatFileSize(file.size)}`}
              onDelete={disabled ? undefined : () => onChange(files.filter((_, j) => j !== i))}
              variant="outlined"
              sx={{ maxWidth: "100%" }}
            />
          ))}
        </Stack>
      )}
      {error && (
        <Alert severity="warning" sx={{ mt: 1 }} onClose={() => setError("")}>
          {error}
        </Alert>
      )}
    </Box>
  );
}
