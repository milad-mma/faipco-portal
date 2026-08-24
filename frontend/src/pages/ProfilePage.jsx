import { useState } from "react";
import {
  Box,
  Card,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Radio,
  RadioGroup,
  FormControlLabel,
  Stack,
  Typography,
  Snackbar,
} from "@mui/material";
import LockResetOutlinedIcon from "@mui/icons-material/LockResetOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import NotificationsActiveOutlinedIcon from "@mui/icons-material/NotificationsActiveOutlined";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import BrightnessAutoOutlinedIcon from "@mui/icons-material/BrightnessAutoOutlined";
import { useAuth } from "../context/AuthContext";
import { useThemeMode } from "../context/ThemeModeContext";
import { enablePushNotifications, getNotificationPermission, isPushSupported } from "../utils/push";
import ChangePasswordDialog from "../components/ChangePasswordDialog";
import DefaultPersonAvatar from "../components/DefaultPersonAvatar";

/**
 * پنل کاربری — قبلاً محتوای این صفحه فقط داخل منوی حساب کاربری (بالای
 * صفحه) بود؛ حالا به یک صفحه مستقل (تب «پنل کاربری» در نوار پایین موبایل)
 * تبدیل شده — همان قابلیت‌ها، فقط جای متفاوت.
 */
export default function ProfilePage() {
  const { user, logout } = useAuth();
  const { mode, setMode, isManual, resetToSystem } = useThemeMode();
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [pushPermission, setPushPermission] = useState(() => getNotificationPermission());
  const [snackbar, setSnackbar] = useState("");

  async function handleEnableNotifications() {
    try {
      await enablePushNotifications();
      setPushPermission(getNotificationPermission());
      setSnackbar("اعلان‌ها با موفقیت فعال شد ✅ — از همین دستگاه اعلان دریافت می‌کنید");
    } catch (err) {
      setPushPermission(getNotificationPermission());
      setSnackbar(err.message || "فعال‌سازی اعلان ناموفق بود");
    }
  }

  function handleThemeChange(value) {
    if (value === "system") {
      resetToSystem();
    } else {
      setMode(value);
    }
  }

  return (
    <Box sx={{ maxWidth: { xs: "100%", md: 480 } }}>
      <Card variant="outlined" sx={{ borderRadius: 3, p: 2.5, mb: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center">
          <Box
            sx={{
              width: 56,
              height: 56,
              borderRadius: "50%",
              bgcolor: "primary.main",
              color: "primary.contrastText",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <DefaultPersonAvatar />
          </Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography fontWeight={700} noWrap>
              {user?.first_name} {user?.last_name}
            </Typography>
            <Typography variant="body2" color="text.secondary" noWrap>
              {user?.personnel_code ? `کد پرسنلی: ${user.personnel_code}` : user?.username}
            </Typography>
          </Box>
        </Stack>
      </Card>

      <Card variant="outlined" sx={{ borderRadius: 3, p: 2.5, mb: 2 }}>
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
          حالت نمایش
        </Typography>
        <RadioGroup
          value={isManual ? mode : "system"}
          onChange={(e) => handleThemeChange(e.target.value)}
        >
          <FormControlLabel
            value="system"
            control={<Radio size="small" />}
            label={
              <Stack direction="row" spacing={1} alignItems="center">
                <BrightnessAutoOutlinedIcon fontSize="small" />
                <span>پیروی از تنظیمات سیستم</span>
              </Stack>
            }
          />
          <FormControlLabel
            value="light"
            control={<Radio size="small" />}
            label={
              <Stack direction="row" spacing={1} alignItems="center">
                <LightModeOutlinedIcon fontSize="small" />
                <span>روشن</span>
              </Stack>
            }
          />
          <FormControlLabel
            value="dark"
            control={<Radio size="small" />}
            label={
              <Stack direction="row" spacing={1} alignItems="center">
                <DarkModeOutlinedIcon fontSize="small" />
                <span>تیره</span>
              </Stack>
            }
          />
        </RadioGroup>
      </Card>

      <Card variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
        <List disablePadding>
          {isPushSupported() && (
            <ListItemButton onClick={handleEnableNotifications} disabled={pushPermission !== "default"}>
              <ListItemIcon>
                <NotificationsActiveOutlinedIcon color={pushPermission === "granted" ? "success" : "inherit"} />
              </ListItemIcon>
              <ListItemText
                primary={
                  pushPermission === "granted"
                    ? "اعلان‌ها فعال است ✓"
                    : pushPermission === "denied"
                      ? "اعلان‌ها مسدود شده (از تنظیمات مرورگر باز کنید)"
                      : "فعال‌سازی اعلان‌ها"
                }
              />
            </ListItemButton>
          )}
          <ListItemButton onClick={() => setPasswordDialogOpen(true)}>
            <ListItemIcon>
              <LockResetOutlinedIcon />
            </ListItemIcon>
            <ListItemText primary="تغییر رمز عبور" />
          </ListItemButton>
          <ListItemButton onClick={logout} sx={{ color: "error.main" }}>
            <ListItemIcon sx={{ color: "error.main" }}>
              <LogoutOutlinedIcon />
            </ListItemIcon>
            <ListItemText primary="خروج از حساب" />
          </ListItemButton>
        </List>
      </Card>

      <ChangePasswordDialog open={passwordDialogOpen} onClose={() => setPasswordDialogOpen(false)} />
      <Snackbar open={Boolean(snackbar)} autoHideDuration={4000} onClose={() => setSnackbar("")} message={snackbar} />
    </Box>
  );
}
