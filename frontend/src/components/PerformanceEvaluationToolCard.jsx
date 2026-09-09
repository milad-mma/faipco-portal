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
 *
 * ⚠️ رفع یک باگ واقعی: این دو (Badge و برچسب «محرمانه») کاملاً مستقل از
 * هم بودند ولی چون کارت ارتفاع ثابت داشت، وقتی هر دو هم‌زمان لازم بود
 * نمایش داده شوند، برچسب «محرمانه» به‌خاطر کمبود جا Clip می‌شد (دیده
 * نمی‌شد) - نه اینکه واقعاً حذف شده باشد. حالا کارت minHeight دارد (نه
 * height ثابت) تا با محتوا رشد کند، و overflow: visible دارد تا اگر
 * Badge با عدد چندرقمی کمی از گوشه کارت بیرون بزند، به‌جای بریده‌شدن،
 * به‌طور طبیعی نمایش داده شود.
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
        minHeight: 82,
        overflow: "visible",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 0.6,
        py: 1,
        borderRadius: 2,
        cursor: "pointer",
        "&:hover": { backgroundColor: "action.hover" },
      }}
    >
      <Badge
        color="warning"
        badgeContent={summary?.pending_to_evaluate_count || 0}
        invisible={!summary?.pending_to_evaluate_count}
        sx={{ "& .MuiBadge-badge": { overflow: "visible" } }}
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
          <Chip
            label="محرمانه"
            size="small"
            sx={{ height: 18, fontSize: 10, backgroundColor: "#ffcdd2", color: "#c62828" }}
          />
        </Stack>
      )}
    </Card>
  );
}
