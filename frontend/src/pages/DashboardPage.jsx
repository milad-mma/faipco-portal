import { useEffect, useState } from "react";
import { Box, Card, Grid, Skeleton, Typography } from "@mui/material";
import GroupOutlinedIcon from "@mui/icons-material/GroupOutlined";
import ApartmentOutlinedIcon from "@mui/icons-material/ApartmentOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import { fetchEmployees } from "../api/employees";
import { fetchSites } from "../api/sites";
import { fetchMyNotices } from "../api/notices";
import { useAuth } from "../context/AuthContext";

function StatCard({ icon, label, value, color }) {
  return (
    <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
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
          }}
        >
          {icon}
        </Box>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            {value === null ? <Skeleton width={40} /> : value}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {label}
          </Typography>
        </Box>
      </Box>
    </Card>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [employeeCount, setEmployeeCount] = useState(null);
  const [siteCount, setSiteCount] = useState(null);
  const [notices, setNotices] = useState([]);

  useEffect(() => {
    fetchEmployees().then((data) => setEmployeeCount(data.length));
    fetchSites().then((data) => setSiteCount(data.length));
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
        <Grid item xs={12} sm={4}>
          <StatCard
            icon={<GroupOutlinedIcon />}
            label="پرسنل فعال"
            value={employeeCount}
            color="#16324F"
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <StatCard
            icon={<ApartmentOutlinedIcon />}
            label="سایت‌های سازمان"
            value={siteCount}
            color="#1F4B75"
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <StatCard
            icon={<CampaignOutlinedIcon />}
            label="اطلاعیه‌های من"
            value={notices.length}
            color="#C97A2B"
          />
        </Grid>
      </Grid>

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
        <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
          آخرین اطلاعیه‌ها
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
