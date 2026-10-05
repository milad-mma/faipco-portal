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
const ACCEPT = "image/*,application/pdf,.pdf,.jpg,.jpeg,.png,.webp,.gif,.bmp,.tif,.tiff";

const isPdfFile = (file) => file.type === "application/pdf" || /\.pdf$/i.test(file.name || "");

/**
 * نوع واقعی فایل را از بایت‌های ابتدایی می‌خواند (همان قاعده‌ی سرور) تا فایل نامعتبر همان لحظه‌ی انتخاب، با نام، رد شود
 * — نه بعد از ارسال. خروجی: null اگر مجاز است، وگرنه متن خطا.
 */
async function checkFileContent(file) {
  const head = new Uint8Array(await file.slice(0, 1024).arrayBuffer());
  const ascii = (from, to) => String.fromCharCode(...head.slice(from, to));
  const startsWith = (...bytes) => bytes.every((b, i) => head[i] === b);
  if (ascii(0, head.length).includes("%PDF-")) return null;
  if (startsWith(0xff, 0xd8, 0xff) || startsWith(0x89, 0x50, 0x4e, 0x47)) return null; // JPEG / PNG
  if (ascii(0, 6) === "GIF87a" || ascii(0, 6) === "GIF89a") return null;
  if (ascii(0, 4) === "RIFF" && ascii(8, 12) === "WEBP") return null;
  if (ascii(0, 2) === "BM" || startsWith(0x49, 0x49, 0x2a, 0x00) || startsWith(0x4d, 0x4d, 0x00, 0x2a)) return null; // BMP / TIFF
  if (ascii(4, 8) === "ftyp" && ["heic", "heix", "hevc", "heim", "heis", "mif1", "msf1", "avif"].includes(ascii(8, 12))) {
    return `«${file.name}» عکس HEIC (فرمت دوربین آیفون) است و پشتیبانی نمی‌شود؛ آن را به JPG تبدیل کنید.`;
  }
  return `محتوای «${file.name}» تصویر یا PDF نیست (ممکن است فقط پسوندش تغییر کرده باشد).`;
}

export function formatFileSize(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024)).toLocaleString("fa-IR")} کیلوبایت`;
  return `${(bytes / (1024 * 1024)).toLocaleString("fa-IR", { maximumFractionDigits: 1 })} مگابایت`;
}

export default function NoticeAttachmentPicker({ files, onChange, disabled }) {
  const inputRef = useRef(null);
  const [error, setError] = useState("");

  async function handleSelect(e) {
    const picked = Array.from(e.target.files || []);
    e.target.value = ""; // انتخاب دوباره‌ی همان فایل هم کار کند
    setError("");
    const next = [...files];
    const problems = [];
    for (const file of picked) {
      if (next.length >= NOTICE_ATTACHMENT_MAX_COUNT) {
        problems.push(`حداکثر ${NOTICE_ATTACHMENT_MAX_COUNT.toLocaleString("fa-IR")} فایل مجاز است.`);
        break;
      }
      if (file.size > NOTICE_ATTACHMENT_MAX_BYTES) {
        problems.push(`حجم «${file.name}» بیشتر از ۱۰ مگابایت است.`);
        continue;
      }
      const problem = await checkFileContent(file).catch(() => `خواندن «${file.name}» ممکن نشد.`);
      if (problem) {
        problems.push(problem);
        continue;
      }
      next.push(file);
    }
    onChange(next);
    if (problems.length) setError(problems.join("\n"));
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
        <Alert severity="warning" sx={{ mt: 1, whiteSpace: "pre-line" }} onClose={() => setError("")}>
          {error}
        </Alert>
      )}
    </Box>
  );
}
