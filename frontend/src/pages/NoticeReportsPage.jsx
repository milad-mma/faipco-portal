import { Box, Card, Typography } from "@mui/material";
import { fetchAdminReport } from "../api/notices";
import NoticeReportTable from "../components/NoticeReportTable";

export default function NoticeReportsPage() {
  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        گزارش اطلاعیه‌ها
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        همه اطلاعیه‌های ارسال‌شده در سیستم — چه کسی، چه زمانی، برای چه کسانی فرستاده و چند نفر دیده‌اند
      </Typography>

      <Card variant="outlined" sx={{ borderRadius: 3, p: 1 }}>
        <NoticeReportTable fetchPage={fetchAdminReport} showSender allowDelete />
      </Card>
    </Box>
  );
}
