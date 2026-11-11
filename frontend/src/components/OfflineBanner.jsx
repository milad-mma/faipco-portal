import { useEffect, useState } from "react";
import { Alert, Snackbar } from "@mui/material";
import WifiOffOutlinedIcon from "@mui/icons-material/WifiOffOutlined";
import CloudOffOutlinedIcon from "@mui/icons-material/CloudOffOutlined";
import { useLocation } from "react-router-dom";
import { useOnlineStatus } from "../context/OnlineStatusContext";
import { isPortalUpdateActive, UPDATE_ACTIVITY_EVENT } from "../utils/serviceWorker";
import { connectionBannerKind, connectionBannerDelay } from "../utils/connectionFeedback";

/** Do not label a backend deployment/restart as a loss of internet.
 * Short interruptions are debounced and update-related ones are suppressed.
 */
export default function OfflineBanner() {
  const { isOnline, isBrowserOffline } = useOnlineStatus();
  const location = useLocation();
  const [updating, setUpdating] = useState(isPortalUpdateActive);
  const [show, setShow] = useState(false);
  const kind = connectionBannerKind({ isOnline, isBrowserOffline, updating });

  useEffect(() => {
    const onUpdateActivity = (event) => setUpdating(Boolean(event.detail?.active));
    window.addEventListener(UPDATE_ACTIVITY_EVENT, onUpdateActivity);
    return () => window.removeEventListener(UPDATE_ACTIVITY_EVENT, onUpdateActivity);
  }, []);

  useEffect(() => {
    if (!kind) {
      setShow(false);
      return undefined;
    }
    // Always debounce anew when the category changes (internet <-> server).
    setShow(false);
    // Service restarts and short network blips must not flash an inaccurate
    // red "internet disconnected" banner over an update in progress.
    const timer = setTimeout(() => setShow(true), connectionBannerDelay(kind));
    return () => clearTimeout(timer);
  }, [kind]);

  if (location.pathname === "/login") return null;

  return (
    <Snackbar
      open={show && Boolean(kind)}
      anchorOrigin={{ vertical: "top", horizontal: "center" }}
      sx={{ zIndex: (theme) => theme.zIndex.snackbar }}
    >
      <Alert
        severity={kind === "internet" ? "error" : "warning"}
        variant="filled"
        icon={kind === "internet" ? <WifiOffOutlinedIcon /> : <CloudOffOutlinedIcon />}
        sx={{ width: "100%", boxShadow: 3 }}
      >
        {kind === "internet"
          ? "اتصال اینترنت دستگاه برقرار نیست. بعضی تغییرات ممکن است ذخیره نشوند."
          : "ارتباط با سرور پرتال موقتاً برقرار نیست. ممکن است سرور در حال به‌روزرسانی باشد؛ کمی بعد دوباره تلاش کنید."}
      </Alert>
    </Snackbar>
  );
}
