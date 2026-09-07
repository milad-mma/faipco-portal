import { useEffect, useState } from "react";
import { Badge, Box, Card, Typography } from "@mui/material";
import SpeedOutlinedIcon from "@mui/icons-material/SpeedOutlined";
import { fetchMyEvaluationDashboardSummary } from "../api/evaluationProcess";

/**
 * کاشی «ارزیابی عملکرد» در داشبورد پرسنل - جایگزین نسخه قبلی («به‌زودی»).
 * برای پرسنل عادی: امتیاز آخرین ارزیابی خودش را نشان می‌دهد.
 * برای سرپرست/مدیر (کسانی که Assignment ای به‌عنوان ارزیاب دارند): یک
 * Badge با تعداد ارزیابی‌های در انتظار انجام هم اضافه می‌شود.
 */
export default function PerformanceEvaluationToolCard({ onClick }) {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    fetchMyEvaluationDashboardSummary()
      .then(setSummary)
      .catch(() => setSummary(null));
  }, []);

  const scoreLabel =
    summary?.latest_score != null ? `امتیاز: ${Math.round(summary.latest_score)}` : "ارزیابی عملکرد";

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
        gap: 0.8,
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
        {scoreLabel}
      </Typography>
    </Card>
  );
}
