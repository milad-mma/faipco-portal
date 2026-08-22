import { Box, Stack, Tooltip, Typography } from "@mui/material";

const CHART_HEIGHT = 160;

/**
 * نمودار میله‌ای ساده — عمداً بدون هیچ کتابخانه نمودار خارجی (این پروژه
 * از قبل هیچ‌کدام را نصب ندارد؛ برای همین چند میله ساده، اضافه‌کردن یک
 * وابستگی npm جدید فقط برای این کار توجیه نداشت). هر میله با Tooltip
 * روی Hover مقدار دقیق را نشان می‌دهد.
 */
export default function UsageBarChart({ data, color = "#16324F", emptyMessage = "داده‌ای برای نمایش نیست" }) {
  if (!data || data.length === 0) {
    return (
      <Box sx={{ height: CHART_HEIGHT, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Typography variant="body2" color="text.secondary">
          {emptyMessage}
        </Typography>
      </Box>
    );
  }

  const maxValue = Math.max(...data.map((d) => d.value), 1);

  return (
    <Stack direction="row" spacing={data.length > 20 ? 0.5 : 1.5} alignItems="flex-end" sx={{ height: CHART_HEIGHT, overflowX: "auto", pb: 0.5 }}>
      {data.map((item) => (
        <Stack key={item.label} alignItems="center" spacing={0.5} sx={{ minWidth: data.length > 20 ? 10 : 32, flex: 1 }}>
          <Tooltip title={`${item.label}: ${item.value.toLocaleString("fa-IR")}`} arrow>
            <Box
              sx={{
                width: "100%",
                maxWidth: 28,
                height: Math.max((item.value / maxValue) * (CHART_HEIGHT - 28), 3),
                backgroundColor: color,
                borderRadius: "4px 4px 0 0",
                opacity: item.value === 0 ? 0.15 : 0.85,
                transition: "opacity 0.15s",
                "&:hover": { opacity: 1 },
              }}
            />
          </Tooltip>
          {data.length <= 20 && (
            <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10, whiteSpace: "nowrap" }}>
              {item.label}
            </Typography>
          )}
        </Stack>
      ))}
    </Stack>
  );
}
