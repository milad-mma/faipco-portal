/**
 * پوسته‌ی اصلی صفحات پس از ورود (Layout).
 * بدون ورودی (props)؛ کاربر، برندینگ و حالت تم را از Context می‌خواند.
 * برای ادمین: AppBar بالا + منوی کناری (Drawer دائمی در دسکتاپ، موقت در موبایل) با آیتم‌های فیلترشده بر اساس مجوز.
 * برای پرسنل غیرادمین: فقط نوار پایین (BottomNavigation) در همه‌ی اندازه‌ها.
 * صفحه‌ی جاری از طریق <Outlet /> رندر می‌شود؛ دیالوگ تغییر رمز، اطلاعیه‌ی پاپ‌آپ و Snackbar پیام‌ها هم اینجا هستند.
 */
import { useEffect, useMemo, useState } from "react";
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
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
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
import { useBranding } from "../context/BrandingContext";
import { useThemeMode } from "../context/ThemeModeContext";
import { usePresenceMonitor } from "../utils/presenceSocket";
import AnnouncementDialog from "./AnnouncementDialog";
import BrandLogo, { surfaceTitleSx } from "./BrandLogo";
import ChangePasswordDialog from "./ChangePasswordDialog";
import { enablePushNotifications, getNotificationPermission, isPushSupported } from "../utils/push";
import { NAV_ITEMS, isItemVisible } from "../config/navItems";

const DRAWER_WIDTH = 260;  // عرض منوی کناری (px)؛ عرض AppBar و main هم بر اساس آن محاسبه می‌شود


export default function Layout() {
  const { user, logout } = useAuth();
  const { sidebarTitle, surfaces } = useBranding();
  const sidebarCfg = surfaces.sidebar;
  const { mode, toggleMode } = useThemeMode();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);  // باز بودن Drawer موقت در موبایل (ادمین)
  const [menuAnchor, setMenuAnchor] = useState(null);  // عنصر لنگر منوی پروفایل؛ null = منو بسته
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [snackbar, setSnackbar] = useState("");  // متن پیام Snackbar؛ رشته‌ی خالی = پنهان

  // آیتم‌های منو را بر اساس مجوز کاربر فیلتر می‌کند و مسیر مؤثر هر آیتم والد را تعیین می‌کند.
  const visibleNavItems = useMemo(
    () =>
      NAV_ITEMS.filter((item) => isItemVisible(item, user)).map((item) => {
        // فرزندان مستقل از والد فیلتر می‌شوند؛ کاربر ممکن است فقط بعضی از زیرمنوها را ببیند.
        const filteredChildren = item.children?.filter((child) => isItemVisible(child, user));

        // اگر صفحه‌ی خودِ والد (ownPageCheck در navItems.jsx) برای کاربر در دسترس نیست ولی
        // حداقل یک فرزند در دسترس است، کلیک روی والد به اولین فرزند در‌دسترس می‌رود.
        let effectivePath = item.path;
        if (item.ownPageCheck && !item.ownPageCheck(user) && filteredChildren?.length) {
          effectivePath = filteredChildren[0].path;
        }
        // گروه بدون صفحه‌ی مستقل (groupOnly): همیشه به اولین زیرمنوی در‌دسترس می‌رود
        if (item.groupOnly && filteredChildren?.length) {
          effectivePath = filteredChildren[0].path;
        }

        // menuKey ثابت (مسیر تعریف‌شده در navItems) برای کلید React و وضعیت باز/بسته‌ی گروه،
        // مستقل از effectivePath
        return { ...item, menuKey: item.path, path: effectivePath, children: filteredChildren };
      }),
    [user]
  );

  // اگر کاربر حداکثر یک مقصد در دسترس داشته باشد، منوی کناری/همبرگری پنهان
  // و محتوا تمام‌عرض می‌شود (در پوسته‌ی ادمین).
  const hasSingleNavItem = visibleNavItems.length <= 1;

  // کاربر غیرادمین (پرسنل) در همه‌ی اندازه‌های صفحه فقط نوار پایین را می‌بیند (بدون AppBar و Drawer)،
  // صرف‌نظر از تعداد مقصدهایش؛ مقصدهای اضافه از صفحه‌ی «پنل کاربری» (ProfilePage.jsx) در دسترس‌اند.
  // hasSingleNavItem فقط برای پوسته‌ی ادمین (Drawer کامل یا تمام‌عرض) به کار می‌رود.
  const isPersonnelNav = !user?.is_superuser;

  // نشانگر زنده‌ی آنلاین/آفلاین با WebSocket: تا وقتی این کامپوننت mount است یک Session باز می‌ماند
  // و سرور لحظه‌ی قطع اتصال و مدت‌زمان حضور را محاسبه می‌کند. فقط برای کاربرانی با can_clock_in_out فعال است.
  usePresenceMonitor(Boolean(user?.can_clock_in_out));

  // وضعیت باز/بسته‌ی زیرمنوها (کلید: مسیر والد)؛ گروهی که خودش یا یکی از فرزندانش فعال است، پیش‌فرض باز است
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

  const [pushPermission, setPushPermission] = useState(() => getNotificationPermission());  // وضعیت اجازه‌ی اعلان مرورگر: default / granted / denied

  // اگر اجازه‌ی اعلان از قبل داده شده، در هر بار باز شدن پنل اشتراک Push را بی‌صدا دوباره به سرور می‌فرستد
  // تا اشتراکی که توسط مرورگر/سیستم‌عامل نامعتبر یا عوض شده، تازه شود (پرامپت جدیدی نمایش داده نمی‌شود).
  useEffect(() => {
    if (getNotificationPermission() === "granted") {
      enablePushNotifications().catch(() => {
        // خطا نادیده گرفته می‌شود؛ تلاشی پس‌زمینه‌ای است و در بار بعدی تکرار می‌شود.
      });
    }
  }, []);

  // باز/بسته کردن زیرمنوی یک آیتم والد
  function toggleMenu(path) {
    setOpenMenus((prev) => ({ ...prev, [path]: !prev[path] }));
  }

  // فعال‌سازی اعلان Push از منوی پروفایل: درخواست اجازه، ثبت اشتراک و نمایش نتیجه در Snackbar
  async function handleEnableNotifications() {
    setMenuAnchor(null);
    try {
      await enablePushNotifications();
      setPushPermission(getNotificationPermission());
      setSnackbar("اعلان‌ها با موفقیت فعال شد ✅ — از همین دستگاه اعلان دریافت می‌کنید");
    } catch (err) {
      setPushPermission(getNotificationPermission());
      setSnackbar(err.message || "فعال‌سازی اعلان با خطا مواجه شد");
    }
  }

  // محتوای منوی کناری (مشترک بین Drawer دائمی و موقت): لوگو/عنوان و فهرست آیتم‌ها با زیرمنوهای جمع‌شونده
  const drawerContent = (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* سربرگ منو: لوگو و عنوان سایدبار */}
      <Toolbar sx={{ gap: 1.5, px: 3, background: sidebarCfg.background || undefined }}>
        <BrandLogo surface="sidebar" alt={sidebarTitle} />
        {sidebarCfg.show_title && (
          <Typography sx={{ color: "primary.main", ...surfaceTitleSx(sidebarCfg, "title") }}>{sidebarTitle}</Typography>
        )}
      </Toolbar>
      <Divider />
      {/* فهرست آیتم‌های منو */}
      <List sx={{ px: 1.5, py: 2, flexGrow: 1 }}>
        {visibleNavItems.map((item) => {
          const hasChildren = item.children?.length > 0;
          const isActive =
            location.pathname === item.path ||
            (hasChildren && item.children.some((child) => location.pathname === child.path));
          const isOpen = hasChildren && (openMenus[item.menuKey] ?? false);

          return (
            <Box key={item.menuKey}>
              <Box sx={{ display: "flex", alignItems: "stretch" }}>
                {/* لینک اصلی آیتم؛ آیتم فعال با رنگ و نوار کناری مشخص می‌شود */}
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
                {/* دکمه‌ی باز/بسته کردن زیرمنو (بدون ناوبری) */}
                {hasChildren && (
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      e.preventDefault();
                      toggleMenu(item.menuKey);
                    }}
                    sx={{ alignSelf: "center", mr: 0.5 }}
                  >
                    {isOpen ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                  </IconButton>
                )}
              </Box>

              {/* زیرمنوهای جمع‌شونده */}
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
    <Box
      sx={{
        display: "flex",
        // ادمین: جهت row تا Drawer دائمی کنار محتوا قرار بگیرد؛ پرسنل: ستونی (محتوا + نوار پایین)
        flexDirection: isPersonnelNav ? "column" : "row",
        ...(isPersonnelNav
          ? {
              // پرسنل: پوسته دقیقاً هم‌ارتفاع Viewport با overflow:hidden است و هرگز اسکرول نمی‌شود؛
              // فقط ناحیه‌ی main اسکرول می‌خورد و نوار پایین فرزند عادی آخر ستون Flex است،
              // پس همیشه پایین صفحه دیده می‌شود و روی محتوا نمی‌افتد.
              // از 100dvh استفاده می‌شود تا ارتفاع با فضای واقعی قابل‌مشاهده (با وجود نوار آدرس مرورگر موبایل)
              // هماهنگ باشد؛ 100vh برای مرورگرهایی که dvh را نمی‌شناسند جایگزین است.
              height: "100vh",
              "@supports (height: 100dvh)": {
                height: "100dvh",
              },
              overflow: "hidden",
            }
          : {
              // ادمین: حداقل ارتفاع به اندازه‌ی Viewport؛ اسکرول عادی صفحه
              minHeight: "100vh",
            }),
      }}
    >
      {/* نوار بالای صفحه (فقط ادمین): دکمه‌ی منوی موبایل و منوی پروفایل */}
      <AppBar
        position="fixed"
        elevation={0}
        color="inherit"
        sx={{
          // پرسنل نوار بالا را نمی‌بینند؛ «پنل کاربری» یک تب در نوار پایین است
          display: isPersonnelNav ? "none" : "flex",
          width: hasSingleNavItem ? "100%" : { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          borderBottom: "1px solid",
          borderColor: "divider",
          zIndex: (theme) => theme.zIndex.drawer + 1,
          // AppBar ثابت بالای صفحه است؛ فاصله‌ی ناحیه‌ی امن بالا (ناچ / Dynamic Island) در حالت
          // viewport-fit=cover اعمال می‌شود تا دکمه‌ها قابل لمس بمانند.
          pt: "env(safe-area-inset-top, 0px)",
        }}
      >
        <Toolbar sx={{ justifyContent: "space-between" }}>
          {/* دکمه‌ی همبرگری فقط در موبایل و فقط وقتی بیش از یک مقصد وجود دارد */}
          {!hasSingleNavItem && (
            <IconButton
              edge="start"
              sx={{ display: { md: "none" } }}
              onClick={() => setMobileOpen((prev) => !prev)}
            >
              <MenuIcon />
            </IconButton>
          )}

          {/* فضای خالی برای هل دادن بخش پروفایل به انتهای نوار */}
          <Box />

          {/* خوش‌آمدگویی و منوی پروفایل: اعلان‌ها، تغییر تم، تغییر رمز و خروج */}
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
        در RTL، stylis-plugin-rtl مقادیر فیزیکی left/right را برعکس می‌کند؛ بنابراین anchor="left"
        پس از برعکس‌شدن، Drawer را در سمت راست صفحه قرار می‌دهد. (Drawer دائمی: فقط دسکتاپ ادمین)
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

      {/* Drawer موقت برای موبایل ادمین؛ با دکمه‌ی همبرگری باز می‌شود */}
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

      {/* ناحیه‌ی اصلی محتوا؛ صفحه‌ی جاری از طریق Outlet اینجا رندر می‌شود */}
      <Box
        component="main"
        sx={{
          minWidth: 0,
          width: isPersonnelNav ? "100%" : { xs: "100%", md: `calc(100% - ${DRAWER_WIDTH}px)` },
          p: { xs: 2, md: 4 },
          ...(isPersonnelNav
            ? {
                // پرسنل: flex:1 تمام فضای باقی‌مانده‌ی ستون را می‌گیرد و خودِ این Box با overflowY:auto اسکرول می‌شود.
                flex: 1,
                overflowY: "auto",
                overflowX: "hidden",
                mt: 0,
                // چون index.html با viewport-fit=cover تعریف شده و پوسته‌ی پرسنل AppBar ندارد،
                // فاصله‌ی ناحیه‌ی امن بالا (ناچ / Dynamic Island) به padding بالا اضافه می‌شود تا
                // اولین عنصر هر صفحه قابل لمس باشد.
                pt: "calc(16px + env(safe-area-inset-top, 0px))",
              }
            : {
                // ادمین: فاصله‌ی بالا به اندازه‌ی AppBar ثابت
                flexGrow: 1,
                mt: 8,
                overflowX: "hidden",
              }),
        }}
      >
        <Outlet />
      </Box>

      {/* نوار پایین برای همه‌ی کاربران غیرادمین در همه‌ی اندازه‌های صفحه: داشبورد، اطلاعیه‌ها و پنل کاربری.
          تب فعال از روی پیشوند مسیر جاری تعیین می‌شود. */}
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
            // position:fixed نیست؛ فرزند آخر ستون Flex پوسته است و چون پوسته هم‌ارتفاع Viewport است
            // همیشه پایین صفحه می‌ماند. ارتفاع و padding پایین، ناحیه‌ی امن پایین را هم در نظر می‌گیرند.
            display: "flex",
            flexShrink: 0,
            borderTop: "1px solid",
            borderColor: "divider",
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

      {/* اطلاعیه‌ی پاپ‌آپ اینجا mount می‌شود چون Layout فقط برای کاربر واردشده رندر می‌شود
          (در صفحه‌ی ورود درخواستش با 401 رد می‌شد). */}
      <AnnouncementDialog />

      {/* پیام نتیجه‌ی فعال‌سازی اعلان */}
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
