/**
 * داشبورد شخصی پرسنل (برخلاف DashboardPage.jsx که آمار سراسری مخصوص Admin است).
 * شامل: کارت پروفایل (با عکس پرسنلی)، تردد امروز از «گزارش تردد ماهانه»، شمارنده اطلاعیه‌های
 * خوانده‌نشده، میان‌برهای گزارش تردد و درخواست مرخصی/ماموریت (با شمارنده درخواست‌های در انتظار)،
 * اطلاعیه‌های اخیر، شبکه ابزارها و متولدین امروز با نوار تبریک.
 *
 * چیدمان با CSS Grid و gridTemplateAreas پیاده شده تا ترتیب موبایل با دسکتاپ متفاوت باشد:
 * در موبایل «اطلاعیه‌های اخیر» بعد از دکمه‌های میان‌بر و پیش از ابزارها می‌آید، در دسکتاپ در
 * ستون کناری است؛ با یک ساختار DOM واحد (order در MUI Grid فقط بین فرزندان یک Container کار می‌کند).
 * قابلیت‌های پیاده‌نشده با برچسب «به‌زودی» و ماژول‌های غیرفعال‌شده با برچسب «غیرفعال» نمایش داده می‌شوند.
 */
import { useEffect, useState } from "react";
import { Avatar, Badge, Box, Card, Chip, Stack, Typography, useMediaQuery } from "@mui/material";
import LoginOutlinedIcon from "@mui/icons-material/LoginOutlined";
import NotificationsNoneOutlinedIcon from "@mui/icons-material/NotificationsNoneOutlined";
import FingerprintOutlinedIcon from "@mui/icons-material/FingerprintOutlined";
import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import AssignmentOutlinedIcon from "@mui/icons-material/AssignmentOutlined";
import ForumOutlinedIcon from "@mui/icons-material/ForumOutlined";
import DirectionsCarFilledOutlinedIcon from "@mui/icons-material/DirectionsCarFilledOutlined";
import HealthAndSafetyOutlinedIcon from "@mui/icons-material/HealthAndSafetyOutlined";
import ApartmentOutlinedIcon from "@mui/icons-material/ApartmentOutlined";
import AccountTreeOutlinedIcon from "@mui/icons-material/AccountTreeOutlined";
import WorkOutlineOutlinedIcon from "@mui/icons-material/WorkOutlineOutlined";
import CakeOutlinedIcon from "@mui/icons-material/CakeOutlined";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { fetchMyNotices } from "../api/notices";
import { fetchMonthlyAttendanceReport } from "../api/monthlyAttendance";
import { gregorianToJalali } from "../utils/jalaliDate";
import { fetchEmployeePhotoThumbnailBlob, fetchTodayBirthdays } from "../api/employees";
import { fetchPendingLeaveRequestCount } from "../api/leaveRequests";
import BirthdayReactionBar from "../components/BirthdayReactionBar";
import DefaultPersonAvatar from "../components/DefaultPersonAvatar";
import EmployeeAvatar from "../components/EmployeeAvatar";
import PerformanceEvaluationToolCard from "../components/PerformanceEvaluationToolCard";

// برچسب «به‌زودی» در گوشه کارت برای قابلیت‌هایی که هنوز در دسترس نیستند
function ComingSoonChip() {
  return (
    <Chip
      label="به‌زودی"
      size="small"
      sx={{ position: "absolute", top: 6, insetInlineEnd: 6, fontSize: 10, height: 18 }}
    />
  );
}

// برچسب «غیرفعال» در گوشه کارت برای ماژول‌هایی که از پنل ادمین غیرفعال شده‌اند
function DisabledChip() {
  return (
    <Chip
      label="غیرفعال"
      size="small"
      color="default"
      sx={{ position: "absolute", top: 6, insetInlineEnd: 6, fontSize: 10, height: 18 }}
    />
  );
}

/**
 * کاشی یک ابزار در شبکه ابزارها.
 * ورودی: آیکون، عنوان، comingSoon/disabled (غیرقابل کلیک و کم‌رنگ با برچسب مربوط) و onClick.
 */
function ToolCard({ icon, label, comingSoon, disabled, onClick }) {
  return (
    <Card
      variant="outlined"
      onClick={comingSoon || disabled ? undefined : onClick}
      sx={{
        position: "relative",
        // حداقل ارتفاع ثابت و مستقل از «متولدین امروز» (دسکتاپ ۱۱۰)؛ height:100% برای
        // هم‌قد ماندن کاشی‌های یک ردیف است (مثلاً وقتی کاشی «ارزیابی عملکرد» شمارنده دارد).
        minHeight: { xs: 82, md: 110 },
        height: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 0.8,
        borderRadius: 2,
        cursor: comingSoon || disabled ? "default" : "pointer",
        opacity: comingSoon || disabled ? 0.55 : 1,
        "&:hover": comingSoon || disabled ? {} : { backgroundColor: "action.hover" },
      }}
    >
      {comingSoon && <ComingSoonChip />}
      {disabled && !comingSoon && <DisabledChip />}
      {/* در دسکتاپ آیکون و متن بزرگ‌تر است (کاشی‌ها در دسکتاپ بلندترند) */}
      <Box sx={{ color: "primary.main", display: "flex", "& svg": { fontSize: { xs: 24, md: 34 } } }}>{icon}</Box>
      <Typography
        variant="caption"
        fontWeight={700}
        textAlign="center"
        sx={{ px: 0.5, fontSize: { xs: "0.75rem", md: "0.95rem" } }}
      >
        {label}
      </Typography>
    </Card>
  );
}

// کامپوننت صفحه؛ داده‌های داشبورد شخصی را بارگذاری و چیدمان Grid را رندر می‌کند
export default function PersonalDashboardPage() {
  const { user } = useAuth();
  const leaveDisabled = Boolean(user?.leave_requests_disabled);  // ماژول مرخصی برای سایت این پرسنل غیرفعال است
  const navigate = useNavigate();
  const [recentNotices, setRecentNotices] = useState(null);
  const [unreadCount, setUnreadCount] = useState(0);  // تعداد کل اطلاعیه‌های خوانده‌نشده
  const [todayAttendance, setTodayAttendance] = useState(null); // { checkIn, checkOut } | "unavailable" | null(loading)
  const [birthdays, setBirthdays] = useState(null);  // متولدین امروز؛ null = در حال بارگذاری
  const [photoUrl, setPhotoUrl] = useState(null);  // Object URL عکس پرسنلی؛ null = بدون عکس
  const [pendingLeaveCount, setPendingLeaveCount] = useState(0);  // تعداد درخواست‌های مرخصی/ماموریت منتظر تصمیم این کاربر
  const isDesktop = useMediaQuery((theme) => theme.breakpoints.up("md"));  // برای تعیین تعداد اطلاعیه‌های اخیر

  // متولدین امروز را (با رعایت تنظیم حریم خصوصی) بارگذاری می‌کند؛ جدا تعریف شده تا پس از
  // ثبت/تغییر واکنش تبریک فقط همین بخش دوباره خوانده شود
  function loadBirthdays() {
    fetchTodayBirthdays({ respectPrivacy: true })
      .then(setBirthdays)
      .catch(() => setBirthdays([]));
  }

  // بارگذاری اولیه: اطلاعیه‌های اخیر، متولدین امروز و شمارنده درخواست‌های در انتظار
  useEffect(() => {
    // ۱۰ اطلاعیه اخیر گرفته می‌شود (دسکتاپ ۱۰ و موبایل ۵ مورد نمایش می‌دهد). شمارنده
    // «خوانده‌نشده» از unread_total سرور است، یعنی همه اطلاعیه‌های خوانده‌نشده، نه فقط موارد نمایش‌داده‌شده.
    fetchMyNotices({ page: 1, pageSize: 10, archived: "all" }).then((data) => {
      setRecentNotices(data.items);
      setUnreadCount(data.unread_total ?? data.items.filter((n) => !n.is_read).length);
    });
    loadBirthdays();
    // شمارنده درخواست‌های مرخصی/ماموریت در انتظار تصمیم این کاربر؛ برای کسی که
    // تأییدکننده نیست صفر برمی‌گردد (نه خطا).
    fetchPendingLeaveRequestCount()
      .then((data) => setPendingLeaveCount(data.pending_count || 0))
      .catch(() => setPendingLeaveCount(0));
  }, []);

  // دریافت عکس پرسنلی به‌صورت Blob، فقط اگر برای کاربر عکس ثبت شده باشد (has_photo از /auth/me)
  // تا برای افراد بدون عکس درخواست ۴۰۴ اضافه ارسال نشود؛ Object URL هنگام پاک‌سازی آزاد می‌شود.
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
    // تردد امروز از «گزارش تردد ماهانه» (داده دستگاه‌های حضور و غیاب) خوانده می‌شود: ردیف روز
    // جاری شمسی پیدا و اولین/آخرین تردد آن استخراج می‌شود. اگر سایت پرسنل نگاشت تردد نداشته
    // باشد (has_monthly_attendance=false)، کارت حالت «به‌زودی» نشان می‌دهد.
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
        // «اولین/آخرین تردد» (نه «ورود/خروج») نمایش داده می‌شود، چون برای پرسنل شب‌کار/گردشی
        // بدون برنامه دقیق شیفت نمی‌توان ورود یا خروج بودن تردد را قطعی تشخیص داد.
        setTodayAttendance({
          firstTransit: transits[0],
          lastTransit: transits.length > 1 ? transits[transits.length - 1] : null,
        });
      })
      .catch(() => setTodayAttendance("unavailable"));
  }, [user?.has_monthly_attendance]);

  // زمان تردد را برای نمایش برمی‌گرداند
  function formatTime(value) {
    // مقدار از گزارش تردد ماهانه رشته آماده HH:MM است و بدون تبدیل نمایش داده می‌شود؛ خالی = «—»
    return value || "—";
  }

  return (
    <Box
      sx={{
        display: "grid",
        gap: 2.5,
        // حداکثر عرض وسط‌چین برای حفظ خوانایی روی مانیتورهای عریض
        maxWidth: 1100,
        mx: "auto",
        gridTemplateColumns: { xs: "1fr", md: "2fr 1fr" },
        // دسکتاپ: کارت‌های ستون اصلی ارتفاع طبیعی خود را دارند و با بلند شدن «متولدین امروز»
        // کشیده نمی‌شوند؛ کارت متولدین هم‌قد ردیف‌های میان‌برها + ابزارها است و فهرستش داخل کارت اسکرول می‌خورد.
        gridTemplateRows: { md: "auto auto auto auto" },
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
          {/* ردیف‌های سایت/واحد/سمت؛ ردیف‌های بدون مقدار حذف می‌شوند */}
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
          {/* اولین/آخرین تردد امروز؛ اگر سایت نگاشت تردد ندارد برچسب «به‌زودی» */}
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
        {/* کارت شمارنده اطلاعیه‌های خوانده‌نشده؛ کلیک به صفحه اطلاعیه‌ها می‌رود */}
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
                minWidth: 24,
                height: 24,
                px: 0.75,
                boxSizing: "border-box",
                borderRadius: 12,
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
        {/* میان‌بر گزارش تردد؛ بدون نگاشت تردد غیرقابل کلیک با برچسب «به‌زودی» */}
        <Card
          variant="outlined"
          onClick={user?.has_monthly_attendance ? () => navigate("/monthly-attendance") : undefined}
          sx={{
            position: "relative",
            flex: 1,
            minHeight: { md: 140 },
            borderRadius: 2,
            p: 1.75,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            cursor: user?.has_monthly_attendance ? "pointer" : "default",
            opacity: user?.has_monthly_attendance ? 1 : 0.55,
          }}
        >
          {!user?.has_monthly_attendance && <ComingSoonChip />}
          <Box
            sx={{
              width: { xs: 38, md: 52 },
              height: { xs: 38, md: 52 },
              "& svg": { fontSize: { xs: 20, md: 28 } },
              borderRadius: "50%",
              bgcolor: "secondary.main",
              color: "secondary.contrastText",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              mb: 2,
            }}
          >
            <FingerprintOutlinedIcon fontSize="small" />
          </Box>
          <Typography fontWeight={800} sx={{ fontSize: { xs: 14, md: 17 } }}>
            گزارش تردد
          </Typography>
        </Card>
        {/* میان‌بر درخواست مرخصی/ماموریت؛ اگر ماژول برای سایت این پرسنل از پنل ادمین غیرفعال
            شده باشد، کارت برچسب «غیرفعال» دارد و قابل کلیک نیست. */}
        <Card
          variant="outlined"
          onClick={leaveDisabled ? undefined : () => navigate("/leave-requests")}
          sx={{
            position: "relative",
            flex: 1,
            minHeight: { md: 140 },
            borderRadius: 2,
            p: 1.75,
            overflow: "visible",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            cursor: leaveDisabled ? "default" : "pointer",
            opacity: leaveDisabled ? 0.55 : 1,
          }}
        >
          {leaveDisabled && <DisabledChip />}
          {/* شمارنده درخواست‌های در انتظار تصمیم؛ فقط برای مدیر/سرپرستی که درخواستی منتظر
              اوست نمایش داده می‌شود (برای بقیه صفر است و Badge پنهان می‌ماند). */}
          <Badge
            color="warning"
            badgeContent={pendingLeaveCount}
            invisible={leaveDisabled || !pendingLeaveCount}
            sx={{ "& .MuiBadge-badge": { overflow: "visible" }, mb: 2 }}
          >
            <Box
              sx={{
                width: { xs: 38, md: 52 },
                height: { xs: 38, md: 52 },
                "& svg": { fontSize: { xs: 20, md: 28 } },
                borderRadius: "50%",
                bgcolor: "primary.main",
                color: "primary.contrastText",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <CalendarMonthOutlinedIcon fontSize="small" />
            </Box>
          </Badge>
          <Typography fontWeight={800} sx={{ fontSize: { xs: 14, md: 17 } }}>
            درخواست مرخصی/ماموریت
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
        {/* فهرست اطلاعیه‌های اخیر: دسکتاپ ۱۰ و موبایل ۵ مورد؛ کلیک روی هر مورد به صفحه اطلاعیه‌ها می‌رود */}
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
            {recentNotices.slice(0, isDesktop ? 10 : 5).map((n) => (
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
          // ردیف‌های کاشی هم‌اندازه‌اند و با کشیده شدن این ناحیه همه با هم بزرگ می‌شوند
          gridAutoRows: "1fr",
          gap: 1.25,
        }}
      >
        <ToolCard icon={<DescriptionOutlinedIcon />} label="فیش حقوقی" onClick={() => navigate("/notices?type=payroll")} />
        <ToolCard icon={<AssignmentOutlinedIcon />} label="فیش کارکرد" onClick={() => navigate("/notices?type=attendance_card")} />
        <PerformanceEvaluationToolCard onClick={() => navigate("/my-performance")} />
        <ToolCard icon={<ForumOutlinedIcon />} label="انتقادات و پیشنهادات" onClick={() => navigate("/feedback")} />
        <ToolCard icon={<DirectionsCarFilledOutlinedIcon />} label="خودروهای من" onClick={() => navigate("/my-vehicles")} />
        {/* کاشی «بیمه تکمیلی»؛ اگر ماژول از پنل غیرفعال شود، مثل کاشی مرخصی برچسب «غیرفعال» می‌گیرد. */}
        <ToolCard
          icon={<HealthAndSafetyOutlinedIcon />}
          label="بیمه تکمیلی"
          disabled={Boolean(user?.insurance_disabled)}
          onClick={() => navigate("/insurance")}
        />
      </Box>

      {/* متولدین امروز؛ اگر امروز تولدی نباشد کارت نمایش داده نمی‌شود */}
      {(birthdays === null || birthdays.length > 0) && (
        <Card
          variant="outlined"
          sx={{
            gridArea: "birthdays",
            borderRadius: 2,
            p: 1.75,
            // دسکتاپ: contain:size یعنی محتوای این کارت در تعیین ارتفاع ردیف‌های Grid نقشی ندارد؛
            // کارت تا انتهای ناحیه‌اش (هم‌قد میان‌برها + ابزارها) کشیده می‌شود و فهرست داخلش اسکرول می‌خورد.
            contain: { md: "size" },
            display: { md: "flex" },
            flexDirection: { md: "column" },
          }}
        >
          <Stack direction="row" spacing={0.8} alignItems="center" sx={{ mb: 1, flexShrink: 0 }}>
            <CakeOutlinedIcon sx={{ fontSize: 17, color: "secondary.main" }} />
            <Typography fontWeight={800} fontSize={14} sx={{ flex: 1 }}>
              متولدین امروز
            </Typography>
            {birthdays?.length > 0 && (
              <Chip label={`${birthdays.length} نفر`} size="small" sx={{ fontSize: 10, height: 20 }} />
            )}
          </Stack>
          {birthdays === null ? (
            <Typography variant="caption" color="text.secondary">
              در حال بارگذاری...
            </Typography>
          ) : (
            <Stack
              spacing={1.5}
              divider={<Box sx={{ borderTop: "1px solid", borderColor: "divider" }} />}
              sx={{ flex: { md: 1 }, minHeight: { md: 0 }, overflowY: { md: "auto" }, paddingInlineEnd: { md: 0.5 } }}
            >
              {birthdays.map((e) => (
                <Box key={e.id}>
                  <Stack direction="row" alignItems="center" spacing={1} sx={{ minHeight: 34 }}>
                    {/* آواتار پرسنل؛ اگر عکس او هنگام Sync از کاراوب ذخیره شده باشد همان نمایش داده می‌شود */}
                    <EmployeeAvatar employeeId={e.id} hasPhoto={e.has_photo} size={30} />
                    {/* نام و واحد سازمانی در یک خط؛ noWrap روی کل ردیف است تا در صورت جا نشدن
                        به‌جای شکستن به خط دوم با «…» کوتاه شود. */}
                    <Typography variant="body2" fontWeight={700} sx={{ minWidth: 0, flex: 1 }} noWrap>
                      {e.first_name} {e.last_name}
                      {e.department_name && (
                        <Typography
                          component="span"
                          variant="caption"
                          color="text.secondary"
                          sx={{ ml: 0.75, fontWeight: 400 }}
                        >
                          — {e.department_name}
                        </Typography>
                      )}
                    </Typography>
                  </Stack>
                  {/* نوار تبریک مستقل برای هر متولد؛ پس از ثبت واکنش فهرست متولدین دوباره خوانده می‌شود */}
                  <BirthdayReactionBar person={e} onChanged={loadBirthdays} />
                </Box>
              ))}
            </Stack>
          )}
        </Card>
      )}
    </Box>
  );
}
