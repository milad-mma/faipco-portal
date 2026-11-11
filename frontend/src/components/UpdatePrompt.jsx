import { useEffect, useState } from "react";
import { Button, CircularProgress, Snackbar } from "@mui/material";
import SystemUpdateAltOutlinedIcon from "@mui/icons-material/SystemUpdateAltOutlined";
import { applyPendingUpdate, UPDATE_READY_EVENT } from "../utils/serviceWorker";

/** Manual PWA/TWA update. Never blocks permanently when a mobile download stalls. */
export default function UpdatePrompt() {
  const [isOpen, setIsOpen] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    function handleUpdateReady() {
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
        ? "نسخه جدید هنوز آماده نشده است. اتصال را بررسی کنید و دوباره تلاش کنید."
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
          {isApplying ? "در حال آماده‌سازی..." : error ? "تلاش دوباره" : "بارگذاری"}
        </Button>
      }
    />
  );
}
