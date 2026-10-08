/**
 * داشبورد مدیریتی: کارت‌های آماری (پرسنل فعال، سایت‌های فعال، واحدها و سرپرست،
 * وضعیت همگام‌سازی امروز، اطلاعیه‌های هفته، پرسنل بدون دسترسی پرتال) **به تفکیک سایت**:
 * بالای کارت‌ها انتخاب سایت («همه‌ی سایت‌ها» یا یک سایت). در حالت «همه»، هر کارت جمع کل را با یک خط تفکیک
 * («صفادشت ۲۱۰ · دفتر مرکزی ۴۵») نشان می‌دهد؛ با انتخاب سایت فقط آمار همان سایت. داده از GET /dashboard/site-stats.
 * فهرست متولدین امروز (با همان فیلتر سایت) و برای Admin کارت‌های آمار استفاده و وضعیت سرور.
 */
import { useEffect, useMemo, useState } from "react";
import { Avatar, Box, Card, Chip, Grid, Skeleton, Stack, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import GroupOutlinedIcon from "@mui/icons-material/GroupOutlined";
import ApartmentOutlinedIcon from "@mui/icons-material/ApartmentOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import CorporateFareOutlinedIcon from "@mui/icons-material/CorporateFareOutlined";
import SyncOutlinedIcon from "@mui/icons-material/SyncOutlined";
import PersonOffOutlinedIcon from "@mui/icons-material/PersonOffOutlined";
import CakeOutlinedIcon from "@mui/icons-material/CakeOutlined";
import { fetchTodayBirthdays } from "../api/employees";
import { fetchDashboardSiteStats } from "../api/dashboard";
import { useAuth } from "../context/AuthContext";
import UsageStatsCard from "../components/UsageStatsCard";
import ServerStatsCard from "../components/ServerStatsCard";

const faNum = (n) => Number(n || 0).toLocaleString("fa-IR");
const SYNC_LABELS = { success: "موفق", failed: "ناموفق", partial: "نیمه‌موفق", running: "در حال اجرا", not_run: "اجرا نشده" };

/**
 * کارت یک شاخص آماری.
 * ورودی: آیکون، عنوان، مقدار (null = اسکلتون در حال بارگذاری)، رنگ، متن/رنگ برچسب کمکی اختیاری و
 * breakdown: خط تفکیک سایت‌ها («صفادشت ۲۱۰ · دفتر مرکزی ۴۵») در حالت «همه‌ی سایت‌ها».
 */
function StatCard({ icon, label, value, color, helperText, helperColor, breakdown }) {
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
      {breakdown && breakdown.length > 1 && (
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 1.5 }}>
          {breakdown.map((b) => (
            <Chip
              key={b.label}
              size="small"
              variant="outlined"
              color={b.color || "default"}
              label={`${b.label}: ${b.value}`}
              sx={{ height: 22, fontSize: 11 }}
            />
          ))}
        </Stack>
      )}
    </Card>
  );
}

// کامپوننت صفحه؛ آمارها را یک‌بار هنگام ورود از سرور می‌گیرد و کارت‌ها را رندر می‌کند
export default function DashboardPage() {
  const { user } = useAuth();
  const theme = useTheme();
  const [siteStats, setSiteStats] = useState(null); // آمار هر سایت (null = در حال بارگذاری)
  const [selectedSite, setSelectedSite] = useState("all"); // "all" یا site_id
  const [birthdays, setBirthdays] = useState([]); // پرسنلی که امروز تولدشان است

  // بارگذاری آمارهای داشبورد هنگام نمایش صفحه
  useEffect(() => {
    fetchDashboardSiteStats()
      .then(setSiteStats)
      .catch(() => setSiteStats([]));
    fetchTodayBirthdays().then(setBirthdays);
  }, []);

  // سایت‌های انتخاب‌شده (همه یا یکی) و جمع شاخص‌ها روی آن‌ها
  const shown = useMemo(() => {
    if (!siteStats) return null;
    return selectedSite === "all" ? siteStats : siteStats.filter((s) => s.site_id === selectedSite);
  }, [siteStats, selectedSite]);
  const sum = (key) => (shown ? shown.reduce((acc, s) => acc + (s[key] || 0), 0) : null);
  // خط تفکیک سایت‌ها زیر هر کارت؛ فقط در حالت «همه» و وقتی بیش از یک سایت هست
  const breakdown = (key, format = faNum, colorOf) =>
    selectedSite === "all" && shown
      ? shown.map((s) => ({ label: s.site_name, value: format(s[key], s), color: colorOf?.(s) }))
      : null;

  const employeeCount = sum("employees_active");
  const portalDisabledCount = sum("portal_disabled");
  const activeSiteCount = siteStats ? siteStats.length : null;
  const departmentStats = shown
    ? { total: sum("departments_total"), withoutSupervisor: sum("departments_without_supervisor") }
    : null;
  // همگام‌سازی: فقط سایت‌هایی که کاربر مجوز دیدنشان را دارد (sync_today غیر null)
  const syncSites = shown ? shown.filter((s) => s.sync_today !== null) : null;
  const syncSummary = syncSites
    ? {
        total_sites: syncSites.length,
        success_today: syncSites.filter((s) => s.sync_today === "success").length,
        failed_today: syncSites.filter((s) => s.sync_today === "failed" || s.sync_today === "partial").length,
        not_run_today: syncSites.filter((s) => s.sync_today === "not_run").length,
      }
    : null;
  const noticeSites = shown ? shown.filter((s) => s.notices_week !== null) : null;
  const weeklyNoticeCount = noticeSites ? noticeSites.reduce((acc, s) => acc + s.notices_week, 0) : null;
  const selectedSiteName = selectedSite === "all" ? null : siteStats?.find((s) => s.site_id === selectedSite)?.site_name;
  const shownBirthdays =
    selectedSite === "all" ? birthdays : birthdays.filter((emp) => emp.site_name === selectedSiteName);

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        خوش آمدید، {user?.username}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        نمای کلی وضعیت پرتال سازمانی
      </Typography>

      {/* انتخاب سایت: کارت‌ها برای همه‌ی سایت‌ها (با خط تفکیک) یا فقط یک سایت */}
      {siteStats && siteStats.length > 1 && (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2.5 }}>
          <Chip
            label="همه‌ی سایت‌ها"
            color={selectedSite === "all" ? "primary" : "default"}
            variant={selectedSite === "all" ? "filled" : "outlined"}
            onClick={() => setSelectedSite("all")}
          />
          {siteStats.map((s) => (
            <Chip
              key={s.site_id}
              icon={<ApartmentOutlinedIcon />}
              label={s.site_name}
              color={selectedSite === s.site_id ? "primary" : "default"}
              variant={selectedSite === s.site_id ? "filled" : "outlined"}
              onClick={() => setSelectedSite(s.site_id)}
            />
          ))}
        </Stack>
      )}

      {/* شبکه کارت‌های آماری */}
      <Grid container spacing={2.5} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={4}>
          <StatCard
            icon={<GroupOutlinedIcon />}
            label="پرسنل فعال"
            value={employeeCount === null ? null : faNum(employeeCount)}
            color={theme.palette.primary.main}
            breakdown={breakdown("employees_active")}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          {selectedSite === "all" ? (
            <StatCard icon={<ApartmentOutlinedIcon />} label="سایت‌های فعال" value={activeSiteCount} color={theme.palette.primary.light} />
          ) : (
            <StatCard
              icon={<ApartmentOutlinedIcon />}
              label="سایت انتخاب‌شده"
              value={selectedSiteName || "—"}
              color={theme.palette.primary.light}
              helperText="برای دیدن همه، «همه‌ی سایت‌ها» را بزنید"
            />
          )}
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          {/* واحدها؛ برچسب کمکی تعداد واحدهای بدون سرپرست را هشدار می‌دهد */}
          <StatCard
            icon={<CorporateFareOutlinedIcon />}
            label="واحدهای سازمانی"
            value={departmentStats === null ? null : faNum(departmentStats.total)}
            color="#3A6EA5"
            breakdown={breakdown(
              "departments_total",
              (v, s) => (s.departments_without_supervisor ? `${faNum(v)} (${faNum(s.departments_without_supervisor)} بی‌سرپرست)` : faNum(v)),
              (s) => (s.departments_without_supervisor ? "warning" : "default"),
            )}
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
            value={syncSummary === null ? null : `${faNum(syncSummary.success_today)}/${faNum(syncSummary.total_sites)}`}
            color="#2F855A"
            breakdown={
              selectedSite === "all" && syncSites
                ? syncSites.map((s) => ({
                    label: s.site_name,
                    value: SYNC_LABELS[s.sync_today] || s.sync_today,
                    color: s.sync_today === "success" ? "success" : s.sync_today === "not_run" ? "default" : "error",
                  }))
                : null
            }
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
            label={selectedSite === "all" ? "اطلاعیه‌های کل سیستم (۷ روز اخیر)" : "اطلاعیه‌های این سایت (۷ روز اخیر)"}
            value={weeklyNoticeCount === null ? null : faNum(weeklyNoticeCount)}
            color="#C97A2B"
            breakdown={
              selectedSite === "all" && noticeSites
                ? noticeSites.map((s) => ({ label: s.site_name, value: faNum(s.notices_week) }))
                : null
            }
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <StatCard
            icon={<PersonOffOutlinedIcon />}
            label="پرسنل بدون دسترسی پرتال"
            value={portalDisabledCount === null ? null : faNum(portalDisabledCount)}
            color="#B23A48"
            breakdown={breakdown("portal_disabled", faNum, (s) => (s.portal_disabled ? "error" : "default"))}
          />
        </Grid>
      </Grid>

      {/* کارت متولدین امروز */}
      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: user?.is_superuser ? 3 : 0 }}>
        <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
          🎂 متولدین روز جاری
        </Typography>
        {shownBirthdays.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            {selectedSite === "all" ? "امروز تولد هیچ‌کدام از پرسنل نیست." : "امروز تولد هیچ‌کدام از پرسنل این سایت نیست."}
          </Typography>
        )}
        <Stack spacing={0}>
          {shownBirthdays.map((emp) => (
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
