import { Navigate } from "react-router-dom";
import { Box, CircularProgress } from "@mui/material";
import { useAuth } from "../context/AuthContext";

/**
 * محافظ مسیرهای نیازمند ورود.
 * ورودی: children. خروجی: هنگام بارگذاری وضعیت کاربر یک اسپینر تمام‌صفحه،
 * اگر کاربر وارد نشده باشد هدایت به /login، و در غیر این صورت children.
 */
export default function ProtectedRoute({ children }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
