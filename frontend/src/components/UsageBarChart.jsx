import { useState } from "react";
import { Box, Typography } from "@mui/material";
import { AXIS_WIDTH, PLOT_HEIGHT, edgeAwareTranslate, formatNumber, labelStepFor, niceMax } from "../utils/chartScale";

/**
 * نمودار میله‌ای عمودی برای مقادیر گسسته‌ی هر بازه (مثل «تعداد درخواست هر روز»)؛
 * برای این داده‌ها میله مناسب‌تر از خط است، چون خط بین دو روز مقدار میانی را القا می‌کند.
 *
 * props:
 *   data: [{ label, value }]
 *   color: رنگ میله‌ها
 *   partialLast: آخرین میله بازه‌ی جاری و ناتمام است (مثلاً امروز)؛ کم‌رنگ و خط‌چین و در Tooltip
 *     با برچسب «تا این لحظه» تا افت ظاهری‌اش با کاهش واقعی اشتباه نشود
 *   unit: پسوند عدد در Tooltip
 *   emptyMessage: پیام نمایش‌داده‌شده وقتی داده‌ای نیست
 *
 * نمودار با dir="ltr" رسم می‌شود و موقعیت‌های افقی (left/marginLeft/textAlign) عمداً در style خطی
 * آمده‌اند نه sx، چون stylis-plugin-rtl مقادیر left/right داخل sx را قرینه می‌کند.
 * میله‌ها و برچسب‌ها در دو ردیف Flex با تعداد ستون برابرند، پس هر برچسب دقیقاً زیر میله‌ی خودش است.
 * Tooltip با Hover و لمس (کلیک) نمایش داده می‌شود.
 */
export default function UsageBarChart({
  data,
  color = "#16324F",
  partialLast = false,
  unit = "",
  emptyMessage = "داده‌ای برای نمایش نیست",
}) {
  const [hoverIndex, setHoverIndex] = useState(null);  // ایندکس میله‌ی انتخاب‌شده برای Tooltip؛ null = هیچ
  const count = data?.length || 0;

  if (count === 0) {
    return (
      <Box sx={{ height: PLOT_HEIGHT + 24, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Typography variant="body2" color="text.secondary">
          {emptyMessage}
        </Typography>
      </Box>
    );
  }

  const maxValue = niceMax(Math.max(...data.map((d) => d.value), 0));  // سقف گرد‌شده‌ی محور عمودی
  const ticks = [0, maxValue / 2, maxValue];  // خطوط راهنمای افقی: صفر، نصف و سقف
  const yPx = (value) => PLOT_HEIGHT - (value / maxValue) * PLOT_HEIGHT;  // تبدیل مقدار به فاصله از بالای ناحیه‌ی رسم (px)
  const labelStep = labelStepFor(count, 10);  // هر چند برچسب یک برچسب نمایش داده شود (حداکثر حدود ۱۰ برچسب)
  const gap = count > 20 ? 2 : 6;  // فاصله‌ی بین میله‌ها؛ با تعداد زیاد کمتر
  const isPartial = (i) => partialLast && i === count - 1;  // آیا میله‌ی i همان بازه‌ی ناتمام آخر است

  return (
    <Box dir="ltr" onMouseLeave={() => setHoverIndex(null)}>
      {/* ناحیه‌ی رسم؛ به اندازه‌ی عرض محور از چپ فاصله دارد */}
      <Box sx={{ position: "relative", height: PLOT_HEIGHT }} style={{ marginLeft: AXIS_WIDTH }}>
        {/* برچسب‌های محور عمودی و خطوط راهنمای افقی (خط صفر توپر، بقیه خط‌چین) */}
        {ticks.map((t) => (
          <Box key={t}>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ position: "absolute", fontSize: 10, lineHeight: 1 }}
              style={{ left: -AXIS_WIDTH, width: AXIS_WIDTH - 6, top: yPx(t) - 5, textAlign: "right" }}
            >
              {formatNumber(t)}
            </Typography>
            <Box
              sx={{
                position: "absolute",
                height: 0,
                borderTop: t === 0 ? "1px solid" : "1px dashed",
                borderColor: "divider",
                opacity: t === 0 ? 1 : 0.6,
              }}
              style={{ left: 0, right: 0, top: yPx(t) }}
            />
          </Box>
        ))}

        {/* ردیف میله‌ها؛ هر ستون کل ارتفاع را می‌گیرد تا Hover روی کل ستون کار کند */}
        <Box
          dir="ltr"
          sx={{ position: "absolute", inset: 0, display: "flex", alignItems: "flex-end" }}
          style={{ gap }}
        >
          {data.map((d, i) => {
            const active = hoverIndex === i;
            return (
              <Box
                key={i}
                onMouseEnter={() => setHoverIndex(i)}
                onClick={() => setHoverIndex(i)}
                sx={{ flex: 1, height: "100%", display: "flex", alignItems: "flex-end", justifyContent: "center", cursor: "pointer" }}
              >
                <Box
                  sx={{
                    width: "100%",
                    maxWidth: 44,
                    minHeight: d.value > 0 ? 2 : 0,
                    borderRadius: "4px 4px 0 0",
                    bgcolor: color,
                    opacity: isPartial(i) ? 0.4 : active ? 1 : 0.82,
                    border: isPartial(i) ? "1px dashed" : "none",
                    borderColor: color,
                    transition: "opacity 0.1s",
                  }}
                  style={{ height: `${(d.value / maxValue) * 100}%` }}
                />
              </Box>
            );
          })}
        </Box>

        {/* Tooltip میله‌ی انتخاب‌شده؛ edgeAwareTranslate از بیرون‌زدن آن از لبه‌های نمودار جلوگیری می‌کند */}
        {hoverIndex !== null && (
          <Box
            dir="rtl"
            sx={{
              position: "absolute",
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
              left: `${((hoverIndex + 0.5) / count) * 100}%`,
              top: Math.max(yPx(data[hoverIndex].value) - 6, 0),
              transform: `${edgeAwareTranslate((hoverIndex + 0.5) / count)} translateY(-100%)`,
            }}
          >
            <Typography variant="caption" fontWeight={700} display="block">
              {data[hoverIndex].label}
              {isPartial(hoverIndex) ? " (تا این لحظه)" : ""}
            </Typography>
            <Typography variant="caption">
              {formatNumber(data[hoverIndex].value)}
              {unit}
            </Typography>
          </Box>
        )}
      </Box>

      {/* ردیف برچسب‌های محور افقی با همان ستون‌بندی میله‌ها؛ فقط هر labelStep برچسب و آخرین برچسب نمایش داده می‌شود */}
      <Box dir="ltr" sx={{ display: "flex", mt: 0.75 }} style={{ marginLeft: AXIS_WIDTH, gap }}>
        {data.map((d, i) => (
          <Typography
            key={i}
            variant="caption"
            color="text.secondary"
            sx={{ flex: 1, fontSize: 10, whiteSpace: "nowrap", overflow: "visible", minWidth: 0 }}
            style={{ textAlign: "center" }}
          >
            {i % labelStep === 0 || i === count - 1 ? d.label : ""}
          </Typography>
        ))}
      </Box>
    </Box>
  );
}
