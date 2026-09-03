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
import EmailOutlinedIcon from "@mui/icons-material/EmailOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import NotificationsActiveOutlinedIcon from "@mui/icons-material/NotificationsActiveOutlined";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import BrightnessAutoOutlinedIcon from "@mui/icons-material/BrightnessAutoOutlined";
import FingerprintOutlinedIcon from "@mui/icons-material/FingerprintOutlined";
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import AssessmentOutlinedIcon from "@mui/icons-material/AssessmentOutlined";
import ForumOutlinedIcon from "@mui/icons-material/ForumOutlined";
import CakeOutlinedIcon from "@mui/icons-material/CakeOutlined";
import DirectionsCarFilledOutlinedIcon from "@mui/icons-material/DirectionsCarFilledOutlined";
import ApartmentOutlinedIcon from "@mui/icons-material/ApartmentOutlined";
import GroupOutlinedIcon from "@mui/icons-material/GroupOutlined";
import SyncOutlinedIcon from "@mui/icons-material/SyncOutlined";
import AdminPanelSettingsOutlinedIcon from "@mui/icons-material/AdminPanelSettingsOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import VpnLockOutlinedIcon from "@mui/icons-material/VpnLockOutlined";
import CloudDownloadOutlinedIcon from "@mui/icons-material/CloudDownloadOutlined";
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

// دسترسی‌های اضافه‌ای که بعضی نقش‌های غیر-Admin دارند (site_manager،
// hr-manager، attendance-pilot و...) — قبلاً این‌ها یک آیتم منوی مستقل در
// Drawer/AppBar بودند؛ حالا که نوار پایین موبایل جای آن منو را گرفته
// (Layout.jsx)، این دسترسی‌ها دیگر روی موبایل جایی نداشتند تا این‌جا
// اضافه شدند — همان شرط‌هایی که Layout.jsx برای NAV_ITEMS چک می‌کند.
const EXTRA_ACCESS_ITEMS = [
  { flag: "can_clock_in_out", label: "ثبت ورود و خروج", path: "/attendance-clock", icon: <FingerprintOutlinedIcon /> },
  { flag: "can_view_clock_records", label: "گزارش ورود و خروج", path: "/clock-in-out-report", icon: <FingerprintOutlinedIcon /> },
  { flag: "can_view_attendance_logs", label: "پرسنل آنلاین", path: "/presence-report", icon: <ScienceOutlinedIcon /> },
  { flag: "can_view_site_notice_report", label: "گزارش اطلاعیه‌ها", path: "/notice-reports", icon: <AssessmentOutlinedIcon /> },
  { flag: "can_view_feedback", label: "انتقادات و پیشنهادات", path: "/feedback-report", icon: <ForumOutlinedIcon /> },
  { flag: "can_manage_birthday_messages", label: "پیام‌های تبریک تولد", path: "/birthday-messages", icon: <CakeOutlinedIcon /> },
  { flag: "can_view_vehicles_report", label: "خودروهای پرسنل", path: "/vehicle-report", icon: <DirectionsCarFilledOutlinedIcon /> },
  // ⚠️ این پنج مورد جدید — طبق درخواست صریح: هر مجوزی که به یک نقش داده
  // شود، منوی متناظرش باید در پنل کاربری هم اضافه شود. چون پرسنل غیر-Admin
  // اصلاً منوی کناری Admin (Layout.jsx) را نمی‌بینند (فقط نوار پایین)، این
  // بخش («دسترسی‌های ویژه») تنها جایی است که این پنج صفحه — اگر نقششان
  // مجوز متناظر را داشته باشد — واقعاً در دسترسشان قرار می‌گیرد.
  {
    check: (u) => u?.can_view_employees || u?.can_update_employees || u?.can_create_employees,
    label: "پرسنل",
    path: "/employees",
    icon: <GroupOutlinedIcon />,
  },
  { flag: "can_view_sites", label: "سایت‌ها", path: "/sites", icon: <ApartmentOutlinedIcon /> },
  {
    check: (u) => u?.can_manage_sync || u?.can_view_sync || u?.can_run_sync,
    label: "همگام‌سازی دیتابیس",
    path: "/sync",
    icon: <SyncOutlinedIcon />,
  },
  { flag: "can_manage_users", label: "مدیریت دسترسی", path: "/access", icon: <AdminPanelSettingsOutlinedIcon /> },
  { flag: "can_manage_roles", label: "مدیریت نقش/مجوز", path: "/role-management", icon: <LockOutlinedIcon /> },
  { flag: "can_manage_system_settings", label: "تنظیمات سامانه", path: "/system-settings", icon: <SettingsOutlinedIcon /> },
  { flag: "can_manage_ip_allowlist", label: "رنج‌های IP مجاز", path: "/ip-allowlist", icon: <VpnLockOutlinedIcon /> },
  {
    check: (u) => u?.can_manage_backup || u?.can_bust_cache,
    label: "پشتیبان‌گیری",
    path: "/backup",
    icon: <CloudDownloadOutlinedIcon />,
  },
];

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
      setSnackbar("ذخیره تنظیمات ناموفق بود — دوباره تلاش کنید.");
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

  const extraAccessItems = EXTRA_ACCESS_ITEMS.filter((item) => (item.check ? item.check(user) : user?.[item.flag]));

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
              <EmailOutlinedIcon />
            </ListItemIcon>
            <ListItemText primary="ویرایش ایمیل و موبایل" />
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
