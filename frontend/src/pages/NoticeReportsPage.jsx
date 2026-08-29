import { useState } from "react";
import { Box, Card, Stack, Typography } from "@mui/material";
import { fetchAdminReport, fetchSiteReport } from "../api/notices";
import NoticeReportTable from "../components/NoticeReportTable";
import SiteFilterSelect from "../components/SiteFilterSelect";
import { useAuth } from "../context/AuthContext";

export default function NoticeReportsPage() {
  const { user } = useAuth();
  const [siteId, setSiteId] = useState(null);
  // Admin واقعی همه اطلاعیه‌های سیستم را می‌بیند؛ site_manager فقط
  // اطلاعیه‌هایی که به سایت(های) تحت مدیریتش رسیده — از هر فرستنده‌ای، نه
  // فقط اطلاعیه‌های خودش (که آن یکی در تب «ارسالی» داخل صفحه اطلاعیه‌ها است).
  const isFullAdminReport = Boolean(user?.is_superuser);

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        گزارش اطلاعیه‌ها
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {isFullAdminReport
          ? "همه اطلاعیه‌های ارسال‌شده در سیستم — چه کسی، چه زمانی، برای چه کسانی فرستاده و چند نفر دیده‌اند"
          : "همه اطلاعیه‌هایی که به سایت(های) تحت مدیریت شما رسیده — از هر فرستنده‌ای، نه فقط اطلاعیه‌های خودتان"}
      </Typography>

      <Stack direction="row" sx={{ mb: 2 }}>
        <SiteFilterSelect value={siteId} permission="notices.site_report" onChange={setSiteId} />
      </Stack>

      <Card variant="outlined" sx={{ borderRadius: 3, p: 1 }}>
        <NoticeReportTable
          fetchPage={(page, pageSize) =>
            isFullAdminReport ? fetchAdminReport(page, pageSize, siteId) : fetchSiteReport(page, pageSize, siteId)
          }
          showSender
          allowDelete
          reloadKey={siteId}
        />
      </Card>
    </Box>
  );
}
