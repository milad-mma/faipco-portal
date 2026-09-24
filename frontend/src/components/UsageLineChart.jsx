import { useState } from "react";
import { Box, Stack, Typography } from "@mui/material";
import {
  AXIS_WIDTH,
  PLOT_HEIGHT,
  edgeAwareTranslate,
  formatNumber,
  labelStepFor,
  niceMax,
} from "../utils/chartScale";

const VIEW_WIDTH = 1000; // عرض منطقی SVG؛ با preserveAspectRatio="none" کش می‌آید

/**
 * نمودار خطی روند زمانی با SVG خالص، بدون کتابخانه‌ی خارجی.
 *
 * props:
 *   data + color: یک سری تکی
 *   series: [{ name, color, data: [{label, value}] }]؛ چند سری با برچسب‌های یکسان
 *     (مثلاً CPU و RAM)؛ راهنمای رنگ خودکار نمایش داده می‌شود
 *   yMax: سقف ثابت محور عمودی (مثلاً ۱۰۰ برای درصد)؛ بدون آن، سقف گرد‌شده‌ی بیشترین مقدار است
 *   unit: پسوند اعداد (مثلاً «٪»)
 *   threshold: { value, label }؛ خط‌چین قرمز هشدار
 *   emptyMessage: پیام نمایش‌داده‌شده وقتی داده‌ای نیست
 *
 * خطوط با vectorEffect="non-scaling-stroke" کشیده می‌شوند و نقطه‌ها به‌صورت المان HTML روی SVG قرار
 * می‌گیرند تا با کش‌آمدن عرض، بیضی نشوند. نمودار با dir="ltr" رسم می‌شود و موقعیت‌های افقی
 * (left/right/marginLeft/textAlign) عمداً در style خطی آمده‌اند نه sx، چون stylis-plugin-rtl مقادیر sx را قرینه می‌کند.
 * Tooltip با Hover (دسکتاپ) و لمس (موبایل) روی ستون هر نقطه باز می‌شود.
 */
export default function UsageLineChart({
  data,
  color = "#16324F",
  series,
  yMax,
  unit = "",
  threshold,
  emptyMessage = "داده‌ای برای نمایش نیست",
}) {
  const [hoverIndex, setHoverIndex] = useState(null);  // ایندکس نقطه‌ی انتخاب‌شده برای Tooltip؛ null = هیچ
  const allSeries = series || [{ name: null, color, data: data || [] }];  // حالت تک‌سری به قالب series تبدیل می‌شود
  const labels = allSeries[0]?.data?.map((d) => d.label) || [];  // برچسب‌های محور افقی از سری اول
  const count = labels.length;

  if (count === 0) {
    return (
      <Box sx={{ height: PLOT_HEIGHT + 24, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Typography variant="body2" color="text.secondary">
          {emptyMessage}
        </Typography>
      </Box>
    );
  }

  const dataMax = Math.max(...allSeries.flatMap((s) => s.data.map((d) => d.value)), 0);
  const maxValue = yMax ?? niceMax(dataMax);  // سقف محور: yMax ثابت یا بیشترین مقدار گرد‌شده
  const ticks = [0, maxValue / 2, maxValue];  // خطوط راهنمای افقی: صفر، نصف و سقف
  const fractionX = (i) => (count === 1 ? 0.5 : i / (count - 1));  // موقعیت افقی نقطه‌ی i به‌صورت کسری از عرض (تک‌نقطه در وسط)
  const yPx = (value) => PLOT_HEIGHT - (Math.min(value, maxValue) / maxValue) * PLOT_HEIGHT;  // تبدیل مقدار به فاصله از بالای ناحیه‌ی رسم (px)؛ مقادیر بیش از سقف بریده می‌شوند
  const step = count === 1 ? 1 : 1 / (count - 1);  // فاصله‌ی کسری بین دو نقطه (عرض ناحیه‌ی Hover هر نقطه)
  const labelStep = labelStepFor(count);  // هر چند برچسب یک برچسب روی محور افقی نمایش داده شود
  const single = allSeries.length === 1;  // در حالت تک‌سری ناحیه‌ی زیر خط گرادیان می‌گیرد و راهنمای رنگ نمایش داده نمی‌شود

  return (
    <Box dir="ltr" onMouseLeave={() => setHoverIndex(null)}>
      {/* راهنمای رنگ سری‌ها (فقط چندسری)، راست‌به‌چپ */}
      {!single && (
        <Stack direction="row" spacing={2} justifyContent="center" sx={{ mb: 1 }} dir="rtl">
          {allSeries.map((s) => (
            <Stack key={s.name} direction="row" spacing={0.75} alignItems="center">
              <Box sx={{ width: 12, height: 3, borderRadius: 2, bgcolor: s.color }} />
              <Typography variant="caption" color="text.secondary">
                {s.name}
              </Typography>
            </Stack>
          ))}
        </Stack>
      )}

      {/* ناحیه‌ی رسم؛ به اندازه‌ی عرض محور از چپ فاصله دارد */}
      <Box sx={{ position: "relative", height: PLOT_HEIGHT }} style={{ marginLeft: AXIS_WIDTH }}>
        {/* اعداد محور عمودی */}
        {ticks.map((t) => (
          <Typography
            key={t}
            variant="caption"
            color="text.secondary"
            sx={{ position: "absolute", fontSize: 10, lineHeight: 1 }}
            style={{ left: -AXIS_WIDTH, width: AXIS_WIDTH - 6, top: yPx(t) - 5, textAlign: "right" }}
          >
            {formatNumber(t)}
            {unit}
          </Typography>
        ))}

        <svg
          viewBox={`0 0 ${VIEW_WIDTH} ${PLOT_HEIGHT}`}
          width="100%"
          height={PLOT_HEIGHT}
          preserveAspectRatio="none"
          style={{ position: "absolute", inset: 0, overflow: "visible" }}
        >
          {/* تعریف گرادیان زیر خط برای حالت تک‌سری */}
          {single && (
            <defs>
              <linearGradient id={`grad-${allSeries[0].color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={allSeries[0].color} stopOpacity="0.3" />
                <stop offset="100%" stopColor={allSeries[0].color} stopOpacity="0.02" />
              </linearGradient>
            </defs>
          )}
          {/* خطوط راهنمای افقی (خط صفر پررنگ‌تر، بقیه خط‌چین) */}
          {ticks.map((t) => (
            <line
              key={t}
              x1={0}
              x2={VIEW_WIDTH}
              y1={yPx(t)}
              y2={yPx(t)}
              stroke="currentColor"
              strokeOpacity={t === 0 ? 0.2 : 0.08}
              strokeDasharray={t === 0 ? undefined : "4 4"}
              vectorEffect="non-scaling-stroke"
            />
          ))}
          {/* خط‌چین هشدار (اگر در بازه‌ی محور باشد) */}
          {threshold && threshold.value <= maxValue && (
            <line
              x1={0}
              x2={VIEW_WIDTH}
              y1={yPx(threshold.value)}
              y2={yPx(threshold.value)}
              stroke="#D32F2F"
              strokeOpacity={0.55}
              strokeDasharray="6 4"
              vectorEffect="non-scaling-stroke"
            />
          )}
          {/* مسیر هر سری؛ در حالت تک‌سری ناحیه‌ی زیر خط هم با گرادیان پر می‌شود */}
          {allSeries.map((s) => {
            const pts = s.data.map((d, i) => `${fractionX(i) * VIEW_WIDTH} ${yPx(d.value)}`);
            const line = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p}`).join(" ");
            return (
              <g key={s.name || "single"}>
                {single && count > 1 && (
                  <path
                    d={`${line} L ${VIEW_WIDTH} ${PLOT_HEIGHT} L 0 ${PLOT_HEIGHT} Z`}
                    fill={`url(#grad-${s.color.replace("#", "")})`}
                  />
                )}
                <path
                  d={line}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                />
              </g>
            );
          })}
        </svg>

        {/* برچسب خط هشدار در سمت راست ناحیه‌ی رسم */}
        {threshold && threshold.value <= maxValue && threshold.label && (
          <Typography
            variant="caption"
            sx={{ position: "absolute", fontSize: 9, color: "#D32F2F", opacity: 0.8 }}
            style={{ right: 2, top: yPx(threshold.value) - 13 }}
          >
            {threshold.label}
          </Typography>
        )}

        {/* خط راهنمای عمودی نقطه انتخاب‌شده */}
        {hoverIndex !== null && (
          <Box
            sx={{ position: "absolute", top: 0, bottom: 0, width: "1px", bgcolor: "divider", pointerEvents: "none" }}
            style={{ left: `${fractionX(hoverIndex) * 100}%` }}
          />
        )}

        {/* نقطه‌ها به‌صورت HTML تا با کش‌آمدن SVG بیضی نشوند؛ با بیش از ۳۰ نقطه فقط نقطه‌ی انتخاب‌شده دیده می‌شود */}
        {allSeries.map((s) =>
          s.data.map((d, i) => {
            const active = hoverIndex === i;
            return (
              <Box
                key={`${s.name}-${i}`}
                sx={{
                  position: "absolute",
                  width: active ? 9 : count > 30 ? 0 : 6,
                  height: active ? 9 : count > 30 ? 0 : 6,
                  borderRadius: "50%",
                  bgcolor: s.color,
                  border: active ? "2px solid" : "none",
                  borderColor: "background.paper",
                  pointerEvents: "none",
                  boxSizing: "content-box",
                }}
                style={{ left: `${fractionX(i) * 100}%`, top: yPx(d.value), transform: "translate(-50%, -50%)" }}
              />
            );
          })
        )}

        {/* ناحیه‌های Hover/لمس: یک ستون تمام‌ارتفاع به‌ازای هر نقطه */}
        {labels.map((_, i) => (
          <Box
            key={`hit-${i}`}
            onMouseEnter={() => setHoverIndex(i)}
            onClick={() => setHoverIndex(i)}
            sx={{ position: "absolute", top: 0, bottom: 0, cursor: "pointer" }}
            style={{
              left: `${Math.max(0, (fractionX(i) - step / 2) * 100)}%`,
              width: `${Math.min(step, 1) * 100}%`,
            }}
          />
        ))}

        {/* Tooltip نقطه‌ی انتخاب‌شده با مقدار همه‌ی سری‌ها؛ edgeAwareTranslate از بیرون‌زدن آن از لبه‌ها جلوگیری می‌کند */}
        {hoverIndex !== null && (
          <Box
            dir="rtl"
            sx={{
              position: "absolute",
              top: -8,
              backgroundColor: "background.paper",
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 1,
              px: 1,
              py: 0.5,
              boxShadow: 2,
              pointerEvents: "none",
              whiteSpace: "nowrap",
              zIndex: 2,
            }}
            style={{
              left: `${fractionX(hoverIndex) * 100}%`,
              transform: `${edgeAwareTranslate(fractionX(hoverIndex))} translateY(-100%)`,
            }}
          >
            <Typography variant="caption" fontWeight={700} display="block">
              {labels[hoverIndex]}
            </Typography>
            {allSeries.map((s) => (
              <Stack key={s.name || "single"} direction="row" spacing={0.75} alignItems="center">
                <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: s.color }} />
                <Typography variant="caption">
                  {s.name ? `${s.name}: ` : ""}
                  {formatNumber(s.data[hoverIndex]?.value ?? 0)}
                  {unit}
                </Typography>
              </Stack>
            ))}
          </Box>
        )}
      </Box>

      {/* برچسب‌های محور افقی دقیقاً زیر نقطه‌ی متناظر؛ فقط هر labelStep برچسب و آخرین برچسب */}
      <Box sx={{ position: "relative", height: 18, mt: 0.75 }} style={{ marginLeft: AXIS_WIDTH }}>
        {labels.map((label, i) =>
          i % labelStep === 0 || i === count - 1 ? (
            <Typography
              key={i}
              variant="caption"
              color="text.secondary"
              sx={{ position: "absolute", fontSize: 10, whiteSpace: "nowrap" }}
              style={{ left: `${fractionX(i) * 100}%`, transform: edgeAwareTranslate(fractionX(i)) }}
            >
              {label}
            </Typography>
          ) : null
        )}
      </Box>
    </Box>
  );
}
