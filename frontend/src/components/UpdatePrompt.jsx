import { useEffect, useState } from "react";
import { Button, CircularProgress, Snackbar } from "@mui/material";
import SystemUpdateAltOutlinedIcon from "@mui/icons-material/SystemUpdateAltOutlined";
import { applyPendingUpdate, UPDATE_READY_EVENT } from "../utils/serviceWorker";

/** Manual PWA/TWA update. Never blocks permanently when a mobile download stalls. */
export default function UpdatePrompt() {
  const [isOpen, setIsOpen] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [error, setError] = useState(false);
  const [updateKind, setUpdateKind] = useState("release");

  useEffect(() => {
    function handleUpdateReady(event) {
      setUpdateKind(event.detail?.kind === "cache_refresh" ? "cache_refresh" : "release");
      setError(false);
      setIsOpen(true);
    }
    window.addEventListener(UPDATE_READY_EVENT, handleUpdateReady);
    return () => window.removeEventListener(UPDATE_READY_EVENT, handleUpdateReady);
  }, []);

  async function handleReloadClick() {
    if (isApplying) return;
    setIsApplying(true);
    setError(false);
    try {
      const result = await applyPendingUpdate();
      if (!result?.ok) setError(true);
      // Successful activation triggers a page reload inside applyPendingUpdate.
    } catch {
      setError(true);
    } finally {
      // On network/installation failures the button is usable again.
      setIsApplying(false);
    }
  }

  return (
    <Snackbar
      open={isOpen}
      anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      message={error
        ? "بارگذاری نسخه آماده ممکن نشد. اتصال را بررسی کنید و دوباره تلاش کنید."
        : updateKind === "cache_refresh"
          ? "نوسازی نسخه ذخیره‌شده پرتال آماده است"
          : "نسخه جدید پرتال آماده است"}
      action={
        <Button
          color="inherit"
          size="small"
          disabled={isApplying}
          startIcon={isApplying
            ? <CircularProgress size={14} color="inherit" />
            : <SystemUpdateAltOutlinedIcon fontSize="small" />}
          onClick={handleReloadClick}
          sx={{ "&.Mui-disabled": { color: "inherit", opacity: 0.8 } }}
        >
          {isApplying ? "در حال بارگذاری..." : error ? "تلاش دوباره" : updateKind === "cache_refresh" ? "بارگذاری مجدد" : "بارگذاری"}
        </Button>
      }
    />
  );
}
