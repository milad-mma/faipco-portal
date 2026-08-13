import { useMemo, useState } from "react";
import { Link as RouterLink, Outlet, useLocation } from "react-router-dom";
import {
  AppBar,
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
  { label: "گزارش اطلاعیه‌ها", path: "/notice-reports", icon: <AssessmentOutlinedIcon />, adminOnly: true },
  {
    label: "مدیریت دسترسی",
    path: "/access",
    icon: <AdminPanelSettingsOutlinedIcon />,
    adminOnly: true,
    children: [
      { label: "واحدهای سازمانی", path: "/departments", icon: <CorporateFareOutlinedIcon /> },
    ],
  },
  { label: "پشتیبان‌گیری", path: "/backup", icon: <CloudDownloadOutlinedIcon />, adminOnly: true },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { mode, toggleMode } = useThemeMode();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuAnchor, setMenuAnchor] = useState(null);
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [snackbar, setSnackbar] = useState("");

  const visibleNavItems = useMemo(
    () =>
      NAV_ITEMS.filter((item) => !item.adminOnly || user?.is_superuser).map((item) => ({
        ...item,
        children: item.children?.filter((child) => !child.adminOnly || user?.is_superuser),
      })),
    [user]
  );

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
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          borderBottom: "1px solid",
          borderColor: "divider",
          backgroundColor: "background.paper",
          zIndex: (theme) => theme.zIndex.drawer + 1,
        }}
      >
        <Toolbar sx={{ justifyContent: "space-between" }}>
          <IconButton
            edge="start"
            sx={{ display: { md: "none" } }}
            onClick={() => setMobileOpen((prev) => !prev)}
          >
            <MenuIcon />
          </IconButton>

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

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minWidth: 0,
          width: { xs: "100%", md: `calc(100% - ${DRAWER_WIDTH}px)` },
          p: { xs: 2, md: 4 },
          mt: 8,
          overflowX: "hidden",
        }}
      >
        <Outlet />
      </Box>

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
