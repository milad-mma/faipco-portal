import { useEffect, useState } from "react";
import { Badge, Box, Card, Chip, Stack, Typography } from "@mui/material";
import SpeedOutlinedIcon from "@mui/icons-material/SpeedOutlined";
import { fetchMyEvaluationDashboardSummary } from "../api/evaluationProcess";

/**
 * کاشی «ارزیابی عملکرد» در داشبورد پرسنل - جایگزین نسخه قبلی («به‌زودی»).
 *
 * ⚠️ طبق درخواست صریح: امتیاز هرگز روی خودِ کارت داشبورد نمایش داده
 * نمی‌شود (محرمانه است) - فقط یک برچسب «محرمانه» نشان می‌دهد که نتیجه‌ای
 * وجود دارد؛ امتیاز واقعی فقط داخل صفحه (بعد از کلیک) نمایش داده می‌شود.
 * برای سرپرست/مدیر، یک Badge با تعداد ارزیابی‌های در انتظار انجام هم
 * اضافه می‌شود (این عدد محرمانه نیست - فقط یک یادآوری کاری است).
 */
export default function PerformanceEvaluationToolCard({ onClick }) {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    fetchMyEvaluationDashboardSummary()
      .then(setSummary)
      .catch(() => setSummary(null));
  }, []);

  const hasResult = summary?.results_count > 0;

  return (
    <Card
      variant="outlined"
      onClick={onClick}
      sx={{
        position: "relative",
        height: 82,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 0.6,
        borderRadius: 2,
        cursor: "pointer",
        "&:hover": { backgroundColor: "action.hover" },
      }}
    >
      <Badge
        color="warning"
        badgeContent={summary?.pending_to_evaluate_count || 0}
        invisible={!summary?.pending_to_evaluate_count}
      >
        <Box sx={{ color: "primary.main", display: "flex" }}>
          <SpeedOutlinedIcon />
        </Box>
      </Badge>
      <Typography variant="caption" fontWeight={700} textAlign="center" sx={{ px: 0.5 }}>
        ارزیابی عملکرد
      </Typography>
      {hasResult && (
        <Stack direction="row" alignItems="center">
          <Chip label="محرمانه" size="small" color="default" sx={{ height: 18, fontSize: 10 }} />
        </Stack>
      )}
    </Card>
  );
}
