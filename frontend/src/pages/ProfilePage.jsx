/**
 * صفحه «پنل کاربری» (تب پنل کاربری در نوار پایین موبایل).
 * شامل کارت برند و نسخه برنامه، میان‌بر مقصدهایی که کاربر طبق مجوزهایش به آن‌ها دسترسی دارد،
 * انتخاب حالت نمایش (سیستم/روشن/تیره)، تنظیم مخفی‌سازی تولد، فعال‌سازی اعلان Push،
 * ویرایش مشخصات، تغییر رمز و خروج از حساب.
 */
import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Card,
  Checkbox,
  Collapse,
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
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
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
import BrandLogo, { surfaceTitleSx } from "../components/BrandLogo";
import { useThemeMode } from "../context/ThemeModeContext";
import { enablePushNotifications, getNotificationPermission, isPushSupported } from "../utils/push";
import { fetchAppVersion } from "../api/system";
import { updateMyBirthdayVisibility } from "../api/employees";
import ChangePasswordDialog from "../components/ChangePasswordDialog";
import EditContactInfoDialog from "../components/EditContactInfoDialog";
import { NAV_ITEMS } from "../config/navItems";

/**
 * «دسترسی‌های ویژه» این صفحه: مقصدهایی که کاربر غیر-Admin (که فقط نوار پایین را می‌بیند،
 * نه منوی کناری Admin) طبق مجوزهایش به آن‌ها دسترسی دارد.
 * مستقیماً از NAV_ITEMS مشترک (navItems.jsx) ساخته می‌شود، پس هر مقصد جدید در NAV_ITEMS
 * خودکار اینجا هم ظاهر می‌شود. آیتم‌های دارای زیرمنو (مثل «ارزیابی عملکرد») به‌صورت یک گروه
 * قابل‌جمع‌شدن (مثل منوی کناری Admin در Layout.jsx) نگه داشته می‌شوند و فقط زیرآیتم‌های دارای check می‌مانند.
 */
const EXTRA_ACCESS_GROUPS = NAV_ITEMS.filter((item) => !item.adminOnly && (item.check || item.children?.length)).map(
  (item) => ({
    label: item.label,
    icon: item.icon,
    path: item.path,
    check: item.check,
    children: item.children?.filter((child) => child.check) || null,
  })
);

/**
 * کامپوننت صفحه پنل کاربری؛ ورودی ندارد.
 * اطلاعات کاربر، برندینگ و حالت تم را از Contextها می‌گیرد و کارت‌های تنظیمات و میان‌برها را رندر می‌کند.
 */
export default function ProfilePage() {
  const { user, logout, refetchUser } = useAuth();
  const { profileTitle, profileSubtitle, surfaces } = useBranding();
  const profileCfg = surfaces.profile;  // تنظیمات برندینگ سطح «profile» (پس‌زمینه، نمایش عنوان/زیرعنوان)
  const navigate = useNavigate();
  const { mode, setMode, isManual, resetToSystem } = useThemeMode();
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [contactInfoDialogOpen, setContactInfoDialogOpen] = useState(false);
  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false);
  const [pushPermission, setPushPermission] = useState(() => getNotificationPermission());  // "default" | "granted" | "denied"
  const [snackbar, setSnackbar] = useState("");  // متن Snackbar؛ رشته خالی = بسته
  const [appVersion, setAppVersion] = useState("");
  const [birthdayInfoAnchor, setBirthdayInfoAnchor] = useState(null);  // عنصر لنگر Popover توضیح گزینه تولد؛ null = بسته
  const [birthdaySaving, setBirthdaySaving] = useState(false);  // در حال ذخیره تنظیم نمایش تولد

  // تنظیم مخفی‌سازی تولد در داشبورد را ذخیره و اطلاعات کاربر را دوباره از سرور می‌خواند
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
    // دریافت شماره نسخه برنامه؛ خطا بی‌صدا نادیده گرفته می‌شود و فقط نسخه نمایش داده نمی‌شود
    fetchAppVersion()
      .then(setAppVersion)
      .catch(() => {});
  }, []);

  // فیلتر مقصدها بر اساس مجوز کاربر: گروه دارای زیرمنو فقط با زیرآیتم‌های مجاز می‌ماند
  // (و اگر هیچ‌کدام مجاز نباشد حذف می‌شود)؛ آیتم ساده با check(user) سنجیده می‌شود
  const extraAccessGroups = EXTRA_ACCESS_GROUPS.map((group) => {
    if (group.children) {
      const visibleChildren = group.children.filter((child) => child.check(user));
      return visibleChildren.length > 0 ? { ...group, children: visibleChildren } : null;
    }
    return group.check(user) ? group : null;
  }).filter(Boolean);

  // وضعیت باز/بسته بودن گروه‌های دارای زیرمنو، به‌صورت { [label]: boolean }
  const [expandedGroups, setExpandedGroups] = useState({});
  // باز/بسته کردن یک گروه بر اساس label
  function toggleGroup(label) {
    setExpandedGroups((prev) => ({ ...prev, [label]: !prev[label] }));
  }

  // مجوز و اشتراک اعلان Push را فعال می‌کند و وضعیت مجوز و پیام نتیجه را به‌روز می‌کند
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

  // انتخاب «system» حالت دستی را پاک می‌کند؛ در غیر این صورت حالت روشن/تیره را ثابت می‌کند
  function handleThemeChange(value) {
    if (value === "system") {
      resetToSystem();
    } else {
      setMode(value);
    }
  }

  return (
    <Box sx={{ maxWidth: { xs: "100%", md: 1100 }, mx: "auto" }}>
      {/* کارت برند: لوگو، عنوان/زیرعنوان (طبق تنظیمات برندینگ) و نسخه برنامه */}
      <Card variant="outlined" sx={{ borderRadius: 2, overflow: "hidden", mb: 2 }}>
        <Box
          sx={{
            background: profileCfg.background || "linear-gradient(135deg, #185E95 0%, #2E84AA 100%)",
            display: "flex",
            justifyContent: "center",
            py: 3.5,
          }}
        >
          <BrandLogo surface="profile" alt={profileTitle} sx={{ boxShadow: 2 }} />
        </Box>
        <Stack alignItems="center" spacing={0.5} sx={{ textAlign: "center", px: 2.5, py: 2.5 }}>
          {profileCfg.show_title && (
            <Typography sx={{ color: "primary.main", ...surfaceTitleSx(profileCfg, "title") }}>{profileTitle}</Typography>
          )}
          {profileCfg.show_subtitle && (
            <Typography sx={{ color: "text.secondary", ...surfaceTitleSx(profileCfg, "subtitle") }}>
              {profileSubtitle}
            </Typography>
          )}
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

      {/* میان‌بر مقصدهای مجاز؛ گروه‌های دارای زیرمنو به‌صورت قابل‌جمع‌شدن */}
      {extraAccessGroups.length > 0 && (
        <Card variant="outlined" sx={{ borderRadius: 2, overflow: "hidden", mb: 2 }}>
          <List disablePadding>
            {extraAccessGroups.map((group) =>
              group.children ? (
                <Box key={group.label}>
                  <ListItemButton onClick={() => toggleGroup(group.label)}>
                    <ListItemIcon>{group.icon}</ListItemIcon>
                    <ListItemText primary={group.label} />
                    {expandedGroups[group.label] ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                  </ListItemButton>
                  <Collapse in={Boolean(expandedGroups[group.label])} timeout="auto" unmountOnExit>
                    <List disablePadding>
                      {group.children.map((child) => (
                        <ListItemButton key={child.path} onClick={() => navigate(child.path)} sx={{ pr: 4 }}>
                          <ListItemIcon>{child.icon}</ListItemIcon>
                          <ListItemText primary={child.label} />
                        </ListItemButton>
                      ))}
                    </List>
                  </Collapse>
                </Box>
              ) : (
                <ListItemButton key={group.path} onClick={() => navigate(group.path)}>
                  <ListItemIcon>{group.icon}</ListItemIcon>
                  <ListItemText primary={group.label} />
                </ListItemButton>
              )
            )}
          </List>
        </Card>
      )}

      {/* انتخاب حالت نمایش: پیروی از سیستم، روشن یا تیره */}
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

      {/* تنظیم مخفی‌سازی تولد (فقط برای کاربرانی که به پرسنل متصل‌اند) با Popover توضیح */}
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

      {/* فهرست عملیات حساب: اعلان‌ها، مشخصات کاربری، تغییر رمز و خروج */}
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

      {/* دیالوگ‌های تغییر رمز و ویرایش مشخصات */}
      <ChangePasswordDialog open={passwordDialogOpen} onClose={() => setPasswordDialogOpen(false)} />
      <EditContactInfoDialog open={contactInfoDialogOpen} onClose={() => setContactInfoDialogOpen(false)} />

      {/* دیالوگ تأیید خروج از حساب */}
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
