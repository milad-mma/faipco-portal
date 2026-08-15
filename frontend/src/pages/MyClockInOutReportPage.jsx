import { useEffect, useState } from "react";
import { Alert, Box, Card, Chip, CircularProgress, Divider, Stack, Typography } from "@mui/material";
import LoginOutlinedIcon from "@mui/icons-material/LoginOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import { fetchMyAttendanceLogs } from "../api/attendance";
import { monoFontSx } from "../theme";

const LOG_TYPE_LABELS = {
  check_in: { label: "ورود", color: "success", icon: <LoginOutlinedIcon fontSize="small" /> },
  check_out: { label: "خروج", color: "default", icon: <LogoutOutlinedIcon fontSize="small" /> },
};

export default function MyClockInOutReportPage() {
  const [logs, setLogs] = useState(null);

  useEffect(() => {
    fetchMyAttendanceLogs().then(setLogs);
  }, []);

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        گزارش ورود و خروج من
      </Typography>
      <Alert severity="warning" icon={<ScienceOutlinedIcon />} sx={{ mb: 3 }}>
        این قابلیت آزمایشی است — این فقط تاریخچه ثبت‌های خودِ شماست، نه گزارش رسمی حضور و غیاب.
      </Alert>

      <Card variant="outlined" sx={{ borderRadius: 3 }}>
        {logs === null ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
            <CircularProgress size={24} />
          </Box>
        ) : logs.length === 0 ? (
          <Box sx={{ px: 2.5, py: 3 }}>
            <Typography variant="body2" color="text.secondary">
              هنوز هیچ ثبتی ندارید.
            </Typography>
          </Box>
        ) : (
          logs.map((log, index) => {
            const meta = LOG_TYPE_LABELS[log.log_type] || { label: log.log_type, color: "default" };
            return (
              <Box key={log.id}>
                {index > 0 && <Divider />}
                <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 2.5, py: 1.5 }}>
                  <Chip size="small" color={meta.color} icon={meta.icon} label={meta.label} />
                  <Typography variant="body2" sx={monoFontSx}>
                    {new Date(log.created_at).toLocaleString("fa-IR")}
                  </Typography>
                </Stack>
              </Box>
            );
          })
        )}
      </Card>
    </Box>
  );
}
