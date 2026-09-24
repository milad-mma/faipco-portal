import { Alert, Snackbar } from "@mui/material";
import WifiOffOutlinedIcon from "@mui/icons-material/WifiOffOutlined";
import { useLocation } from "react-router-dom";
import { useOnlineStatus } from "../context/OnlineStatusContext";

/**
 * بنر شناور قرمز «اتصال اینترنت قطع شده» که هنگام آفلاین شدن بالای صفحه نمایش داده می‌شود.
 * بدون ورودی (props)؛ وضعیت اتصال را از OnlineStatusContext می‌خواند.
 * در صفحه‌ی ورود نمایش داده نمی‌شود، چون آنجا بلوک تمام‌صفحه‌ی OfflineLoginBlock (در LoginPage) همین نقش را دارد.
 */
export default function OfflineBanner() {
  const { isOnline } = useOnlineStatus();
  const location = useLocation();

  if (location.pathname === "/login") return null;

  return (
    <Snackbar open={!isOnline} anchorOrigin={{ vertical: "top", horizontal: "center" }} sx={{ zIndex: (theme) => theme.zIndex.snackbar }}>
      <Alert severity="error" variant="filled" icon={<WifiOffOutlinedIcon />} sx={{ width: "100%", boxShadow: 3 }}>
        اتصال اینترنت قطع شده — تا وصل‌شدن دوباره، برخی کارها ممکن است ذخیره نشوند.
      </Alert>
    </Snackbar>
  );
}
