import { useState } from "react";
import { Link as RouterLink, Outlet, useLocation } from "react-router-dom";
import {
  AppBar,
  Avatar,
  Box,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Toolbar,
  Typography,
} from "@mui/material";
import DashboardOutlinedIcon from "@mui/icons-material/DashboardOutlined";
import GroupOutlinedIcon from "@mui/icons-material/GroupOutlined";
import ApartmentOutlinedIcon from "@mui/icons-material/ApartmentOutlined";
import SyncOutlinedIcon from "@mui/icons-material/SyncOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import MenuIcon from "@mui/icons-material/Menu";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import { useAuth } from "../context/AuthContext";

const DRAWER_WIDTH = 260;

const NAV_ITEMS = [
  { label: "داشبورد", path: "/", icon: <DashboardOutlinedIcon /> },
  { label: "پرسنل", path: "/employees", icon: <GroupOutlinedIcon /> },
  { label: "سایت‌ها", path: "/sites", icon: <ApartmentOutlinedIcon /> },
  { label: "مدیریت Sync", path: "/sync", icon: <SyncOutlinedIcon /> },
  { label: "اطلاعیه‌ها", path: "/notices", icon: <CampaignOutlinedIcon /> },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuAnchor, setMenuAnchor] = useState(null);

  const drawerContent = (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Toolbar sx={{ gap: 1.5, px: 3 }}>
        <Box
          sx={{
            width: 36,
            height: 36,
            borderRadius: "10px",
            background: "linear-gradient(135deg, #16324F 0%, #1F4B75 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "secondary.main",
            fontWeight: 800,
            fontSize: 16,
          }}
        >
          F
        </Box>
        <Typography variant="subtitle1" fontWeight={700} color="primary.main">
          FAIPCO Portal
        </Typography>
      </Toolbar>
      <Divider />
      <List sx={{ px: 1.5, py: 2, flexGrow: 1 }}>
        {NAV_ITEMS.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <ListItemButton
              key={item.path}
              component={RouterLink}
              to={item.path}
              selected={isActive}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                borderInlineEnd: isActive ? "3px solid" : "3px solid transparent",
                borderInlineEndColor: isActive ? "secondary.main" : "transparent",
                "&.Mui-selected": {
                  backgroundColor: "rgba(22, 50, 79, 0.08)",
                },
              }}
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
          );
        })}
      </List>
    </Box>
  );

  return (
    <Box sx={{ display: "flex" }}>
      <AppBar
        position="fixed"
        elevation={0}
        color="inherit"
        sx={{
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          borderBottom: "1px solid",
          borderColor: "divider",
          backgroundColor: "background.paper",
        }}
      >
        <Toolbar sx={{ justifyContent: "space-between" }}>
          <IconButton
            edge="start"
            sx={{ display: { md: "none" } }}
            onClick={() => setMobileOpen(true)}
          >
            <MenuIcon />
          </IconButton>

          <Box />

          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <Typography variant="body2" color="text.secondary">
              {user?.username}
            </Typography>
            <Avatar
              onClick={(e) => setMenuAnchor(e.currentTarget)}
              sx={{ cursor: "pointer", bgcolor: "primary.main", width: 36, height: 36, fontSize: 14 }}
            >
              {user?.username?.slice(0, 2)?.toUpperCase()}
            </Avatar>
            <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={() => setMenuAnchor(null)}>
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

      {/* Drawer دسکتاپ */}
      <Drawer
        variant="permanent"
        anchor="right"
        sx={{
          display: { xs: "none", md: "block" },
          width: DRAWER_WIDTH,
          flexShrink: 0,
          "& .MuiDrawer-paper": {
            width: DRAWER_WIDTH,
            boxSizing: "border-box",
            borderLeft: "1px solid",
            borderColor: "divider",
            borderRight: "none",
          },
        }}
        open
      >
        {drawerContent}
      </Drawer>

      {/* Drawer موبایل */}
      <Drawer
        variant="temporary"
        anchor="right"
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
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          p: { xs: 2, md: 4 },
          mt: 8,
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
}
