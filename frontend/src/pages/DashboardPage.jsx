import { useEffect, useState } from "react";
import { Box, Card, Chip, Grid, Skeleton, Typography } from "@mui/material";
import GroupOutlinedIcon from "@mui/icons-material/GroupOutlined";
import ApartmentOutlinedIcon from "@mui/icons-material/ApartmentOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import CorporateFareOutlinedIcon from "@mui/icons-material/CorporateFareOutlined";
import SyncOutlinedIcon from "@mui/icons-material/SyncOutlined";
import PersonOffOutlinedIcon from "@mui/icons-material/PersonOffOutlined";
import { fetchEmployeeCount, fetchPortalDisabledCount } from "../api/employees";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import { fetchMyNotices, fetchNoticeStatsSummary } from "../api/notices";
import { fetchSyncStatusSummary } from "../api/sync";
import { useAuth } from "../context/AuthContext";

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
            backgroundColor: `${color}1A`,
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

export default function DashboardPage() {
  const { user } = useAuth();
  const [employeeCount, setEmployeeCount] = useState(null);
  const [activeSiteCount, setActiveSiteCount] = useState(null);
  const [departmentStats, setDepartmentStats] = useState(null); // { total, withoutSupervisor }
  const [syncSummary, setSyncSummary] = useState(null);
  const [weeklyNoticeCount, setWeeklyNoticeCount] = useState(null);
  const [portalDisabledCount, setPortalDisabledCount] = useState(null);
  const [notices, setNotices] = useState([]);

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
    fetchMyNotices().then(setNotices);
  }, []);

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        خوش آمدید، {user?.username}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>
        نمای کلی وضعیت پرتال سازمانی
      </Typography>

      <Grid container spacing={2.5} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={4}>
          <StatCard icon={<GroupOutlinedIcon />} label="پرسنل فعال" value={employeeCount} color="#103498" />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <StatCard icon={<ApartmentOutlinedIcon />} label="سایت‌های فعال" value={activeSiteCount} color="#536DB5" />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
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

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
        <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
          آخرین اطلاعیه‌های من
        </Typography>
        {notices.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            در حال حاضر اطلاعیه‌ای برای شما ثبت نشده است.
          </Typography>
        )}
        {notices.slice(0, 5).map((notice) => (
          <Box
            key={notice.id}
            sx={{
              py: 1.5,
              borderBottom: "1px solid",
              borderColor: "divider",
              "&:last-of-type": { borderBottom: "none" },
            }}
          >
            <Typography variant="body1" fontWeight={600}>
              {notice.title}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {notice.body}
            </Typography>
          </Box>
        ))}
      </Card>
    </Box>
  );
}
