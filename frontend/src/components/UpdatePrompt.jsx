import { useEffect, useState } from "react";
import { Button, Snackbar } from "@mui/material";
import SystemUpdateAltOutlinedIcon from "@mui/icons-material/SystemUpdateAltOutlined";
import { applyPendingUpdate, UPDATE_READY_EVENT } from "../utils/serviceWorker";

/**
 * یک پیام کوچک و غیرمزاحم — فقط دقیقاً همان لحظه‌ای ظاهر می‌شود که واقعاً
 * یک نسخه جدید Deploy شده و آماده است، نه به‌طور اتفاقی/دوره‌ای. تا کاربر
 * خودش کلیک نکند، هیچ Reload ای اتفاق نمی‌افتد — پس اگر وسط پرکردن یک فرم
 * باشد، می‌تواند اول کارش را تمام کند.
 */
export default function UpdatePrompt() {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    function handleUpdateReady() {
      setIsOpen(true);
    }
    window.addEventListener(UPDATE_READY_EVENT, handleUpdateReady);
    return () => window.removeEventListener(UPDATE_READY_EVENT, handleUpdateReady);
  }, []);

  function handleReloadClick() {
    applyPendingUpdate();
    // خودِ Reload توسط controllerchange (در serviceWorker.js) انجام می‌شود؛
    // این‌جا فقط پیام را می‌بندیم تا دوباره نشان داده نشود.
    setIsOpen(false);
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
          startIcon={<SystemUpdateAltOutlinedIcon fontSize="small" />}
          onClick={handleReloadClick}
        >
          بارگذاری
        </Button>
      }
    />
  );
}
