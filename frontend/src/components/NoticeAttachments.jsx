/**
 * نمایش پیوست‌های یک اطلاعیه برای گیرنده/فرستنده: تصویرها به‌صورت بندانگشتی (با کلیک بزرگ می‌شوند)
 * و PDF ها به‌صورت کارت با دکمه‌ی مشاهده. فایل‌ها با توکن کاربر از API گرفته می‌شوند (Blob)، نه لینک مستقیم.
 * ورودی: items ([{ id, file_name, content_type, size_bytes }]).
 */
import { useEffect, useState } from "react";
import { Box, Button, Card, CircularProgress, Dialog, IconButton, Stack, Typography } from "@mui/material";
import PictureAsPdfOutlinedIcon from "@mui/icons-material/PictureAsPdfOutlined";
import CloseIcon from "@mui/icons-material/Close";
import { fetchNoticeAttachmentBlob } from "../api/notices";
import { formatFileSize } from "./NoticeAttachmentPicker";

function ImageThumb({ item, onOpen }) {
  const [url, setUrl] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl = null;
    let cancelled = false;
    fetchNoticeAttachmentBlob(item.id)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [item.id]);

  return (
    <Box
      onClick={() => url && onOpen(url)}
      sx={{
        width: 110,
        height: 110,
        borderRadius: 2,
        overflow: "hidden",
        border: 1,
        borderColor: "divider",
        bgcolor: "action.hover",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        cursor: url ? "zoom-in" : "default",
      }}
      title={item.file_name}
    >
      {url ? (
        <Box component="img" src={url} alt={item.file_name} sx={{ width: "100%", height: "100%", objectFit: "cover" }} />
      ) : failed ? (
        <Typography variant="caption" color="text.secondary">
          نمایش ممکن نشد
        </Typography>
      ) : (
        <CircularProgress size={20} />
      )}
    </Box>
  );
}

// PWA نصب‌شده (standalone): تب جدید/blob در آن باز نمی‌شود، پس فایل دانلود می‌شود (همان روش فیش حقوقی)
const isStandalone = () =>
  window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true;

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

function PdfCard({ item }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function open() {
    setBusy(true);
    setError("");
    // در مرورگر عادی پنجره همان لحظه‌ی کلیک باز می‌شود تا مسدودکننده‌ی پاپ‌آپ جلویش را نگیرد
    const win = isStandalone() ? null : window.open("", "_blank");
    try {
      const blob = new Blob([await fetchNoticeAttachmentBlob(item.id)], { type: "application/pdf" });
      if (win) {
        const url = URL.createObjectURL(blob);
        win.location.href = url;
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
      } else {
        downloadBlob(blob, item.file_name);
      }
    } catch {
      if (win) win.close();
      setError("دریافت فایل ممکن نشد.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card variant="outlined" sx={{ display: "flex", alignItems: "center", gap: 1.25, p: 1.25, borderRadius: 2, maxWidth: 360 }}>
      <PictureAsPdfOutlinedIcon color="error" />
      <Box sx={{ minWidth: 0, flexGrow: 1 }}>
        <Typography variant="body2" fontWeight={700} noWrap>
          {item.file_name}
        </Typography>
        <Typography variant="caption" color={error ? "error" : "text.secondary"}>
          {error || formatFileSize(item.size_bytes)}
        </Typography>
      </Box>
      <Button size="small" variant="outlined" onClick={open} disabled={busy}>
        {busy ? <CircularProgress size={16} /> : "مشاهده"}
      </Button>
    </Card>
  );
}

export default function NoticeAttachments({ items }) {
  const [preview, setPreview] = useState(null); // آدرس تصویر بزرگ‌شده
  if (!items?.length) return null;
  const images = items.filter((a) => a.content_type.startsWith("image/"));
  const pdfs = items.filter((a) => a.content_type === "application/pdf");

  return (
    <Stack spacing={1.25} sx={{ mt: 1.5 }}>
      {images.length > 0 && (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {images.map((item) => (
            <ImageThumb key={item.id} item={item} onOpen={setPreview} />
          ))}
        </Stack>
      )}
      {pdfs.map((item) => (
        <PdfCard key={item.id} item={item} />
      ))}
      <Dialog open={Boolean(preview)} onClose={() => setPreview(null)} maxWidth="lg">
        <Box sx={{ position: "relative", bgcolor: "black" }}>
          <IconButton
            onClick={() => setPreview(null)}
            sx={{ position: "absolute", top: 8, left: 8, color: "white", bgcolor: "rgba(0,0,0,0.4)" }}
            aria-label="بستن"
          >
            <CloseIcon />
          </IconButton>
          {preview && (
            <Box component="img" src={preview} alt="" sx={{ display: "block", maxWidth: "90vw", maxHeight: "85vh" }} />
          )}
        </Box>
      </Dialog>
    </Stack>
  );
}
