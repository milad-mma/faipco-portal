import { Alert, Snackbar } from "@mui/material";
import WifiOffOutlinedIcon from "@mui/icons-material/WifiOffOutlined";
import { useLocation } from "react-router-dom";
import { useOnlineStatus } from "../context/OnlineStatusContext";

/**
 * بنر شناور قرمز — فقط وقتی کاربر داخل برنامه است و اتصال قطع می‌شود.
 * توی صفحه ورود عمداً نمایش داده نمی‌شود، چون آنجا یک بلوک تمام‌صفحه
 * اختصاصی (OfflineLoginBlock در LoginPage) جای این بنر را می‌گیرد — نمایش
 * هردو با هم فقط شلوغی بصری اضافه می‌کرد.
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
