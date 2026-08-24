import { useEffect, useState } from "react";
import { Box, Card, Chip, Grid, Stack, Typography } from "@mui/material";
import LoginOutlinedIcon from "@mui/icons-material/LoginOutlined";
import NotificationsNoneOutlinedIcon from "@mui/icons-material/NotificationsNoneOutlined";
import RouteOutlinedIcon from "@mui/icons-material/RouteOutlined";
import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import AssignmentOutlinedIcon from "@mui/icons-material/AssignmentOutlined";
import SpeedOutlinedIcon from "@mui/icons-material/SpeedOutlined";
import ForumOutlinedIcon from "@mui/icons-material/ForumOutlined";
import DirectionsCarFilledOutlinedIcon from "@mui/icons-material/DirectionsCarFilledOutlined";
import SupportAgentOutlinedIcon from "@mui/icons-material/SupportAgentOutlined";
import ApartmentOutlinedIcon from "@mui/icons-material/ApartmentOutlined";
import AccountTreeOutlinedIcon from "@mui/icons-material/AccountTreeOutlined";
import WorkOutlineOutlinedIcon from "@mui/icons-material/WorkOutlineOutlined";
import CakeOutlinedIcon from "@mui/icons-material/CakeOutlined";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { fetchMyNotices } from "../api/notices";
import { fetchMyAttendanceLogs } from "../api/attendance";
import { fetchTodayBirthdays } from "../api/employees";
import DefaultPersonAvatar from "../components/DefaultPersonAvatar";

/**
 * داشبورد شخصی پرسنل — بر اساس نمونه HTML ارسالی کاربر (personnel_portal.html).
 * برخلاف DashboardPage.jsx (که آمار سراسری فقط برای Admin است)، این صفحه
 * مخصوص خودِ هر پرسنل است: اطلاعات پروفایل، تردد امروز، اطلاعیه‌های اخیر،
 * و دسترسی سریع به قابلیت‌های مختلف.
 *
 * قابلیت‌هایی که در طرح هستند ولی هنوز در پروژه پیاده نشده‌اند (ارزیابی
 * عملکرد، تیکت IT، خودروهای من، نظرسنجی و انتقادات، درخواست مرخصی) با
 * برچسب «به‌زودی» غیرفعال نمایش داده می‌شوند — طبق دستور صریح کارفرما.
 */

function ComingSoonChip() {
  return (
    <Chip
      label="به‌زودی"
      size="small"
      sx={{ position: "absolute", top: 6, insetInlineEnd: 6, fontSize: 10, height: 18 }}
    />
  );
}

function ToolCard({ icon, label, comingSoon, onClick }) {
  return (
    <Card
      variant="outlined"
      onClick={comingSoon ? undefined : onClick}
      sx={{
        position: "relative",
        height: 82,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 0.8,
        borderRadius: 3,
        cursor: comingSoon ? "default" : "pointer",
        opacity: comingSoon ? 0.55 : 1,
        "&:hover": comingSoon ? {} : { backgroundColor: "action.hover" },
      }}
    >
      {comingSoon && <ComingSoonChip />}
      <Box sx={{ color: "primary.main", display: "flex" }}>{icon}</Box>
      <Typography variant="caption" fontWeight={700} textAlign="center" sx={{ px: 0.5 }}>
        {label}
      </Typography>
    </Card>
  );
}

export default function PersonalDashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [recentNotices, setRecentNotices] = useState(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [todayAttendance, setTodayAttendance] = useState(null); // { checkIn, checkOut } | "unavailable" | null(loading)
  const [birthdays, setBirthdays] = useState(null);

  useEffect(() => {
    fetchMyNotices({ page: 1, pageSize: 3 }).then((data) => {
      setRecentNotices(data.items);
      setUnreadCount(data.items.filter((n) => !n.is_read).length);
    });
    fetchTodayBirthdays()
      .then(setBirthdays)
      .catch(() => setBirthdays([]));
  }, []);

  useEffect(() => {
    if (!user?.can_clock_in_out) {
      setTodayAttendance("unavailable");
      return;
    }
    const now = new Date();
    fetchMyAttendanceLogs({ year: undefined, month: undefined })
      .then((data) => {
        const todayStr = now.toLocaleDateString("en-CA"); // YYYY-MM-DD مستقل از تایم‌زون نمایش
        const todayLogs = data.items.filter(
          (log) => new Date(log.created_at).toLocaleDateString("en-CA") === todayStr
        );
        const checkIn = todayLogs.find((l) => l.log_type === "check_in");
        const checkOut = [...todayLogs].reverse().find((l) => l.log_type === "check_out");
        setTodayAttendance({
          checkIn: checkIn ? new Date(checkIn.created_at) : null,
          checkOut: checkOut ? new Date(checkOut.created_at) : null,
        });
      })
      .catch(() => setTodayAttendance("unavailable"));
  }, [user?.can_clock_in_out]);

  function formatTime(date) {
    return date ? date.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" }) : "—";
  }

  return (
    // در موبایل یک ستون (مثل نمونه HTML)؛ در دسکتاپ دو ستون — ستون اصلی
    // (پروفایل/تردد/دسترسی سریع/ابزارها) و یک ستون کناری (اطلاعیه‌ها +
    // متولدین) — تا فضای صفحه دسکتاپ درست استفاده شود، نه یک ستون باریک
    // وسط‌چین که شبیه موبایل بماند.
    <Grid container spacing={2.5}>
      <Grid item xs={12} md={8}>
        <Stack spacing={2.5}>
          <Card variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
            <Box
              sx={{
                background: "linear-gradient(90deg, #185E95 0%, #2E84AA 100%)",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                p: 1.75,
              }}
            >
              <Box>
                <Typography fontWeight={800} fontSize={17}>
                  {user?.first_name} {user?.last_name}
                </Typography>
                <Typography fontSize={12} sx={{ opacity: 0.85 }}>
                  کد پرسنلی: {user?.personnel_code || "—"}
                </Typography>
              </Box>
              <Box
                sx={{
                  width: 50,
                  height: 50,
                  borderRadius: "50%",
                  backgroundColor: "rgba(255,255,255,0.18)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <DefaultPersonAvatar />
              </Box>
            </Box>
            <Stack sx={{ px: 1.75, py: 1 }}>
              {[
                { icon: <ApartmentOutlinedIcon fontSize="small" />, label: "سایت", value: user?.site_name },
                { icon: <AccountTreeOutlinedIcon fontSize="small" />, label: "واحد سازمانی", value: user?.department_name },
                { icon: <WorkOutlineOutlinedIcon fontSize="small" />, label: "سمت", value: user?.position_title },
              ]
                .filter((row) => row.value)
                .map((row) => (
                  <Stack
                    key={row.label}
                    direction="row"
                    alignItems="center"
                    justifyContent="space-between"
                    sx={{ minHeight: 32, borderBottom: "1px solid", borderColor: "divider", "&:last-child": { borderBottom: "none" } }}
                  >
                    <Stack direction="row" spacing={0.8} alignItems="center" sx={{ color: "text.secondary" }}>
                      <Box sx={{ color: "primary.main", display: "flex" }}>{row.icon}</Box>
                      <Typography variant="caption">{row.label}</Typography>
                    </Stack>
                    <Typography variant="body2" fontWeight={700}>
                      {row.value}
                    </Typography>
                  </Stack>
                ))}
            </Stack>
          </Card>

          <Stack direction="row" spacing={1.5}>
            <Card variant="outlined" sx={{ flex: 1, borderRadius: 3, p: 1.75 }}>
              <Stack direction="row" spacing={0.8} alignItems="center" sx={{ color: "text.secondary", mb: 1 }}>
                <LoginOutlinedIcon sx={{ fontSize: 16, color: "primary.main" }} />
                <Typography variant="caption">تردد امروز</Typography>
              </Stack>
              {user?.can_clock_in_out ? (
                <>
                  <Stack direction="row" justifyContent="space-between" sx={{ fontSize: 13 }}>
                    <Typography variant="caption" color="text.secondary">
                      ورود:
                    </Typography>
                    <Typography variant="body2" fontWeight={700}>
                      {todayAttendance && todayAttendance !== "unavailable" ? formatTime(todayAttendance.checkIn) : "—"}
                    </Typography>
                  </Stack>
                  <Stack direction="row" justifyContent="space-between" sx={{ fontSize: 13 }}>
                    <Typography variant="caption" color="text.secondary">
                      خروج:
                    </Typography>
                    <Typography variant="body2" fontWeight={700}>
                      {todayAttendance && todayAttendance !== "unavailable" ? formatTime(todayAttendance.checkOut) : "—"}
                    </Typography>
                  </Stack>
                </>
              ) : (
                <Chip label="به‌زودی" size="small" />
              )}
            </Card>
            <Card variant="outlined" sx={{ flex: 1, borderRadius: 3, p: 1.75 }}>
              <Stack direction="row" spacing={0.8} alignItems="center" sx={{ color: "text.secondary", mb: 1 }}>
                <NotificationsNoneOutlinedIcon sx={{ fontSize: 16, color: "primary.main" }} />
                <Typography variant="caption">اطلاعیه</Typography>
              </Stack>
              <Stack direction="row" spacing={1} alignItems="center">
                <Box
                  sx={{
                    width: 24,
                    height: 24,
                    borderRadius: "50%",
                    bgcolor: "error.main",
                    color: "#fff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 12,
                    fontWeight: 700,
                  }}
                >
                  {unreadCount}
                </Box>
                <Typography variant="caption" fontWeight={700}>
                  خوانده‌نشده
                </Typography>
              </Stack>
            </Card>
          </Stack>

          <Stack direction="row" spacing={1.5}>
            <Card
              variant="outlined"
              onClick={user?.can_clock_in_out ? () => navigate("/attendance-clock") : undefined}
              sx={{
                position: "relative",
                flex: 1,
                borderRadius: 3,
                p: 1.75,
                cursor: user?.can_clock_in_out ? "pointer" : "default",
                opacity: user?.can_clock_in_out ? 1 : 0.55,
              }}
            >
              {!user?.can_clock_in_out && <ComingSoonChip />}
              <Box
                sx={{
                  width: 38,
                  height: 38,
                  borderRadius: "50%",
                  bgcolor: "secondary.main",
                  color: "secondary.contrastText",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  mb: 2,
                }}
              >
                <RouteOutlinedIcon fontSize="small" />
              </Box>
              <Typography fontWeight={800} fontSize={14}>
                گزارش تردد
              </Typography>
            </Card>
            <Card variant="outlined" sx={{ position: "relative", flex: 1, borderRadius: 3, p: 1.75, opacity: 0.55 }}>
              <ComingSoonChip />
              <Box
                sx={{
                  width: 38,
                  height: 38,
                  borderRadius: "50%",
                  bgcolor: "primary.main",
                  color: "primary.contrastText",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  mb: 2,
                }}
              >
                <CalendarMonthOutlinedIcon fontSize="small" />
              </Box>
              <Typography fontWeight={800} fontSize={14}>
                درخواست مرخصی
              </Typography>
            </Card>
          </Stack>

          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "repeat(3, 1fr)", sm: "repeat(6, 1fr)" }, gap: 1.25 }}>
            <ToolCard icon={<DescriptionOutlinedIcon />} label="فیش حقوقی" onClick={() => navigate("/notices")} />
            <ToolCard icon={<AssignmentOutlinedIcon />} label="فیش کارکرد" onClick={() => navigate("/notices")} />
            <ToolCard icon={<SpeedOutlinedIcon />} label="ارزیابی عملکرد" comingSoon />
            <ToolCard icon={<ForumOutlinedIcon />} label="نظرسنجی و انتقادات" comingSoon />
            <ToolCard icon={<DirectionsCarFilledOutlinedIcon />} label="خودروهای من" comingSoon />
            <ToolCard icon={<SupportAgentOutlinedIcon />} label="تیکت IT" comingSoon />
          </Box>
        </Stack>
      </Grid>

      <Grid item xs={12} md={4}>
        <Stack spacing={2.5}>
          <Card variant="outlined" sx={{ borderRadius: 3, p: 1.75 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
              <Typography fontWeight={800} fontSize={14}>
                اطلاعیه‌های اخیر
              </Typography>
              <Chip
                label="همه"
                size="small"
                onClick={() => navigate("/notices")}
                sx={{ fontSize: 10, height: 20, cursor: "pointer" }}
              />
            </Stack>
            {recentNotices === null ? (
              <Typography variant="caption" color="text.secondary">
                در حال بارگذاری...
              </Typography>
            ) : recentNotices.length === 0 ? (
              <Typography variant="caption" color="text.secondary">
                اطلاعیه‌ای برای نمایش نیست.
              </Typography>
            ) : (
              <Stack spacing={1}>
                {recentNotices.map((n) => (
                  <Stack
                    key={n.id}
                    direction="row"
                    justifyContent="space-between"
                    alignItems="center"
                    spacing={1}
                    onClick={() => navigate("/notices")}
                    sx={{ cursor: "pointer" }}
                  >
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 0 }}>
                      <Box sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: "primary.main", flexShrink: 0 }} />
                      <Typography variant="caption" noWrap>
                        {n.title}
                      </Typography>
                    </Stack>
                    <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0, fontSize: 10 }}>
                      {new Date(n.publish_at || n.created_at).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" })}
                    </Typography>
                  </Stack>
                ))}
              </Stack>
            )}
          </Card>

          <Card variant="outlined" sx={{ borderRadius: 3, p: 1.75 }}>
            <Stack direction="row" spacing={0.8} alignItems="center" sx={{ mb: 1 }}>
              <CakeOutlinedIcon sx={{ fontSize: 17, color: "secondary.main" }} />
              <Typography fontWeight={800} fontSize={14}>
                متولدین امروز
              </Typography>
            </Stack>
            {birthdays === null ? (
              <Typography variant="caption" color="text.secondary">
                در حال بارگذاری...
              </Typography>
            ) : birthdays.length === 0 ? (
              <Typography variant="caption" color="text.secondary">
                امروز کسی تولد ندارد.
              </Typography>
            ) : (
              <Stack spacing={1}>
                {birthdays.map((e) => (
                  <Stack key={e.id} direction="row" alignItems="center" spacing={1} sx={{ minHeight: 34 }}>
                    <Box
                      sx={{
                        width: 30,
                        height: 30,
                        borderRadius: "50%",
                        bgcolor: "action.hover",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                        color: "text.secondary",
                      }}
                    >
                      <DefaultPersonAvatar />
                    </Box>
                    <Typography variant="body2" fontWeight={700} noWrap>
                      {e.first_name} {e.last_name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" noWrap>
                      {e.department_name}
                    </Typography>
                  </Stack>
                ))}
              </Stack>
            )}
          </Card>
        </Stack>
      </Grid>
    </Grid>
  );
}
