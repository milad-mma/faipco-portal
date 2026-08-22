import { useId, useState } from "react";
import { Box, Typography } from "@mui/material";

const CHART_HEIGHT = 160;
const PADDING_TOP = 16;
const PADDING_BOTTOM = 28;
const PADDING_X = 8;

/**
 * نمودار خطی/ناحیه‌ای — برای داده‌های روند زمانی (مثل تعداد درخواست یا
 * درصد مصرف منابع در طول زمان) خواناتر از میله‌های جدا است، چون مسیر
 * تغییرات را پیوسته نشان می‌دهد. با SVG خالص (بدون کتابخانه خارجی)، با
 * یک نقطه قابل‌Hover روی هر مقدار برای دیدن عدد دقیق.
 */
export default function UsageLineChart({ data, color = "#16324F", emptyMessage = "داده‌ای برای نمایش نیست" }) {
  const gradientId = useId();
  const [hoverIndex, setHoverIndex] = useState(null);

  if (!data || data.length === 0) {
    return (
      <Box sx={{ height: CHART_HEIGHT, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Typography variant="body2" color="text.secondary">
          {emptyMessage}
        </Typography>
      </Box>
    );
  }

  const width = 600; // ViewBox منطقی — با viewBox و width:100% خودش Responsive می‌شود
  const plotWidth = width - PADDING_X * 2;
  const plotHeight = CHART_HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const maxValue = Math.max(...data.map((d) => d.value), 1);

  const points = data.map((item, i) => {
    const x = data.length === 1 ? PADDING_X + plotWidth / 2 : PADDING_X + (i / (data.length - 1)) * plotWidth;
    const y = PADDING_TOP + plotHeight - (item.value / maxValue) * plotHeight;
    return { x, y, ...item };
  });

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${PADDING_TOP + plotHeight} L ${points[0].x} ${PADDING_TOP + plotHeight} Z`;

  // فاصله‌گذاری هوشمند برچسب‌های محور افقی — اگر نقطه‌ها زیاد باشند (مثلاً
  // ۲۴ ساعت)، همه برچسب‌ها را نشان نده (شلوغ و ناخوانا می‌شود)
  const labelStep = Math.ceil(data.length / 8);

  return (
    <Box sx={{ position: "relative" }}>
      <svg viewBox={`0 0 ${width} ${CHART_HEIGHT}`} width="100%" height={CHART_HEIGHT} preserveAspectRatio="none" style={{ overflow: "visible" }}>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.35" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* خطوط راهنمای افقی */}
        {[0.25, 0.5, 0.75].map((fraction) => (
          <line
            key={fraction}
            x1={PADDING_X}
            x2={width - PADDING_X}
            y1={PADDING_TOP + plotHeight * fraction}
            y2={PADDING_TOP + plotHeight * fraction}
            stroke="currentColor"
            strokeOpacity={0.08}
            strokeDasharray="4 4"
          />
        ))}

        <path d={areaPath} fill={`url(#${gradientId})`} />
        <path d={linePath} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

        {points.map((p, i) => (
          <g key={i}>
            {/* یک ناحیه نامرئی بزرگ‌تر دور هر نقطه، برای راحت‌تر شدن Hover روی موبایل/دسکتاپ */}
            <circle
              cx={p.x}
              cy={p.y}
              r={10}
              fill="transparent"
              onMouseEnter={() => setHoverIndex(i)}
              onMouseLeave={() => setHoverIndex(null)}
              style={{ cursor: "pointer" }}
            />
            <circle cx={p.x} cy={p.y} r={hoverIndex === i ? 4.5 : 2.5} fill={color} style={{ transition: "r 0.1s", pointerEvents: "none" }} />
          </g>
        ))}
      </svg>

      {hoverIndex !== null && (
        <Box
          sx={{
            position: "absolute",
            left: `${(points[hoverIndex].x / width) * 100}%`,
            top: 0,
            transform: "translate(-50%, -100%)",
            backgroundColor: "background.paper",
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1,
            px: 1,
            py: 0.5,
            boxShadow: 2,
            pointerEvents: "none",
            whiteSpace: "nowrap",
          }}
        >
          <Typography variant="caption" fontWeight={700}>
            {points[hoverIndex].label}: {points[hoverIndex].value.toLocaleString("fa-IR")}
          </Typography>
        </Box>
      )}

      <Box sx={{ position: "relative", height: 16, mt: 0.5 }}>
        {points
          .filter((_, i) => i % labelStep === 0 || i === points.length - 1)
          .map((p, i) => (
            <Typography
              key={i}
              variant="caption"
              color="text.secondary"
              sx={{
                position: "absolute",
                left: `${(p.x / width) * 100}%`,
                transform: "translateX(-50%)",
                fontSize: 10,
                whiteSpace: "nowrap",
              }}
            >
              {p.label}
            </Typography>
          ))}
      </Box>
    </Box>
  );
}
