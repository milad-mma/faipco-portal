import { useEffect, useState } from "react";
import { Button, CircularProgress, Snackbar } from "@mui/material";
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
  const [isApplying, setIsApplying] = useState(false);

  useEffect(() => {
    function handleUpdateReady() {
      setIsOpen(true);
    }
    window.addEventListener(UPDATE_READY_EVENT, handleUpdateReady);
    return () => window.removeEventListener(UPDATE_READY_EVENT, handleUpdateReady);
  }, []);

  async function handleReloadClick() {
    // «بارگذاری» بین‌بین از کاربر جلوگیری می‌کند دوباره روی دکمه بزند —
    // پاک‌سازی Cache Storage معمولاً خیلی سریع است، ولی همین چند لحظه
    // بازخورد بصری بهتر از یک دکمه بی‌واکنش است.
    setIsApplying(true);
    // خودِ Reload توسط controllerchange (در serviceWorker.js) بعد از این
    // انجام می‌شود — این تابع صبر می‌کند تا Cache Storage کاملاً پاک شود
    // (نه localStorage/ورود کاربر — کاملاً مجزا و دست‌نخورده می‌ماند) و
    // بعد نسخه جدید را فعال می‌کند.
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
