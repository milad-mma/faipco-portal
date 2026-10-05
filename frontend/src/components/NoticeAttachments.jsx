/**
 * باکس «پیوست‌ها» در اطلاعیه: هر فایل یک لینک (نام + حجم) است و چیزی از قبل بارگذاری نمی‌شود.
 * با کلیک، فایل با توکن کاربر گرفته می‌شود و در لایت‌باکس نمایش داده می‌شود: تصویر بزرگ، PDF داخل نمایشگر مرورگر
 * (روی گوشی که نمایشگر داخلی PDF ندارد، فقط دکمه‌ی دانلود). در هر دو حالت دکمه‌ی «دانلود» هست.
 * ورودی: items ([{ id, file_name, content_type, size_bytes }]).
 */
import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  IconButton,
  Link,
  Stack,
  Typography,
  useMediaQuery,
} from "@mui/material";
import AttachFileOutlinedIcon from "@mui/icons-material/AttachFileOutlined";
import PictureAsPdfOutlinedIcon from "@mui/icons-material/PictureAsPdfOutlined";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import CloseIcon from "@mui/icons-material/Close";
import { fetchNoticeAttachmentBlob } from "../api/notices";
import { formatFileSize } from "./NoticeAttachmentPicker";

// دانلود یک Blob با نام داده‌شده (در PWA نصب‌شده هم کار می‌کند؛ مثل فیش حقوقی)
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/** لایت‌باکس یک پیوست؛ item=null یعنی بسته. */
function AttachmentLightbox({ item, onClose }) {
  const [state, setState] = useState({ url: null, blob: null, error: "" });
  // نمایشگر داخلی PDF روی مرورگرهای گوشی (به‌خصوص اندروید) وجود ندارد
  const isSmallScreen = useMediaQuery("(max-width:900px)");
  const isPdf = item?.content_type === "application/pdf";

  useEffect(() => {
    if (!item) return undefined;
    let objectUrl = null;
    let cancelled = false;
    setState({ url: null, blob: null, error: "" });
    fetchNoticeAttachmentBlob(item.id)
      .then((data) => {
        if (cancelled) return;
        const blob = new Blob([data], { type: item.content_type });
        objectUrl = URL.createObjectURL(blob);
        setState({ url: objectUrl, blob, error: "" });
      })
      .catch(() => !cancelled && setState({ url: null, blob: null, error: "دریافت فایل ممکن نشد." }));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [item]);

  return (
    <Dialog
      open={Boolean(item)}
      onClose={onClose}
      maxWidth={isPdf ? "lg" : "md"}
      fullWidth={isPdf}
      PaperProps={{ sx: { bgcolor: isPdf ? "background.paper" : "#111", overflow: "hidden" } }}
    >
      {/* نوار بالا: نام فایل، دانلود، بستن */}
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        sx={{ px: 1.5, py: 1, bgcolor: "rgba(0,0,0,0.75)", color: "white" }}
      >
        <Typography variant="body2" fontWeight={700} noWrap sx={{ flexGrow: 1, minWidth: 0 }}>
          {item?.file_name}
        </Typography>
        <Button
          size="small"
          variant="contained"
          color="inherit"
          startIcon={<FileDownloadOutlinedIcon />}
          disabled={!state.blob}
          onClick={() => state.blob && downloadBlob(state.blob, item.file_name)}
          sx={{ color: "black", bgcolor: "white", "&:hover": { bgcolor: "#e0e0e0" } }}
        >
          دانلود
        </Button>
        <IconButton onClick={onClose} sx={{ color: "white" }} aria-label="بستن">
          <CloseIcon />
        </IconButton>
      </Stack>

      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: 240,
          ...(isPdf && !isSmallScreen ? { height: "80vh" } : {}),
        }}
      >
        {state.error ? (
          <Alert severity="error" sx={{ m: 2 }}>
            {state.error}
          </Alert>
        ) : !state.url ? (
          <CircularProgress sx={{ color: isPdf ? undefined : "white" }} />
        ) : isPdf ? (
          isSmallScreen ? (
            <Stack spacing={2} alignItems="center" sx={{ p: 3, textAlign: "center" }}>
              <PictureAsPdfOutlinedIcon color="error" sx={{ fontSize: 56 }} />
              <Typography variant="body2" color="text.secondary">
                نمایش PDF داخل صفحه روی گوشی ممکن نیست؛ با دکمه‌ی «دانلود» فایل را باز کنید.
              </Typography>
              <Button
                variant="contained"
                startIcon={<FileDownloadOutlinedIcon />}
                onClick={() => downloadBlob(state.blob, item.file_name)}
              >
                دانلود {formatFileSize(item.size_bytes)}
              </Button>
            </Stack>
          ) : (
            <Box component="iframe" src={state.url} title={item.file_name} sx={{ width: "100%", height: "100%", border: 0 }} />
          )
        ) : (
          <Box
            component="img"
            src={state.url}
            alt={item.file_name}
            sx={{ display: "block", maxWidth: "90vw", maxHeight: "80vh" }}
          />
        )}
      </Box>
    </Dialog>
  );
}

export default function NoticeAttachments({ items }) {
  const [open, setOpen] = useState(null); // پیوستی که لایت‌باکسش باز است
  if (!items?.length) return null;

  return (
    <Box sx={{ mt: 1.5, p: 1.25, borderRadius: 2, border: 1, borderColor: "divider", bgcolor: "action.hover" }}>
      <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 0.75 }}>
        <AttachFileOutlinedIcon fontSize="small" sx={{ color: "text.secondary" }} />
        <Typography variant="caption" fontWeight={800} color="text.secondary">
          پیوست‌ها
        </Typography>
      </Stack>
      <Stack spacing={0.5}>
        {items.map((item) => (
          <Stack key={item.id} direction="row" spacing={0.75} alignItems="center" sx={{ minWidth: 0 }}>
            {item.content_type === "application/pdf" ? (
              <PictureAsPdfOutlinedIcon fontSize="small" color="error" />
            ) : (
              <ImageOutlinedIcon fontSize="small" color="primary" />
            )}
            <Link
              component="button"
              type="button"
              variant="body2"
              underline="hover"
              onClick={(e) => {
                e.stopPropagation();
                setOpen(item);
              }}
              sx={{ textAlign: "start", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", minWidth: 0 }}
            >
              {item.file_name}
            </Link>
            <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
              ({formatFileSize(item.size_bytes)})
            </Typography>
          </Stack>
        ))}
      </Stack>
      <AttachmentLightbox item={open} onClose={() => setOpen(null)} />
    </Box>
  );
}
