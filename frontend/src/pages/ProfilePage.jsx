import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Card,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Popover,
  Radio,
  RadioGroup,
  FormControlLabel,
  Stack,
  Typography,
  Snackbar,
} from "@mui/material";
import LockResetOutlinedIcon from "@mui/icons-material/LockResetOutlined";
import BadgeOutlinedIcon from "@mui/icons-material/BadgeOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import NotificationsActiveOutlinedIcon from "@mui/icons-material/NotificationsActiveOutlined";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import BrightnessAutoOutlinedIcon from "@mui/icons-material/BrightnessAutoOutlined";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useBranding } from "../context/BrandingContext";
import { useThemeMode } from "../context/ThemeModeContext";
import { enablePushNotifications, getNotificationPermission, isPushSupported } from "../utils/push";
import { fetchAppVersion } from "../api/system";
import { updateMyBirthdayVisibility } from "../api/employees";
import ChangePasswordDialog from "../components/ChangePasswordDialog";
import EditContactInfoDialog from "../components/EditContactInfoDialog";
import { NAV_ITEMS } from "../config/navItems";

/**
 * «دسترسی‌های ویژه» این صفحه - مقصدهایی که کاربر غیر-Admin (که فقط نوار
 * پایین را می‌بیند، نه منوی کناری Admin) طبق مجوزهایش به آن‌ها دسترسی
 * دارد. ⚠️ این لیست دیگر جداگانه و دستی نگه‌داری نمی‌شود - مستقیماً از
 * همان NAV_ITEMS مشترک (navItems.jsx) مسطح (Flatten) می‌شود؛ دقیقاً
 * همین دوگانگیِ قبلی (دو لیست جدا) بود که باعث شد «ارزیابی عملکرد» برای
 * کاربران غیر-Admin هیچ راه دسترسی نداشته باشد - از این به بعد هر مقصد
 * جدیدی که به NAV_ITEMS اضافه شود، خودکار همین‌جا هم ظاهر می‌شود.
 */
const EXTRA_ACCESS_ITEMS = NAV_ITEMS.flatMap((item) => {
  if (item.adminOnly) return []; // این صفحه فقط برای غیر-Admin است
  if (item.children?.length) return item.children.filter((child) => child.check);
  return item.check ? [item] : [];
});

/**
 * پنل کاربری — قبلاً محتوای این صفحه فقط داخل منوی حساب کاربری (بالای
 * صفحه) بود؛ حالا به یک صفحه مستقل (تب «پنل کاربری» در نوار پایین موبایل)
 * تبدیل شده — همان قابلیت‌ها، فقط جای متفاوت.
 */
export default function ProfilePage() {
  const { user, logout, refetchUser } = useAuth();
  const { appLogoUrl, profileTitle, profileSubtitle } = useBranding();
  const navigate = useNavigate();
  const { mode, setMode, isManual, resetToSystem } = useThemeMode();
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [contactInfoDialogOpen, setContactInfoDialogOpen] = useState(false);
  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false);
  const [pushPermission, setPushPermission] = useState(() => getNotificationPermission());
  const [snackbar, setSnackbar] = useState("");
  const [appVersion, setAppVersion] = useState("");
  const [birthdayInfoAnchor, setBirthdayInfoAnchor] = useState(null);
  const [birthdaySaving, setBirthdaySaving] = useState(false);

  async function handleToggleBirthdayVisibility(e) {
    const hide = e.target.checked;
    setBirthdaySaving(true);
    try {
      await updateMyBirthdayVisibility(hide);
      await refetchUser();
    } catch {
      setSnackbar("ذخیره تنظیمات با خطا مواجه شد — دوباره تلاش کنید.");
    } finally {
      setBirthdaySaving(false);
    }
  }

  useEffect(() => {
    // بی‌صدا — مثل صفحه ورود، اگر شکست بخورد فقط شماره نسخه نشان داده نمی‌شود
    fetchAppVersion()
      .then(setAppVersion)
      .catch(() => {});
  }, []);

  const extraAccessItems = EXTRA_ACCESS_ITEMS.filter((item) => item.check(user));

  async function handleEnableNotifications() {
    try {
      await enablePushNotifications();
      setPushPermission(getNotificationPermission());
      setSnackbar("اعلان‌ها با موفقیت فعال شد ✅ — از همین دستگاه اعلان دریافت می‌کنید");
    } catch (err) {
      setPushPermission(getNotificationPermission());
      setSnackbar(err.message || "فعال‌سازی اعلان با خطا مواجه شد");
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
    <Box sx={{ maxWidth: { xs: "100%", md: 1100 }, mx: "auto" }}>
      <Card variant="outlined" sx={{ borderRadius: 2, overflow: "hidden", mb: 2 }}>
        <Box
          sx={{
            background: "linear-gradient(135deg, #185E95 0%, #2E84AA 100%)",
            display: "flex",
            justifyContent: "center",
            py: 3.5,
          }}
        >
          <Box
            sx={{
              width: 108,
              height: 108,
              borderRadius: "50%",
              bgcolor: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: 2,
            }}
          >
            <Box
              component="img"
              src={appLogoUrl}
              alt={profileTitle}
              onError={(e) => {
                e.currentTarget.onerror = null;
                e.currentTarget.src = "/faipco-logo.png";
              }}
              sx={{ width: 84, height: 84, objectFit: "contain" }}
            />
          </Box>
        </Box>
        <Stack alignItems="center" spacing={0.5} sx={{ textAlign: "center", px: 2.5, py: 2.5 }}>
          <Typography variant="subtitle1" fontWeight={700} color="primary.main">
            {profileTitle}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {profileSubtitle}
          </Typography>
          {appVersion && (
            <Typography
              variant="caption"
              color="text.disabled"
              sx={{ direction: "ltr", mt: 1 }}
            >
              {appVersion}
            </Typography>
          )}
        </Stack>
      </Card>

      {extraAccessItems.length > 0 && (
        <Card variant="outlined" sx={{ borderRadius: 2, overflow: "hidden", mb: 2 }}>
          <List disablePadding>
            {extraAccessItems.map((item) => (
              <ListItemButton key={item.path} onClick={() => navigate(item.path)}>
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            ))}
          </List>
        </Card>
      )}

      <Card variant="outlined" sx={{ borderRadius: 2, p: 2.5, mb: 2 }}>
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

      {user?.employee_id && (
        <Card variant="outlined" sx={{ borderRadius: 2, p: 2.5, mb: 2 }}>
          <Stack direction="row" alignItems="center" spacing={0.5}>
            <FormControlLabel
              sx={{ flex: 1, mr: 0 }}
              control={
                <Checkbox
                  checked={Boolean(user?.hide_birthday_in_dashboard)}
                  onChange={handleToggleBirthdayVisibility}
                  disabled={birthdaySaving}
                />
              }
              label="غیرفعال نمودن نمایش روز تولد در داشبورد پرسنل"
            />
            <IconButton
              size="small"
              onClick={(e) => setBirthdayInfoAnchor(e.currentTarget)}
              aria-label="توضیحات بیشتر"
            >
              <InfoOutlinedIcon fontSize="small" />
            </IconButton>
          </Stack>
          <Popover
            open={Boolean(birthdayInfoAnchor)}
            anchorEl={birthdayInfoAnchor}
            onClose={() => setBirthdayInfoAnchor(null)}
            anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
            transformOrigin={{ vertical: "top", horizontal: "center" }}
          >
            <Typography variant="body2" sx={{ p: 2, maxWidth: 280 }}>
              همکار گرامی، در صورتی که مایل نیستید روز تولدتان در داشبورد
              همکاران نمایش داده شود، این گزینه را فعال نمایید.
            </Typography>
          </Popover>
        </Card>
      )}

      <Card variant="outlined" sx={{ borderRadius: 2, overflow: "hidden" }}>
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
          <ListItemButton onClick={() => setContactInfoDialogOpen(true)}>
            <ListItemIcon>
              <BadgeOutlinedIcon />
            </ListItemIcon>
            <ListItemText primary="مشخصات کاربری" />
          </ListItemButton>
          <ListItemButton onClick={() => setPasswordDialogOpen(true)}>
            <ListItemIcon>
              <LockResetOutlinedIcon />
            </ListItemIcon>
            <ListItemText primary="تغییر رمز عبور" />
          </ListItemButton>
          <ListItemButton onClick={() => setLogoutConfirmOpen(true)} sx={{ color: "error.main" }}>
            <ListItemIcon sx={{ color: "error.main" }}>
              <LogoutOutlinedIcon />
            </ListItemIcon>
            <ListItemText primary="خروج از حساب" />
          </ListItemButton>
        </List>
      </Card>

      <ChangePasswordDialog open={passwordDialogOpen} onClose={() => setPasswordDialogOpen(false)} />
      <EditContactInfoDialog open={contactInfoDialogOpen} onClose={() => setContactInfoDialogOpen(false)} />

      <Dialog open={logoutConfirmOpen} onClose={() => setLogoutConfirmOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>خروج از حساب کاربری</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            در صورت خروج از سامانه، اعلان اطلاعیه‌های شرکت برای شما ارسال نخواهد شد.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setLogoutConfirmOpen(false)}>انصراف</Button>
          <Button variant="contained" color="error" onClick={logout}>
            خروج از حساب کاربری
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar open={Boolean(snackbar)} autoHideDuration={4000} onClose={() => setSnackbar("")} message={snackbar} />
    </Box>
  );
}
