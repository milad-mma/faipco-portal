import { useMemo, useState } from "react";
import { Link as RouterLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  AppBar,
  BottomNavigation,
  BottomNavigationAction,
  Box,
  Collapse,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Snackbar,
  Toolbar,
  Typography,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import DashboardOutlinedIcon from "@mui/icons-material/DashboardOutlined";
import GroupOutlinedIcon from "@mui/icons-material/GroupOutlined";
import ApartmentOutlinedIcon from "@mui/icons-material/ApartmentOutlined";
import CorporateFareOutlinedIcon from "@mui/icons-material/CorporateFareOutlined";
import SyncOutlinedIcon from "@mui/icons-material/SyncOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import AdminPanelSettingsOutlinedIcon from "@mui/icons-material/AdminPanelSettingsOutlined";
import CloudDownloadOutlinedIcon from "@mui/icons-material/CloudDownloadOutlined";
import SystemUpdateAltOutlinedIcon from "@mui/icons-material/SystemUpdateAltOutlined";
import VpnLockOutlinedIcon from "@mui/icons-material/VpnLockOutlined";
import GroupAddOutlinedIcon from "@mui/icons-material/GroupAddOutlined";
import FingerprintOutlinedIcon from "@mui/icons-material/FingerprintOutlined";
import CakeOutlinedIcon from "@mui/icons-material/CakeOutlined";
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import AssessmentOutlinedIcon from "@mui/icons-material/AssessmentOutlined";
import MenuIcon from "@mui/icons-material/Menu";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import LockResetOutlinedIcon from "@mui/icons-material/LockResetOutlined";
import NotificationsActiveOutlinedIcon from "@mui/icons-material/NotificationsActiveOutlined";
import AccountCircleOutlinedIcon from "@mui/icons-material/AccountCircleOutlined";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import { useAuth } from "../context/AuthContext";
import { useThemeMode } from "../context/ThemeModeContext";
import { usePresenceMonitor } from "../utils/presenceSocket";
import ChangePasswordDialog from "./ChangePasswordDialog";
import { enablePushNotifications, getNotificationPermission, isPushSupported } from "../utils/push";
import faipcoLogo from "../assets/faipco-logo.png";

const DRAWER_WIDTH = 260;

// «واحدهای سازمانی» به‌عنوان زیرمجموعه «مدیریت دسترسی» تعریف شده — چون تعیین
// سرپرست واحد یک تصمیم دسترسی/مسئولیت سازمانی است، نه صرفاً داده پرسنلی.
const NAV_ITEMS = [
  { label: "داشبورد", path: "/", icon: <DashboardOutlinedIcon />, adminOnly: true },
  { label: "پرسنل", path: "/employees", icon: <GroupOutlinedIcon />, adminOnly: true },
  { label: "سایت‌ها", path: "/sites", icon: <ApartmentOutlinedIcon />, adminOnly: true },
  { label: "همگام‌سازی دیتابیس", path: "/sync", icon: <SyncOutlinedIcon />, adminOnly: true },
  { label: "اطلاعیه‌ها", path: "/notices", icon: <CampaignOutlinedIcon />, adminOnly: false },
  {
    label: "ثبت ورود و خروج",
    path: "/attendance-clock",
    icon: <FingerprintOutlinedIcon />,
    adminOnly: false,
    requiresClockInOut: true,
    hiddenForAdmin: true,
  },
  {
    label: "گزارش اطلاعیه‌ها",
    path: "/notice-reports",
    icon: <AssessmentOutlinedIcon />,
    adminOnly: false,
    requiresSiteNoticeReport: true,
  },
  {
    label: "مدیریت دسترسی",
    path: "/access",
    icon: <AdminPanelSettingsOutlinedIcon />,
    adminOnly: true,
    children: [
      { label: "واحدهای سازمانی", path: "/departments", icon: <CorporateFareOutlinedIcon /> },
      { label: "رنج‌های IP مجاز", path: "/ip-allowlist", icon: <VpnLockOutlinedIcon /> },
      { label: "انتصاب دسته‌جمعی نقش", path: "/bulk-role-assignment", icon: <GroupAddOutlinedIcon /> },
    ],
  },
  { label: "پشتیبان‌گیری", path: "/backup", icon: <CloudDownloadOutlinedIcon />, adminOnly: true },
  { label: "بررسی و اعمال آپدیت", path: "/update", icon: <SystemUpdateAltOutlinedIcon />, adminOnly: true },
  { label: "پرسنل آنلاین", path: "/presence-report", icon: <ScienceOutlinedIcon />, adminOnly: true },
  {
    label: "گزارش ورود و خروج",
    path: "/clock-in-out-report",
    icon: <FingerprintOutlinedIcon />,
    adminOnly: false,
    requiresClockRecordsView: true,
  },
  {
    label: "پیام‌های تبریک تولد",
    path: "/birthday-messages",
    icon: <CakeOutlinedIcon />,
    adminOnly: false,
    requiresBirthdayMessages: true,
  },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { mode, toggleMode } = useThemeMode();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuAnchor, setMenuAnchor] = useState(null);
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [snackbar, setSnackbar] = useState("");

  const visibleNavItems = useMemo(
    () =>
      NAV_ITEMS.filter((item) => {
        if (item.adminOnly && !user?.is_superuser) return false;
        if (item.requiresClockInOut && !user?.can_clock_in_out) return false;
        if (item.requiresClockRecordsView && !user?.can_view_clock_records) return false;
        if (item.requiresBirthdayMessages && !user?.can_manage_birthday_messages) return false;
        if (item.requiresSiteNoticeReport && !user?.can_view_site_notice_report) return false;
        if (item.hiddenForAdmin && user?.is_superuser) return false;
        return true;
      }).map((item) => ({
        ...item,
        children: item.children?.filter((child) => !child.adminOnly || user?.is_superuser),
      })),
    [user]
  );

  // اگر کاربر فقط یک مقصد قابل‌دسترس دارد (مثلاً یک پرسنل عادی که فقط
  // «اطلاعیه‌ها» را می‌بیند)، نشون‌دادن یک منوی کناری/همبرگری با یک گزینه
  // تکراری بی‌فایده است — چون جایی برای رفتن جز همون صفحه فعلی نیست. کل
  // منو مخفی می‌شود و صفحه تمام‌عرض می‌شود؛ به‌محض این‌که (مثلاً بعداً)
  // مجوز/نقش دومی به این کاربر اضافه شود، همین شرط خودکار false می‌شود و
  // منو دوباره ظاهر می‌شود — بدون نیاز به هیچ تغییر دستی دیگری.
  const hasSingleNavItem = visibleNavItems.length <= 1;

  // ⚠️ این با hasSingleNavItem فرق دارد و باگ واقعی همین تفاوت بود: یک
  // پرسنل عادی که علاوه بر «اطلاعیه‌ها» یک دسترسی دیگر هم دارد (مثلاً
  // ثبت ورود/خروج، یا site_manager با «گزارش اطلاعیه‌ها»)، طبق
  // hasSingleNavItem دیگر «تک‌مقصدی» محسوب نمی‌شد (۲+ آیتم) — یعنی نوار
  // پایین که فقط بر همان شرط بود، برایش هرگز نمایش داده نمی‌شد و به‌جایش
  // Drawer قدیمی می‌دید. نوار پایین باید برای **هر** کاربر غیر-Admin
  // نمایش داده شود، صرف‌نظر از تعداد دقیق مقصدهای اضافه‌اش — مقصدهای
  // اضافه (اگر داشته باشد) از صفحه «پنل کاربری» در دسترس‌اند (پایین‌تر
  // در ProfilePage.jsx).
  //
  // ⚠️ به‌روزرسانی بعدی: قبلاً این فقط MOBILE را عوض می‌کرد (نوار پایین
  // فقط زیر md، Drawer/AppBar فقط بالای md). طبق درخواست صریح، حالا در
  // دسکتاپ هم — به‌جز پنل Admin — همین تجربهٔ «فقط نوار پایین، بدون
  // Sidebar/AppBar» اعمال می‌شود؛ یعنی این متغیر دیگر واقعاً «فقط موبایل»
  // نیست، اسمش هم به همین دلیل عوض شد. hasSingleNavItem برای دسکتاپِ
  // Admin (تصمیم Drawer کامل یا تمام‌عرض) دست‌نخورده باقی مانده.
  const isPersonnelNav = !user?.is_superuser;

  // نشانگر زنده «آنلاین/آفلاین» با WebSocket — دقیقاً مثل یک سیستم چت: تا
  // وقتی این کامپوننت زنده است، یک Session باز نگه داشته می‌شود؛ سرور خودش
  // لحظه‌ی قطع‌شدن (بستن تب/قطعی شبکه/هرچیز دیگر) را تشخیص و مدت‌زمان دقیق
  // را محاسبه می‌کند. فقط برای پرسنلی که وارد آزمایش شده‌اند (can_clock_in_out).
  usePresenceMonitor(Boolean(user?.can_clock_in_out));

  // زیرمنو اگر خودش یا یکی از زیرمجموعه‌هایش فعال باشد، به‌طور پیش‌فرض باز است
  const [openMenus, setOpenMenus] = useState(() => {
    const initial = {};
    NAV_ITEMS.forEach((item) => {
      if (item.children?.length) {
        initial[item.path] =
          location.pathname === item.path ||
          item.children.some((child) => location.pathname.startsWith(child.path));
      }
    });
    return initial;
  });

  const [pushPermission, setPushPermission] = useState(() => getNotificationPermission());

  function toggleMenu(path) {
    setOpenMenus((prev) => ({ ...prev, [path]: !prev[path] }));
  }

  async function handleEnableNotifications() {
    setMenuAnchor(null);
    try {
      await enablePushNotifications();
      setPushPermission(getNotificationPermission());
      setSnackbar("اعلان‌ها با موفقیت فعال شد ✅ — از همین دستگاه اعلان دریافت می‌کنید");
    } catch (err) {
      setPushPermission(getNotificationPermission());
      setSnackbar(err.message || "فعال‌سازی اعلان ناموفق بود");
    }
  }

  const drawerContent = (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Toolbar sx={{ gap: 1.5, px: 3 }}>
        <Box
          component="img"
          src={faipcoLogo}
          alt="FAIPCO"
          sx={{ width: 40, height: 40, objectFit: "contain", flexShrink: 0 }}
        />
        <Typography variant="subtitle1" fontWeight={700} color="primary.main">
          FAIPCO Portal
        </Typography>
      </Toolbar>
      <Divider />
      <List sx={{ px: 1.5, py: 2, flexGrow: 1 }}>
        {visibleNavItems.map((item) => {
          const hasChildren = item.children?.length > 0;
          const isActive =
            location.pathname === item.path ||
            (hasChildren && item.children.some((child) => location.pathname === child.path));
          const isOpen = hasChildren && (openMenus[item.path] ?? false);

          return (
            <Box key={item.path}>
              <Box sx={{ display: "flex", alignItems: "stretch" }}>
                <ListItemButton
                  component={RouterLink}
                  to={item.path}
                  onClick={() => setMobileOpen(false)}
                  selected={isActive}
                  sx={(theme) => ({
                    borderRadius: 2,
                    mb: 0.5,
                    flexGrow: 1,
                    borderInlineEnd: isActive ? "3px solid" : "3px solid transparent",
                    borderInlineEndColor: isActive ? "secondary.main" : "transparent",
                    "&.Mui-selected": {
                      backgroundColor: alpha(theme.palette.primary.main, 0.08),
                    },
                  })}
                >
                  <ListItemIcon sx={{ color: isActive ? "primary.main" : "text.secondary", minWidth: 40 }}>
                    {item.icon}
                  </ListItemIcon>
                  <ListItemText
                    primary={item.label}
                    primaryTypographyProps={{
                      fontWeight: isActive ? 700 : 500,
                      color: isActive ? "primary.main" : "text.primary",
                    }}
                  />
                </ListItemButton>
                {hasChildren && (
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      e.preventDefault();
                      toggleMenu(item.path);
                    }}
                    sx={{ alignSelf: "center", mr: 0.5 }}
                  >
                    {isOpen ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                  </IconButton>
                )}
              </Box>

              {hasChildren && (
                <Collapse in={isOpen} timeout="auto" unmountOnExit>
                  <List component="div" disablePadding>
                    {item.children.map((child) => {
                      const isChildActive = location.pathname === child.path;
                      return (
                        <ListItemButton
                          key={child.path}
                          component={RouterLink}
                          to={child.path}
                          onClick={() => setMobileOpen(false)}
                          selected={isChildActive}
                          sx={(theme) => ({
                            borderRadius: 2,
                            mb: 0.5,
                            pl: 5,
                            borderInlineEnd: isChildActive ? "3px solid" : "3px solid transparent",
                            borderInlineEndColor: isChildActive ? "secondary.main" : "transparent",
                            "&.Mui-selected": {
                              backgroundColor: alpha(theme.palette.primary.main, 0.08),
                            },
                          })}
                        >
                          <ListItemIcon
                            sx={{ color: isChildActive ? "primary.main" : "text.secondary", minWidth: 32 }}
                          >
                            {child.icon}
                          </ListItemIcon>
                          <ListItemText
                            primary={child.label}
                            primaryTypographyProps={{
                              fontSize: 14,
                              fontWeight: isChildActive ? 700 : 500,
                              color: isChildActive ? "primary.main" : "text.primary",
                            }}
                          />
                        </ListItemButton>
                      );
                    })}
                  </List>
                </Collapse>
              )}
            </Box>
          );
        })}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <AppBar
        position="fixed"
        elevation={0}
        color="inherit"
        sx={{
          // پرسنل غیر-Admin که نوار پایین را می‌بیند، دیگر منوی بالای صفحه
          // را هم نمی‌بیند — نه فقط روی موبایل، طبق درخواست صریح روی
          // دسکتاپ هم؛ چون «پنل کاربری» حالا یک تب مستقل در همان نوار
          // پایین است، نه نیاز به منوی بالا هم.
          display: isPersonnelNav ? "none" : "flex",
          width: hasSingleNavItem ? "100%" : { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          borderBottom: "1px solid",
          borderColor: "divider",
          zIndex: (theme) => theme.zIndex.drawer + 1,
        }}
      >
        <Toolbar sx={{ justifyContent: "space-between" }}>
          {!hasSingleNavItem && (
            <IconButton
              edge="start"
              sx={{ display: { md: "none" } }}
              onClick={() => setMobileOpen((prev) => !prev)}
            >
              <MenuIcon />
            </IconButton>
          )}

          <Box />

          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="body2" color="text.secondary">
              خوش آمدید
            </Typography>
            <IconButton onClick={(e) => setMenuAnchor(e.currentTarget)} sx={{ color: "primary.main" }}>
              <AccountCircleOutlinedIcon sx={{ fontSize: 36 }} />
            </IconButton>
            <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={() => setMenuAnchor(null)}>
              {isPushSupported() && (
                <MenuItem onClick={handleEnableNotifications} disabled={pushPermission !== "default"}>
                  <ListItemIcon>
                    <NotificationsActiveOutlinedIcon
                      fontSize="small"
                      color={pushPermission === "granted" ? "success" : "inherit"}
                    />
                  </ListItemIcon>
                  {pushPermission === "granted"
                    ? "اعلان‌ها فعال است ✓"
                    : pushPermission === "denied"
                      ? "اعلان‌ها مسدود شده (از تنظیمات مرورگر باز کنید)"
                      : "فعال‌سازی اعلان‌ها"}
                </MenuItem>
              )}
              <MenuItem
                onClick={() => {
                  toggleMode();
                }}
              >
                <ListItemIcon>
                  {mode === "dark" ? (
                    <LightModeOutlinedIcon fontSize="small" />
                  ) : (
                    <DarkModeOutlinedIcon fontSize="small" />
                  )}
                </ListItemIcon>
                {mode === "dark" ? "استایل کلاسیک (روشن)" : "استایل مدرن (تیره)"}
              </MenuItem>
              <MenuItem
                onClick={() => {
                  setMenuAnchor(null);
                  setPasswordDialogOpen(true);
                }}
              >
                <ListItemIcon>
                  <LockResetOutlinedIcon fontSize="small" />
                </ListItemIcon>
                تغییر رمز عبور
              </MenuItem>
              <MenuItem onClick={logout}>
                <ListItemIcon>
                  <LogoutOutlinedIcon fontSize="small" />
                </ListItemIcon>
                خروج از حساب
              </MenuItem>
            </Menu>
          </Box>
        </Toolbar>
      </AppBar>

      {/*
        نکته مهم RTL: چون stylis-plugin-rtl تمام استایل‌های فیزیکی left/right را
        خودکار Mirror می‌کند، اگر اینجا anchor="right" بگذاریم، در نهایت روی
        صفحه سمت چپ می‌نشیند! برای اینکه واقعاً سمت راست بنشیند، باید anchor="left"
        بدهیم تا بعد از Mirror شدن توسط پلاگین RTL، در سمت راست قرار بگیرد.
      */}
      {!isPersonnelNav && (
        <Drawer
          variant="permanent"
          anchor="left"
          sx={{
            display: { xs: "none", md: "block" },
            width: DRAWER_WIDTH,
            flexShrink: 0,
            "& .MuiDrawer-paper": {
              width: DRAWER_WIDTH,
              boxSizing: "border-box",
              borderInlineEnd: "1px solid",
              borderInlineEndColor: "divider",
              borderInlineStart: "none",
            },
          }}
          open
        >
          {drawerContent}
        </Drawer>
      )}

      {!isPersonnelNav && (
        <Drawer
          variant="temporary"
          anchor="left"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: "block", md: "none" },
            "& .MuiDrawer-paper": { width: DRAWER_WIDTH },
          }}
        >
          {drawerContent}
        </Drawer>
      )}

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minWidth: 0,
          width: isPersonnelNav ? "100%" : { xs: "100%", md: `calc(100% - ${DRAWER_WIDTH}px)` },
          p: { xs: 2, md: 4 },
          // چون منوی بالای صفحه برای پرسنل غیر-Admin کاملاً مخفی است (بالا)،
          // نه فقط موبایل — دیگر هیچ فاصله بالای صفحه‌ای لازم نیست.
          mt: isPersonnelNav ? 0 : 8,
          // چون نوار پایین برای پرسنل غیر-Admin روی هر اندازه صفحه‌ای نمایش
          // داده می‌شود، فضای اضافه پایین صفحه هم همیشه لازم است، نه فقط موبایل.
          // ⚠️ رفع واقعی: قبلاً یک عدد ثابت (۹۶px) بود که safe-area گوشی‌های
          // دارای Home Indicator را حساب نمی‌کرد و روی برخی صفحات/گوشی‌ها
          // کافی نبود — حالا هم بیشتر است (۱۲۰px پایه) هم صریحاً safe-area
          // واقعی گوشی را هم اضافه می‌کند.
          pb: isPersonnelNav ? "calc(120px + env(safe-area-inset-bottom, 0px))" : { xs: 2, md: 4 },
          overflowX: "hidden",
        }}
      >
        <Outlet />
      </Box>

      {/* نوار پایین — برای هر کاربر غیر-Admin (صرف‌نظر از تعداد دقیق
          دسترسی‌های اضافه‌اش — همان باگی که قبلاً روی hasSingleNavItem بود).
          ⚠️ طبق درخواست صریح، دیگر فقط موبایل نیست — روی دسکتاپ هم (به‌جز
          پنل Admin) همین تجربه (بدون Sidebar/AppBar، فقط همین نوار پایین)
          اعمال می‌شود. بر اساس طرح personnel_portal.html کاربر. */}
      {isPersonnelNav && (
        <BottomNavigation
          value={
            location.pathname.startsWith("/profile")
              ? "/profile"
              : location.pathname.startsWith("/notices")
                ? "/notices"
                : "/my-dashboard"
          }
          onChange={(_, newValue) => navigate(newValue)}
          showLabels
          sx={{
            display: "flex",
            position: "fixed",
            bottom: 0,
            insetInline: 0,
            zIndex: (theme) => theme.zIndex.drawer + 2,
            borderTop: "1px solid",
            borderColor: "divider",
            // ⚠️ رفع واقعی مشکل «المان‌ها زیر نوار پایین پنهان می‌شوند»:
            // قبلاً هیچ فضایی برای safe-area (نوار پایین گوشی‌های دارای
            // Home Indicator، مثل آیفون‌های بدون دکمه Home) در نظر گرفته
            // نشده بود — روی آن گوشی‌ها ارتفاع واقعیِ ناحیه قابل‌کلیک نوار
            // پایین بیشتر از ۶۸px می‌شد، و محاسبه pb ثابت پایین‌تر (در Box
            // اصلی) دیگر کافی نبود. حالا height واقعی = ۶۸px + هر مقدار
            // safe-area که مرورگر/گوشی گزارش کند.
            height: `calc(68px + env(safe-area-inset-bottom, 0px))`,
            pb: "env(safe-area-inset-bottom, 0px)",
          }}
        >
          <BottomNavigationAction label="داشبورد" value="/my-dashboard" icon={<DashboardOutlinedIcon />} />
          <BottomNavigationAction label="اطلاعیه‌ها" value="/notices" icon={<CampaignOutlinedIcon />} />
          <BottomNavigationAction label="پنل کاربری" value="/profile" icon={<AccountCircleOutlinedIcon />} />
        </BottomNavigation>
      )}

      <ChangePasswordDialog open={passwordDialogOpen} onClose={() => setPasswordDialogOpen(false)} />

      <Snackbar
        open={Boolean(snackbar)}
        autoHideDuration={4000}
        onClose={() => setSnackbar("")}
        message={snackbar}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      />
    </Box>
  );
}
