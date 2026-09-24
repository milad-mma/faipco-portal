/**
 * کامپوننت کاشی «ارزیابی عملکرد» در داشبورد پرسنل.
 * خلاصه‌ی داشبورد ارزیابی را از سرور می‌گیرد و وضعیت را روی کاشی نشان می‌دهد.
 */
import { useEffect, useState } from "react";
import { Badge, Box, Card, Chip, Stack, Typography } from "@mui/material";
import SpeedOutlinedIcon from "@mui/icons-material/SpeedOutlined";
import { fetchMyEvaluationDashboardSummary } from "../api/evaluationProcess";

/**
 * کاشی «ارزیابی عملکرد» در داشبورد پرسنل.
 * ورودی: onClick برای باز کردن صفحه‌ی ارزیابی.
 * امتیاز روی کارت نمایش داده نمی‌شود (محرمانه است)؛ اگر نتیجه‌ای وجود داشته باشد فقط برچسب «محرمانه» دیده می‌شود.
 * برای سرپرست/مدیر، Badge تعداد ارزیابی‌های در انتظار انجام را نشان می‌دهد.
 * کارت minHeight دارد تا با محتوا رشد کند و overflow: visible تا Badge بریده نشود.
 */
export default function PerformanceEvaluationToolCard({ onClick }) {
  const [summary, setSummary] = useState(null);  // خلاصه‌ی داشبورد ارزیابی؛ null = دریافت نشده یا خطا

  // در اولین رندر خلاصه‌ی داشبورد ارزیابی را می‌گیرد؛ در خطا null می‌گذارد
  useEffect(() => {
    fetchMyEvaluationDashboardSummary()
      .then(setSummary)
      .catch(() => setSummary(null));
  }, []);

  const hasResult = summary?.results_count > 0;  // آیا کاربر حداقل یک نتیجه‌ی ارزیابی دارد

  return (
    <Card
      variant="outlined"
      onClick={onClick}
      sx={{
        position: "relative",
        minHeight: { xs: 82, md: 110 },
        height: "100%",
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
      {/* آیکون کاشی با Badge تعداد ارزیابی‌های در انتظار انجام */}
      <Badge
        color="warning"
        badgeContent={summary?.pending_to_evaluate_count || 0}
        invisible={!summary?.pending_to_evaluate_count}
        sx={{ "& .MuiBadge-badge": { overflow: "visible" } }}
      >
        {/* فقط دسکتاپ: آیکون و متن بزرگ‌تر - هم‌اندازه بقیه کاشی‌های داشبورد */}
        <Box sx={{ color: "primary.main", display: "flex", "& svg": { fontSize: { xs: 24, md: 34 } } }}>
          <SpeedOutlinedIcon />
        </Box>
      </Badge>
      <Typography
        variant="caption"
        fontWeight={700}
        textAlign="center"
        sx={{ px: 0.5, fontSize: { xs: "0.75rem", md: "0.95rem" } }}
      >
        ارزیابی عملکرد
      </Typography>
      {/* برچسب «محرمانه» وقتی نتیجه‌ی ارزیابی وجود دارد */}
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
