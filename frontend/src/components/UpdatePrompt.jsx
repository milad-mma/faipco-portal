import { useEffect, useState } from "react";
import { Button, CircularProgress, Snackbar } from "@mui/material";
import SystemUpdateAltOutlinedIcon from "@mui/icons-material/SystemUpdateAltOutlined";
import { applyPendingUpdate, UPDATE_READY_EVENT } from "../utils/serviceWorker";

/**
 * پیام کوچک «نسخه جدید پرتال آماده است» که فقط وقتی نسخه‌ی جدید Deploy و آماده شده ظاهر می‌شود
 * (با رویداد UPDATE_READY_EVENT از serviceWorker). بدون ورودی (props).
 * تا کاربر روی «بارگذاری» کلیک نکند Reload انجام نمی‌شود، پس کار نیمه‌تمام (مثلاً فرم) از دست نمی‌رود.
 */
export default function UpdatePrompt() {
  const [isOpen, setIsOpen] = useState(false);
  const [isApplying, setIsApplying] = useState(false);  // در حال اعمال نسخه‌ی جدید (دکمه غیرفعال و اسپینر)

  // گوش دادن به رویداد آماده بودن نسخه‌ی جدید و نمایش پیام
  useEffect(() => {
    function handleUpdateReady() {
      setIsOpen(true);
    }
    window.addEventListener(UPDATE_READY_EVENT, handleUpdateReady);
    return () => window.removeEventListener(UPDATE_READY_EVENT, handleUpdateReady);
  }, []);

  // اعمال به‌روزرسانی با کلیک کاربر
  async function handleReloadClick() {
    // حالت «در حال بارگذاری» از کلیک دوباره جلوگیری می‌کند و بازخورد بصری می‌دهد
    setIsApplying(true);
    // applyPendingUpdate صبر می‌کند تا Cache Storage پاک شود (localStorage و ورود کاربر دست‌نخورده می‌مانند)
    // و سپس نسخه‌ی جدید را فعال می‌کند؛ Reload توسط controllerchange در serviceWorker.js انجام می‌شود.
    await applyPendingUpdate();
  }

  return (
    <Snackbar
      open={isOpen}
      anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      message="نسخه جدید پرتال آماده است"
      action={
        <Button
          color="inherit"
          size="small"
          disabled={isApplying}
          startIcon={
            isApplying ? (
              <CircularProgress size={14} color="inherit" />
            ) : (
              <SystemUpdateAltOutlinedIcon fontSize="small" />
            )
          }
          onClick={handleReloadClick}
        >
          {isApplying ? "در حال بارگذاری..." : "بارگذاری"}
        </Button>
      }
    />
  );
}
