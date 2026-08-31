import { useEffect, useState } from "react";
import { Avatar, Box, Card, Chip, Stack, Typography } from "@mui/material";
import LoginOutlinedIcon from "@mui/icons-material/LoginOutlined";
import NotificationsNoneOutlinedIcon from "@mui/icons-material/NotificationsNoneOutlined";
import HistoryOutlinedIcon from "@mui/icons-material/HistoryOutlined";
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
import { fetchMonthlyAttendanceReport } from "../api/monthlyAttendance";
import { gregorianToJalali } from "../utils/jalaliDate";
import FeedbackSubmitDialog from "../components/FeedbackSubmitDialog";
import { fetchEmployeePhotoThumbnailBlob, fetchTodayBirthdays } from "../api/employees";
import DefaultPersonAvatar from "../components/DefaultPersonAvatar";

/**
 * داشبورد شخصی پرسنل — بر اساس نمونه HTML ارسالی کاربر (personnel_portal.html).
 * برخلاف DashboardPage.jsx (که آمار سراسری فقط برای Admin است)، این صفحه
 * مخصوص خودِ هر پرسنل است: اطلاعات پروفایل، تردد امروز، اطلاعیه‌های اخیر،
 * و دسترسی سریع به قابلیت‌های مختلف.
 *
 * قابلیت‌هایی که در طرح هستند ولی هنوز در پروژه پیاده نشده‌اند (ارزیابی
 * عملکرد، تیکت IT، نظرسنجی، درخواست مرخصی) با برچسب «به‌زودی» غیرفعال
 * نمایش داده می‌شوند — طبق دستور صریح کارفرما. «خودروهای من» از این
 * لیست خارج شد چون واقعاً پیاده‌سازی و به /my-vehicles وصل شد؛ «انتقادات
 * و پیشنهادات» هم همین‌طور — به FeedbackSubmitDialog.jsx وصل شد.
 *
 * ⚠️ چیدمان با CSS Grid + gridTemplateAreas پیاده شده (نه MUI Grid ساده) —
 * چون طبق بازخورد، ترتیب موبایل باید با دسکتاپ فرق داشته باشد: در موبایل
 * «اطلاعیه‌های اخیر» درست بعد از دکمه‌های «گزارش تردد»/«درخواست مرخصی»
 * می‌آید (قبل از شبکه ابزارها)؛ در دسکتاپ همان ستون کناری قبلی (کنار
 * پروفایل/تردد/ابزارها) باقی می‌ماند. MUI Grid ساده نمی‌تواند این را با
 * یک ساختار DOM واحد پوشش دهد (Order فقط بین Siblingهای همان Container
 * کار می‌کند)، ولی gridTemplateAreas دقیقاً برای همین ساخته شده.
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
        borderRadius: 2,
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
  const [feedbackDialogOpen, setFeedbackDialogOpen] = useState(false);
  const [birthdays, setBirthdays] = useState(null);
  const [photoUrl, setPhotoUrl] = useState(null);

  useEffect(() => {
    fetchMyNotices({ page: 1, pageSize: 5, archived: "all" }).then((data) => {
      setRecentNotices(data.items);
      setUnreadCount(data.items.filter((n) => !n.is_read).length);
    });
    fetchTodayBirthdays({ respectPrivacy: true })
      .then(setBirthdays)
      .catch(() => setBirthdays([]));
  }, []);

  // عکس پرسنلی — مثل تم قبلی، فقط اگر واقعاً برای این کاربر ثبت شده باشد
  // (has_photo از /auth/me)، تا برای اکثر افراد که هنوز عکسشان Sync نشده،
  // یک درخواست ۴۰۴ اضافه به سرور نزنیم.
  useEffect(() => {
    if (!user?.employee_id || !user?.has_photo) {
      setPhotoUrl(null);
      return;
    }
    let objectUrl = null;
    fetchEmployeePhotoThumbnailBlob(user.employee_id)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setPhotoUrl(objectUrl);
      })
      .catch(() => setPhotoUrl(null));
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [user?.employee_id, user?.has_photo]);

  useEffect(() => {
    // ⚠️ طبق درخواست صریح: این کارت دیگر به سیستم آزمایشی GPS وصل نیست —
    // کاملاً با «گزارش تردد ماهانه» (از دستگاه‌های حضور و غیاب واقعی
    // کارخانه) جایگزین شده. اگر سایت این پرسنل نگاشت تردد تنظیم‌شده
    // نداشته باشد (has_monthly_attendance=false)، این کارت حالت «به‌زودی» نشان می‌دهد.
    if (!user?.has_monthly_attendance) {
      setTodayAttendance("unavailable");
      return;
    }
    const { jd: todayJalaliDay } = gregorianToJalali(new Date());
    fetchMonthlyAttendanceReport({})
      .then((report) => {
        const todayEntry = report.days.find((d) => d.day === todayJalaliDay);
        const transits = todayEntry?.transits || [];
        if (transits.length === 0) {
          setTodayAttendance({ firstTransit: null, lastTransit: null });
          return;
        }
        // ⚠️ عمداً «اولین/آخرین تردد» نه «ورود/خروج» — برای پرسنل شب‌کار/
        // گردشی، تشخیص قطعی این‌که کدام تردد واقعاً ورود و کدام خروج بوده
        // بدون دانستن برنامه دقیق شیفت هر نفر ممکن نیست.
        setTodayAttendance({
          firstTransit: transits[0],
          lastTransit: transits.length > 1 ? transits[transits.length - 1] : null,
        });
      })
      .catch(() => setTodayAttendance("unavailable"));
  }, [user?.has_monthly_attendance]);

  function formatTime(value) {
    // ⚠️ منبع جدید (گزارش تردد ماهانه) خودش رشته HH:MM آماده برمی‌گرداند —
    // نه یک شیء Date مثل سیستم قدیمی GPS — پس دیگر نیازی به toLocaleTimeString نیست.
    return value || "—";
  }

  return (
    <Box
      sx={{
        display: "grid",
        gap: 2.5,
        // چون دیگر Drawer/AppBar کنارش نیست (نوار پایین همه‌جا)، این صفحه
        // ممکن است روی دسکتاپ‌های خیلی عریض تمام پهنا را بگیرد — یک
        // maxWidth منطقی، وسط‌چین، خوانایی را روی مانیتورهای بزرگ حفظ می‌کند.
        maxWidth: 1100,
        mx: "auto",
        gridTemplateColumns: { xs: "1fr", md: "2fr 1fr" },
        gridTemplateAreas: {
          xs: `"profile" "stats" "actions" "recent" "tools" "birthdays"`,
          md: `"profile recent" "stats recent" "actions birthdays" "tools birthdays"`,
        },
      }}
    >
      {/* پروفایل */}
      <Card variant="outlined" sx={{ gridArea: "profile", borderRadius: 2, overflow: "hidden" }}>
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
          <Avatar
            src={photoUrl || undefined}
            sx={{
              width: 50,
              height: 50,
              backgroundColor: "rgba(255,255,255,0.18)",
              flexShrink: 0,
            }}
          >
            {!photoUrl && <DefaultPersonAvatar />}
          </Avatar>
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

      {/* تردد امروز + اطلاعیه خوانده‌نشده */}
      <Stack direction="row" spacing={1.5} sx={{ gridArea: "stats" }}>
        <Card variant="outlined" sx={{ flex: 1, borderRadius: 2, p: 1.75 }}>
          <Stack direction="row" spacing={0.8} alignItems="center" sx={{ color: "text.secondary", mb: 1 }}>
            <LoginOutlinedIcon sx={{ fontSize: 16, color: "primary.main" }} />
            <Typography variant="caption">تردد امروز</Typography>
          </Stack>
          {user?.has_monthly_attendance ? (
            <>
              <Stack direction="row" justifyContent="space-between" sx={{ fontSize: 13 }}>
                <Typography variant="caption" color="text.secondary">
                  اولین تردد:
                </Typography>
                <Typography variant="body2" fontWeight={700}>
                  {todayAttendance && todayAttendance !== "unavailable"
                    ? formatTime(todayAttendance.firstTransit)
                    : "—"}
                </Typography>
              </Stack>
              <Stack direction="row" justifyContent="space-between" sx={{ fontSize: 13 }}>
                <Typography variant="caption" color="text.secondary">
                  آخرین تردد:
                </Typography>
                <Typography variant="body2" fontWeight={700}>
                  {todayAttendance && todayAttendance !== "unavailable"
                    ? formatTime(todayAttendance.lastTransit)
                    : "—"}
                </Typography>
              </Stack>
            </>
          ) : (
            <Chip label="به‌زودی" size="small" />
          )}
        </Card>
        <Card
          variant="outlined"
          onClick={() => navigate("/notices")}
          sx={{ flex: 1, borderRadius: 2, p: 1.75, cursor: "pointer", "&:hover": { backgroundColor: "action.hover" } }}
        >
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

      {/* دکمه‌های میانبر: گزارش تردد + درخواست مرخصی */}
      <Stack direction="row" spacing={1.5} sx={{ gridArea: "actions" }}>
        <Card
          variant="outlined"
          onClick={user?.has_monthly_attendance ? () => navigate("/monthly-attendance") : undefined}
          sx={{
            position: "relative",
            flex: 1,
            borderRadius: 2,
            p: 1.75,
            cursor: user?.has_monthly_attendance ? "pointer" : "default",
            opacity: user?.has_monthly_attendance ? 1 : 0.55,
          }}
        >
          {!user?.has_monthly_attendance && <ComingSoonChip />}
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
            <HistoryOutlinedIcon fontSize="small" />
          </Box>
          <Typography fontWeight={800} fontSize={14}>
            گزارش تردد
          </Typography>
        </Card>
        <Card variant="outlined" sx={{ position: "relative", flex: 1, borderRadius: 2, p: 1.75, opacity: 0.55 }}>
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

      {/* اطلاعیه‌های اخیر — در موبایل بعد از دکمه‌های بالا، در دسکتاپ ستون کناری */}
      <Card variant="outlined" sx={{ gridArea: "recent", borderRadius: 2, p: 1.75 }}>
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
                  {new Date(n.publish_at || n.created_at).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" })}
                </Typography>
              </Stack>
            ))}
          </Stack>
        )}
      </Card>

      {/* شبکه ابزارها */}
      <Box
        sx={{
          gridArea: "tools",
          display: "grid",
          gridTemplateColumns: { xs: "repeat(3, 1fr)", sm: "repeat(6, 1fr)", md: "repeat(3, 1fr)" },
          gap: 1.25,
        }}
      >
        <ToolCard icon={<DescriptionOutlinedIcon />} label="فیش حقوقی" onClick={() => navigate("/notices?type=payroll")} />
        <ToolCard icon={<AssignmentOutlinedIcon />} label="فیش کارکرد" onClick={() => navigate("/notices?type=attendance_card")} />
        <ToolCard icon={<SpeedOutlinedIcon />} label="ارزیابی عملکرد" comingSoon />
        <ToolCard icon={<ForumOutlinedIcon />} label="انتقادات و پیشنهادات" onClick={() => setFeedbackDialogOpen(true)} />
        <ToolCard icon={<DirectionsCarFilledOutlinedIcon />} label="خودروهای من" onClick={() => navigate("/my-vehicles")} />
        <ToolCard icon={<SupportAgentOutlinedIcon />} label="تیکت IT" comingSoon />
      </Box>

      {/* متولدین امروز */}
      {(birthdays === null || birthdays.length > 0) && (
        <Card variant="outlined" sx={{ gridArea: "birthdays", borderRadius: 2, p: 1.75 }}>
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
      )}

      <FeedbackSubmitDialog open={feedbackDialogOpen} onClose={() => setFeedbackDialogOpen(false)} />
    </Box>
  );
}
