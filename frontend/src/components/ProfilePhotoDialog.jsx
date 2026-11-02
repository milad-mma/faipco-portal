// پنجره‌ی عکس پروفایل داشبورد: عکس بزرگ و دایره‌ای وسط صفحه + «حذف تصویر» (اگر عکس دارد) یا «بارگذاری تصویر».
// هر تغییر به‌صورت درخواست برای منابع انسانی ثبت می‌شود و بعد از تأیید در کاراوب و پرتال می‌نشیند.
import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  IconButton,
  LinearProgress,
  Stack,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import AddAPhotoOutlinedIcon from "@mui/icons-material/AddAPhotoOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DefaultPersonAvatar from "./DefaultPersonAvatar";
import {
  cancelPhotoRequest,
  fetchMyPendingPhotoBlob,
  fetchMyPhotoStatus,
  requestPhotoDelete,
  requestPhotoUpload,
} from "../api/profilePhoto";

const circleSx = {
  width: { xs: "62vw", sm: 260 },
  maxWidth: 280,
  aspectRatio: "1 / 1",
  borderRadius: "50%",
  border: "4px solid #fff",
  boxShadow: 6,
  objectFit: "cover",
  bgcolor: "grey.200",
  userSelect: "none",
};

export default function ProfilePhotoDialog({ open, onClose, photoUrl }) {
  const fileRef = useRef(null);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [pendingUrl, setPendingUrl] = useState(null);

  useEffect(() => {
    if (!open) return;
    setError("");
    setConfirmDelete(false);
    fetchMyPhotoStatus()
      .then(setStatus)
      .catch((err) => setError(err.response?.data?.detail || "دریافت وضعیت عکس ناموفق بود."));
  }, [open]);

  // پیش‌نمایش عکس درخواست در انتظار
  useEffect(() => {
    if (!open || status?.pending?.action !== "upload") {
      setPendingUrl(null);
      return undefined;
    }
    let url = null;
    let alive = true;
    fetchMyPendingPhotoBlob()
      .then((blob) => {
        if (!alive) return;
        url = URL.createObjectURL(blob);
        setPendingUrl(url);
      })
      .catch(() => {});
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [open, status?.pending?.id, status?.pending?.action]);

  async function run(action) {
    setBusy(true);
    setError("");
    try {
      setStatus(await action());
      setConfirmDelete(false);
    } catch (err) {
      setError(err.response?.data?.detail || "انجام نشد؛ دوباره تلاش کنید.");
    } finally {
      setBusy(false);
      setProgress(0);
    }
  }

  function handleFile(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    run(() => requestPhotoUpload(file, setProgress));
  }

  const pending = status?.pending;
  const rejected = !pending && status?.last_decision?.status === "rejected" ? status.last_decision : null;
  const shownUrl = pendingUrl || photoUrl;

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} PaperProps={{ sx: { borderRadius: 4, m: 2, width: 340, maxWidth: "calc(100% - 32px)" } }}>
      <Box sx={{ position: "relative", p: 2.5, pt: 4 }}>
        <IconButton onClick={onClose} disabled={busy} size="small" sx={{ position: "absolute", top: 8, insetInlineEnd: 8 }} aria-label="بستن">
          <CloseIcon fontSize="small" />
        </IconButton>
        <Stack alignItems="center" spacing={2}>
          {shownUrl ? (
            <Box
              component="img"
              src={shownUrl}
              alt=""
              draggable={false}
              onContextMenu={(e) => e.preventDefault()}
              sx={{ ...circleSx, display: "block", opacity: pendingUrl ? 0.85 : 1 }}
            />
          ) : (
            <Box sx={{ ...circleSx, display: "flex", alignItems: "center", justifyContent: "center", color: "grey.500" }}>
              <DefaultPersonAvatar size="60%" />
            </Box>
          )}

          {!status && !error && <CircularProgress size={24} />}
          {error && <Alert severity="error" sx={{ width: "100%" }}>{error}</Alert>}
          {busy && progress > 0 && progress < 100 && <LinearProgress variant="determinate" value={progress} sx={{ width: "100%" }} />}

          {status && pending && (
            <>
              <Alert severity="info" sx={{ width: "100%" }}>
                {pending.action === "upload"
                  ? "عکس جدید شما ثبت شد و بعد از تأیید منابع انسانی جایگزین می‌شود."
                  : "درخواست حذف عکس ثبت شد و بعد از تأیید منابع انسانی انجام می‌شود."}
              </Alert>
              <Button variant="outlined" color="inherit" disabled={busy} onClick={() => run(cancelPhotoRequest)} sx={{ height: 40 }}>
                لغو درخواست
              </Button>
            </>
          )}

          {status && !pending && rejected && (
            <Alert severity="warning" sx={{ width: "100%" }}>
              درخواست {rejected.action === "upload" ? "بارگذاری" : "حذف"} قبلی رد شد{rejected.reason ? `: ${rejected.reason}` : "."}
            </Alert>
          )}

          {status && !pending && status.enabled && status.has_photo && !confirmDelete && (
            <Button variant="outlined" color="error" startIcon={<DeleteOutlineIcon />} disabled={busy} onClick={() => setConfirmDelete(true)} sx={{ height: 40 }}>
              حذف تصویر
            </Button>
          )}
          {status && !pending && status.enabled && status.has_photo && confirmDelete && (
            <Stack spacing={1} alignItems="center" sx={{ width: "100%" }}>
              <Typography variant="body2" textAlign="center">
                درخواست حذف عکس برای منابع انسانی ارسال شود؟
              </Typography>
              <Stack direction="row" spacing={1}>
                <Button variant="contained" color="error" disabled={busy} onClick={() => run(requestPhotoDelete)} sx={{ height: 40 }}>
                  بله، حذف شود
                </Button>
                <Button variant="text" color="inherit" disabled={busy} onClick={() => setConfirmDelete(false)} sx={{ height: 40 }}>
                  انصراف
                </Button>
              </Stack>
            </Stack>
          )}

          {status && !pending && status.enabled && !status.has_photo && (
            <>
              <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={handleFile} />
              <Button
                variant="contained"
                startIcon={busy ? <CircularProgress size={18} color="inherit" /> : <AddAPhotoOutlinedIcon />}
                disabled={busy}
                onClick={() => fileRef.current?.click()}
                sx={{ height: 40 }}
              >
                بارگذاری تصویر
              </Button>
              <Typography variant="caption" color="text.secondary" textAlign="center">
                عکس چهره‌ی واضح و مربعی بهتر است. حجم و اندازه خودکار تنظیم می‌شود و بعد از تأیید منابع انسانی ثبت می‌شود.
              </Typography>
            </>
          )}

          {status && !pending && !status.enabled && (
            <Typography variant="caption" color="text.secondary" textAlign="center">
              تغییر عکس برای سایت شما هنوز فعال نشده است.
            </Typography>
          )}
        </Stack>
      </Box>
    </Dialog>
  );
}
