/**
 * داشبورد مدیریتی: کارت‌های آماری (پرسنل فعال، سایت‌های فعال، واحدها و سرپرست،
 * وضعیت همگام‌سازی امروز، اطلاعیه‌های هفته، پرسنل بدون دسترسی پرتال)،
 * فهرست متولدین امروز و برای Admin کارت‌های آمار استفاده و وضعیت سرور.
 */
import { useEffect, useState } from "react";
import { Avatar, Box, Card, Chip, Grid, Skeleton, Stack, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import GroupOutlinedIcon from "@mui/icons-material/GroupOutlined";
import ApartmentOutlinedIcon from "@mui/icons-material/ApartmentOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import CorporateFareOutlinedIcon from "@mui/icons-material/CorporateFareOutlined";
import SyncOutlinedIcon from "@mui/icons-material/SyncOutlined";
import PersonOffOutlinedIcon from "@mui/icons-material/PersonOffOutlined";
import CakeOutlinedIcon from "@mui/icons-material/CakeOutlined";
import { fetchEmployeeCount, fetchPortalDisabledCount, fetchTodayBirthdays } from "../api/employees";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import { fetchNoticeStatsSummary } from "../api/notices";
import { fetchSyncStatusSummary } from "../api/sync";
import { useAuth } from "../context/AuthContext";
import UsageStatsCard from "../components/UsageStatsCard";
import ServerStatsCard from "../components/ServerStatsCard";

/**
 * کارت یک شاخص آماری.
 * ورودی: آیکون، عنوان، مقدار (null = اسکلتون در حال بارگذاری)، رنگ و متن/رنگ برچسب کمکی اختیاری.
 */
function StatCard({ icon, label, value, color, helperText, helperColor }) {
  return (
    <Card variant="outlined" sx={{ p: 3, borderRadius: 3, height: "100%" }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
        <Box
          sx={{
            width: 48,
            height: 48,
            borderRadius: 2.5,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: `${color}1A`,  // همان رنگ با شفافیت حدود ۱۰٪ (آلفای هگز 1A)
            color: color,
            flexShrink: 0,
          }}
        >
          {icon}
        </Box>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h5" fontWeight={700}>
            {value === null ? <Skeleton width={40} /> : value}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {label}
          </Typography>
        </Box>
      </Box>
      {helperText && (
        <Chip
          size="small"
          label={helperText}
          color={helperColor || "default"}
          variant="outlined"
          sx={{ mt: 1.5 }}
        />
      )}
    </Card>
  );
}

// کامپوننت صفحه؛ آمارها را یک‌بار هنگام ورود از سرور می‌گیرد و کارت‌ها را رندر می‌کند
export default function DashboardPage() {
  const { user } = useAuth();
  const theme = useTheme();
  const [employeeCount, setEmployeeCount] = useState(null);
  const [activeSiteCount, setActiveSiteCount] = useState(null);
  const [departmentStats, setDepartmentStats] = useState(null); // { total, withoutSupervisor }
  const [syncSummary, setSyncSummary] = useState(null);  // خلاصه همگام‌سازی امروز: success_today / failed_today / not_run_today / total_sites
  const [weeklyNoticeCount, setWeeklyNoticeCount] = useState(null);
  const [portalDisabledCount, setPortalDisabledCount] = useState(null);
  const [birthdays, setBirthdays] = useState([]);  // پرسنلی که امروز تولدشان است

  // بارگذاری هم‌زمان همه آمارهای داشبورد هنگام نمایش صفحه
  useEffect(() => {
    fetchEmployeeCount().then(setEmployeeCount);
    fetchSites().then((data) => setActiveSiteCount(data.filter((s) => s.is_active).length));
    fetchDepartments().then((data) =>
      setDepartmentStats({
        total: data.length,
        withoutSupervisor: data.filter((d) => !d.supervisor_user_id).length,
      })
    );
    fetchSyncStatusSummary().then(setSyncSummary);
    fetchNoticeStatsSummary().then((data) => setWeeklyNoticeCount(data.published_this_week));
    fetchPortalDisabledCount().then(setPortalDisabledCount);
    fetchTodayBirthdays().then(setBirthdays);
  }, []);

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        خوش آمدید، {user?.username}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        نمای کلی وضعیت پرتال سازمانی
      </Typography>

      {/* شبکه کارت‌های آماری */}
      <Grid container spacing={2.5} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={4}>
          <StatCard icon={<GroupOutlinedIcon />} label="پرسنل فعال" value={employeeCount} color={theme.palette.primary.main} />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <StatCard icon={<ApartmentOutlinedIcon />} label="سایت‌های فعال" value={activeSiteCount} color={theme.palette.primary.light} />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          {/* واحدها؛ برچسب کمکی تعداد واحدهای بدون سرپرست را هشدار می‌دهد */}
          <StatCard
            icon={<CorporateFareOutlinedIcon />}
            label="واحدهای سازمانی"
            value={departmentStats === null ? null : departmentStats.total}
            color="#3A6EA5"
            helperText={
              departmentStats && departmentStats.withoutSupervisor > 0
                ? `${departmentStats.withoutSupervisor} واحد بدون سرپرست`
                : departmentStats
                  ? "همه واحدها سرپرست دارند"
                  : undefined
            }
            helperColor={departmentStats && departmentStats.withoutSupervisor > 0 ? "warning" : "success"}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          {/* همگام‌سازی امروز: تعداد سایت‌های موفق از کل؛ برچسب کمکی ناموفق/اجرانشده را نشان می‌دهد */}
          <StatCard
            icon={<SyncOutlinedIcon />}
            label="همگام‌سازی امروز"
            value={syncSummary === null ? null : `${syncSummary.success_today}/${syncSummary.total_sites}`}
            color="#2F855A"
            helperText={
              syncSummary && syncSummary.failed_today > 0
                ? `${syncSummary.failed_today} سایت ناموفق`
                : syncSummary && syncSummary.not_run_today > 0
                  ? `${syncSummary.not_run_today} سایت هنوز اجرا نشده`
                  : syncSummary
                    ? "همه موفق"
                    : undefined
            }
            helperColor={syncSummary && syncSummary.failed_today > 0 ? "error" : "success"}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <StatCard
            icon={<CampaignOutlinedIcon />}
            label="اطلاعیه‌های کل سیستم (۷ روز اخیر)"
            value={weeklyNoticeCount}
            color="#C97A2B"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <StatCard
            icon={<PersonOffOutlinedIcon />}
            label="پرسنل بدون دسترسی پرتال"
            value={portalDisabledCount}
            color="#B23A48"
          />
        </Grid>
      </Grid>

      {/* کارت متولدین امروز */}
      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: user?.is_superuser ? 3 : 0 }}>
        <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
          🎂 متولدین روز جاری
        </Typography>
        {birthdays.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            امروز تولد هیچ‌کدام از پرسنل نیست.
          </Typography>
        )}
        <Stack spacing={0}>
          {birthdays.map((emp) => (
            <Box
              key={emp.id}
              sx={{
                py: 1.5,
                display: "flex",
                alignItems: "center",
                gap: 2,
                borderBottom: "1px solid",
                borderColor: "divider",
                "&:last-of-type": { borderBottom: "none" },
              }}
            >
              <Avatar sx={{ bgcolor: "secondary.main", color: "secondary.contrastText" }}>
                <CakeOutlinedIcon />
              </Avatar>
              <Box sx={{ minWidth: 0 }}>
                <Typography variant="body1" fontWeight={600}>
                  {emp.first_name} {emp.last_name}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {[emp.department_name, emp.site_name].filter(Boolean).join(" — ") || "—"}
                </Typography>
              </Box>
            </Box>
          ))}
        </Stack>
      </Card>

      {/* فقط Admin — چون خودِ Endpoint هم فقط با مجوز system.backup پاسخ می‌دهد */}
      {user?.is_superuser && (
        <Stack spacing={3}>
          <UsageStatsCard />
          <ServerStatsCard />
        </Stack>
      )}
    </Box>
  );
}
