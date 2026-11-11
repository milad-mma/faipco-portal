import { Navigate } from "react-router-dom";
import { Alert, Box, Button, CircularProgress, Stack, Typography } from "@mui/material";
import RefreshOutlinedIcon from "@mui/icons-material/RefreshOutlined";
import { useAuth } from "../context/AuthContext";
import { getProtectedRouteState } from "../utils/authRestorePolicy";

/** Keep the original route during a transient /auth/me failure after a PWA update. */
export default function ProtectedRoute({ children }) {
  const { user, isLoading, restoreError, isRecovering, tryRestoreSession, logout } = useAuth();
  const state = getProtectedRouteState({
    user,
    isLoading,
    restoreError,
    hasToken: Boolean(localStorage.getItem("access_token")),
  });

  if (state === "loading") {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100dvh" }}>
        <CircularProgress aria-label="در حال بررسی وضعیت ورود" />
      </Box>
    );
  }

  if (state === "reconnect") {
    return (
      <Box dir="rtl" sx={{ minHeight: "100dvh", display: "flex", justifyContent: "center", alignItems: "center", px: 2 }}>
        <Stack spacing={2} sx={{ width: "100%", maxWidth: 460 }}>
          <Typography variant="h6">در حال بازیابی اتصال پرتال</Typography>
          <Alert severity="warning" role="status">
            ارتباط با سرور موقتاً برقرار نشد. اطلاعات ورود شما حفظ شده است و پرتال به‌صورت خودکار دوباره تلاش می‌کند.
          </Alert>
          <Button
            variant="contained"
            startIcon={<RefreshOutlinedIcon />}
            onClick={() => { void tryRestoreSession({ retry: true }); }}
            disabled={isRecovering}
            sx={{ minHeight: 44, alignSelf: "flex-start" }}
          >
            {isRecovering ? "در حال بررسی اتصال..." : "تلاش دوباره"}
          </Button>
          <Button color="inherit" onClick={logout} sx={{ alignSelf: "flex-start" }}>
            خروج از حساب
          </Button>
        </Stack>
      </Box>
    );
  }

  if (state === "login") return <Navigate to="/login" replace />;
  return children;
}
