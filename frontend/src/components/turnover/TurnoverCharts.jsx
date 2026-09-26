/**
 * نمودارهای سبک SVG/HTML برای «گزارش جذب و ترک کار» (بدون کتابخانه‌ی خارجی).
 *
 * قواعد: یک محور عمودی در هر نمودار (هرگز دو محور)، رنگ دسته‌ای به ترتیب ثابت و اعتبارسنجی‌شده
 * برای کوررنگی، خطوط ۲px، میله‌ها با فاصله‌ی ۲px، راهنما برای ≥۲ سری و Tooltip روی هر ستون/نقطه.
 * نمودار با dir="ltr" رسم می‌شود تا محور زمان همیشه چپ‌به‌راست باشد؛ موقعیت‌های افقی در style خطی
 * نوشته شده‌اند چون stylis-plugin-rtl مقادیر left/right داخل sx را قرینه می‌کند.
 */
import { useEffect, useRef, useState } from "react";
import { Box, Stack, Typography, useTheme } from "@mui/material";

// رنگ‌های دسته‌ای به ترتیب ثابت (روشن / تیره) — هر گروه همیشه همان رنگ را دارد
const PALETTE = {
  light: {
    blue: "#2a78d6",
    orange: "#eb6834",
    aqua: "#1baf7a",
    yellow: "#eda100",
    magenta: "#e87ba4",
    green: "#008300",
    violet: "#4a3aa7",
    red: "#e34948",
    gray: "#8a8984",
    seq: ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
  },
  dark: {
    blue: "#3987e5",
    orange: "#d95926",
    aqua: "#199e70",
    yellow: "#c98500",
    magenta: "#d55181",
    green: "#008300",
    violet: "#9085e9",
    red: "#e66767",
    gray: "#7a7975",
    seq: ["#383835", "#104281", "#184f95", "#1c5cab", "#256abf", "#3987e5", "#86b6ef"],
  },
};
const CATEGORICAL_ORDER = ["blue", "orange", "aqua", "yellow", "magenta", "green", "violet", "red"];

/** رنگ‌های نمودار بر اساس حالت روشن/تیره‌ی تم */
export function useChartColors() {
  const theme = useTheme();
  const p = PALETTE[theme.palette.mode === "dark" ? "dark" : "light"];
  return {
    ...p,
    hires: p.aqua,
    separations: p.orange,
    groups: { voluntary: p.blue, involuntary: p.magenta, probation: p.violet, other: p.yellow, uncategorized: p.gray },
    categorical: CATEGORICAL_ORDER.map((k) => p[k]),
    grid: theme.palette.divider,
    text: theme.palette.text.secondary,
  };
}

const fa = (v, digits = 0) =>
  v === null || v === undefined ? "—" : Number(v).toLocaleString("fa-IR", { maximumFractionDigits: digits });

/** عرض واقعی ظرف برای رسم SVG با پیکسل واقعی (متن‌ها کش نمی‌آیند) */
function useWidth() {
  const ref = useRef(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    if (!ref.current) return undefined;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

/** سقف گرد محور: ۱، ۲، ۲.۵ یا ۵ ضربدر توان ۱۰ */
function niceMax(v) {
  if (!v || v <= 0) return 1;
  const e = Math.pow(10, Math.floor(Math.log10(v)));
  const f = v / e;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * e;
}

/** راهنمای سری‌ها (برای ≥۲ سری) */
export function Legend({ items }) {
  if (!items || items.length < 2) return null;
  return (
    <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
      {items.map((it) => (
        <Stack key={it.name} direction="row" spacing={0.75} alignItems="center">
          <Box
            sx={{
              width: it.line ? 16 : 10,
              height: it.line ? 0 : 10,
              borderRadius: it.line ? 0 : "3px",
              bgcolor: it.line ? "transparent" : it.color,
              borderTop: it.line ? `2px ${it.dashed ? "dashed" : "solid"} ${it.color}` : "none",
            }}
          />
          <Typography variant="caption" color="text.primary">
            {it.name}
          </Typography>
        </Stack>
      ))}
    </Stack>
  );
}

function Tooltip({ x, width, children }) {
  // Tooltip داخل کادر نمودار می‌ماند (نزدیک لبه‌ها به داخل جابه‌جا می‌شود)
  const w = 190;
  const left = Math.max(0, Math.min(x - w / 2, width - w));
  return (
    <Box
      sx={{
        position: "absolute",
        top: 0,
        zIndex: 2,
        pointerEvents: "none",
        bgcolor: "background.paper",
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1.5,
        boxShadow: 3,
        px: 1.25,
        py: 0.75,
      }}
      style={{ left, width: w }}
      dir="rtl"
    >
      {children}
    </Box>
  );
}

function TooltipRow({ color, label, value, line }) {
  return (
    <Stack direction="row" spacing={0.75} alignItems="center" justifyContent="space-between">
      <Stack direction="row" spacing={0.75} alignItems="center">
        {color && (
          <Box sx={{ width: 8, height: line ? 2 : 8, borderRadius: line ? 0 : "2px", bgcolor: color }} />
        )}
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
      </Stack>
      <Typography variant="caption" fontWeight={700} color="text.primary">
        {value}
      </Typography>
    </Stack>
  );
}

/** اسکلت مشترک نمودارهای ماهانه: محور، خطوط راهنما، برچسب‌ها و ناحیه‌ی Hover */
function useFrame(width, height, count, maxValue) {
  const pad = { left: 44, right: 10, top: 12, bottom: 26 };
  const plotW = Math.max(10, width - pad.left - pad.right);
  const plotH = height - pad.top - pad.bottom;
  const top = niceMax(maxValue);
  const y = (v) => pad.top + plotH - (v / top) * plotH;
  const band = plotW / Math.max(1, count);
  const xCenter = (i) => pad.left + band * i + band / 2;
  const ticks = [0, top / 2, top];
  const labelEvery = Math.max(1, Math.ceil(count / Math.max(2, Math.floor(plotW / 58))));
  return { pad, plotW, plotH, top, y, band, xCenter, ticks, labelEvery };
}

function Axes({ f, labels, colors, width, yFormat }) {
  return (
    <g>
      {f.ticks.map((t) => (
        <g key={t}>
          <line x1={f.pad.left} x2={width - f.pad.right} y1={f.y(t)} y2={f.y(t)} stroke={colors.grid} strokeDasharray={t ? "3 3" : undefined} />
          <text x={f.pad.left - 6} y={f.y(t) + 4} textAnchor="end" fontSize="10" fill={colors.text}>
            {yFormat ? yFormat(t) : fa(t, 1)}
          </text>
        </g>
      ))}
      {labels.map((l, i) =>
        i % f.labelEvery === 0 || i === labels.length - 1 ? (
          <text key={l + i} x={f.xCenter(i)} y={f.pad.top + f.plotH + 16} textAnchor="middle" fontSize="10" fill={colors.text}>
            {l}
          </text>
        ) : null
      )}
    </g>
  );
}

const shortMonth = (m) => (m ? `${m.slice(2, 4)}/${m.slice(5, 7)}` : m); // 1403/06 → 03/06

/**
 * میله‌ای گروهی ماهانه (مثل استخدام در برابر ترک کار).
 * props: labels ([«1403/06»...])، series: [{ name, color, values }]، height
 */
export function GroupedBarChart({ labels, series, height = 240, unit = "نفر" }) {
  const colors = useChartColors();
  const [ref, width] = useWidth();
  const [hover, setHover] = useState(null);
  const count = labels.length;
  const max = Math.max(1, ...series.flatMap((s) => s.values.map((v) => v || 0)));
  const f = useFrame(width, height, count, max);
  const groupW = Math.max(2, f.band * 0.72);
  const barW = Math.max(1, (groupW - 2 * (series.length - 1)) / series.length);
  return (
    <Box>
      <Legend items={series.map((s) => ({ name: s.name, color: s.color }))} />
      <Box ref={ref} dir="ltr" sx={{ position: "relative", width: "100%" }} onMouseLeave={() => setHover(null)}>
        {width > 0 && (
          <svg width={width} height={height} role="img">
            <Axes f={f} labels={labels.map(shortMonth)} colors={colors} width={width} yFormat={(t) => fa(t)} />
            {labels.map((l, i) => {
              const x0 = f.xCenter(i) - groupW / 2;
              return (
                <g key={l}>
                  {hover === i && <rect x={f.pad.left + f.band * i} y={f.pad.top} width={f.band} height={f.plotH} fill={colors.grid} opacity={0.35} />}
                  {series.map((s, si) => {
                    const v = s.values[i] || 0;
                    const h = f.y(0) - f.y(v);
                    return v ? (
                      <rect key={s.name} x={x0 + si * (barW + 2)} y={f.y(v)} width={barW} height={h} rx={Math.min(3, barW / 2)} fill={s.color} />
                    ) : null;
                  })}
                  <rect x={f.pad.left + f.band * i} y={f.pad.top} width={f.band} height={f.plotH} fill="transparent"
                    onMouseEnter={() => setHover(i)} onClick={() => setHover(i)} />
                </g>
              );
            })}
          </svg>
        )}
        {hover !== null && (
          <Tooltip x={f.xCenter(hover)} width={width}>
            <Typography variant="caption" fontWeight={700} display="block">{labels[hover]}</Typography>
            {series.map((s) => (
              <TooltipRow key={s.name} color={s.color} label={s.name} value={`${fa(s.values[hover])} ${unit}`} />
            ))}
          </Tooltip>
        )}
      </Box>
    </Box>
  );
}

/**
 * میله‌ای انباشته‌ی ماهانه (مثل ترک کار به تفکیک گروه) با فاصله‌ی ۲px بین قطعه‌ها.
 * props: labels، series: [{ name, color, values }]
 */
export function StackedBarChart({ labels, series, height = 240, unit = "نفر" }) {
  const colors = useChartColors();
  const [ref, width] = useWidth();
  const [hover, setHover] = useState(null);
  const totals = labels.map((_l, i) => series.reduce((a, s) => a + (s.values[i] || 0), 0));
  const f = useFrame(width, height, labels.length, Math.max(1, ...totals));
  const barW = Math.max(2, f.band * 0.62);
  const visible = series.filter((s) => s.values.some((v) => v));
  return (
    <Box>
      <Legend items={visible.map((s) => ({ name: s.name, color: s.color }))} />
      <Box ref={ref} dir="ltr" sx={{ position: "relative", width: "100%" }} onMouseLeave={() => setHover(null)}>
        {width > 0 && (
          <svg width={width} height={height} role="img">
            <Axes f={f} labels={labels.map(shortMonth)} colors={colors} width={width} yFormat={(t) => fa(t)} />
            {labels.map((l, i) => {
              let acc = 0;
              const x = f.xCenter(i) - barW / 2;
              return (
                <g key={l}>
                  {hover === i && <rect x={f.pad.left + f.band * i} y={f.pad.top} width={f.band} height={f.plotH} fill={colors.grid} opacity={0.35} />}
                  {series.map((s) => {
                    const v = s.values[i] || 0;
                    if (!v) return null;
                    const y1 = f.y(acc + v);
                    const y0 = f.y(acc);
                    acc += v;
                    return <rect key={s.name} x={x} y={y1} width={barW} height={Math.max(1, y0 - y1 - 2)} rx={2} fill={s.color} />;
                  })}
                  <rect x={f.pad.left + f.band * i} y={f.pad.top} width={f.band} height={f.plotH} fill="transparent"
                    onMouseEnter={() => setHover(i)} onClick={() => setHover(i)} />
                </g>
              );
            })}
          </svg>
        )}
        {hover !== null && (
          <Tooltip x={f.xCenter(hover)} width={width}>
            <Typography variant="caption" fontWeight={700} display="block">
              {labels[hover]} — مجموع {fa(totals[hover])} {unit}
            </Typography>
            {visible.map((s) => (
              <TooltipRow key={s.name} color={s.color} label={s.name} value={fa(s.values[hover])} />
            ))}
          </Tooltip>
        )}
      </Box>
    </Box>
  );
}

/**
 * نمودار خطی (یک محور). props: labels، series: [{ name, color, values (null = بدون داده), dashed }]،
 * yFormat، yMax (اختیاری، مثلاً ۱۰۰ برای درصد)، xFormat برای برچسب محور افقی.
 */
export function LineChart({ labels, series, height = 240, yFormat = (v) => fa(v, 1), yMax, xFormat = shortMonth, valueFormat }) {
  const colors = useChartColors();
  const [ref, width] = useWidth();
  const [hover, setHover] = useState(null);
  const max = yMax ?? Math.max(1, ...series.flatMap((s) => s.values.filter((v) => v !== null && v !== undefined)));
  const f = useFrame(width, height, labels.length, max);
  const fmt = valueFormat || yFormat;
  return (
    <Box>
      <Legend items={series.map((s) => ({ name: s.name, color: s.color, line: true, dashed: s.dashed }))} />
      <Box ref={ref} dir="ltr" sx={{ position: "relative", width: "100%" }} onMouseLeave={() => setHover(null)}>
        {width > 0 && (
          <svg width={width} height={height} role="img">
            <Axes f={f} labels={labels.map(xFormat)} colors={colors} width={width} yFormat={yFormat} />
            {hover !== null && (
              <line x1={f.xCenter(hover)} x2={f.xCenter(hover)} y1={f.pad.top} y2={f.pad.top + f.plotH} stroke={colors.text} strokeOpacity={0.4} />
            )}
            {series.map((s) => {
              // خط در نقاط بدون داده قطع می‌شود (مسیرهای جدا)
              const segments = [];
              let cur = [];
              s.values.forEach((v, i) => {
                if (v === null || v === undefined) {
                  if (cur.length) segments.push(cur);
                  cur = [];
                } else cur.push([f.xCenter(i), f.y(v)]);
              });
              if (cur.length) segments.push(cur);
              return (
                <g key={s.name}>
                  {segments.map((seg, si) =>
                    seg.length > 1 ? (
                      <polyline key={si} points={seg.map((p) => p.join(",")).join(" ")} fill="none" stroke={s.color} strokeWidth={2}
                        strokeDasharray={s.dashed ? "5 4" : undefined} strokeLinejoin="round" strokeLinecap="round" />
                    ) : (
                      <circle key={si} cx={seg[0][0]} cy={seg[0][1]} r={3} fill={s.color} />
                    )
                  )}
                  {hover !== null && s.values[hover] !== null && s.values[hover] !== undefined && (
                    <circle cx={f.xCenter(hover)} cy={f.y(s.values[hover])} r={4.5} fill={s.color} stroke="#fff" strokeWidth={2} />
                  )}
                </g>
              );
            })}
            {labels.map((l, i) => (
              <rect key={l + i} x={f.pad.left + f.band * i} y={f.pad.top} width={f.band} height={f.plotH} fill="transparent"
                onMouseEnter={() => setHover(i)} onClick={() => setHover(i)} />
            ))}
          </svg>
        )}
        {hover !== null && (
          <Tooltip x={f.xCenter(hover)} width={width}>
            <Typography variant="caption" fontWeight={700} display="block">{labels[hover]}</Typography>
            {series.map((s) => (
              <TooltipRow key={s.name} color={s.color} line label={s.name} value={fmt(s.values[hover])} />
            ))}
          </Tooltip>
        )}
      </Box>
    </Box>
  );
}

/**
 * میله‌ی افقی (HTML) برای مقایسه‌ی دسته‌ها. items: [{ key, label, value, note?, color? }]
 * مقدار کنار هر میله نوشته می‌شود (رنگ تنها حامل معنا نیست).
 */
export function HBarChart({ items, color, valueFormat = (v) => fa(v), maxItems }) {
  const colors = useChartColors();
  const list = maxItems ? items.slice(0, maxItems) : items;
  const max = Math.max(1, ...list.map((i) => i.value || 0));
  if (!list.length) return <Typography variant="body2" color="text.secondary">داده‌ای نیست</Typography>;
  return (
    <Stack spacing={1}>
      {list.map((it) => (
        <Box key={it.key ?? it.label}>
          <Stack direction="row" justifyContent="space-between" alignItems="baseline" spacing={1}>
            <Typography variant="body2" noWrap title={it.label} sx={{ minWidth: 0 }}>
              {it.label}
            </Typography>
            <Typography variant="body2" fontWeight={700} sx={{ flexShrink: 0 }}>
              {valueFormat(it.value)}
              {it.note ? (
                <Typography component="span" variant="caption" color="text.secondary" sx={{ mx: 0.5 }}>
                  {it.note}
                </Typography>
              ) : null}
            </Typography>
          </Stack>
          <Box sx={{ height: 8, borderRadius: 4, bgcolor: "action.hover", overflow: "hidden", mt: 0.5 }}>
            <Box sx={{ height: "100%", borderRadius: 4, bgcolor: it.color || color || colors.blue, width: `${((it.value || 0) / max) * 100}%` }} />
          </Box>
        </Box>
      ))}
    </Stack>
  );
}

/**
 * نقشه‌ی حرارتی واحد × ماه (تعداد ترک کار). رنگ ترتیبی تک‌رنگ (آبی کم‌رنگ → پررنگ)؛ عدد داخل خانه
 * نوشته می‌شود و با Hover عنوان کامل نمایش داده می‌شود.
 */
export function Heatmap({ columns, rows }) {
  const colors = useChartColors();
  const max = Math.max(1, ...rows.flatMap((r) => r.values));
  if (!rows.length) return <Typography variant="body2" color="text.secondary">داده‌ای نیست</Typography>;
  const shade = (v) => (v ? colors.seq[Math.min(colors.seq.length - 1, 1 + Math.floor((v / max) * (colors.seq.length - 2)))] : "transparent");
  const darkText = (v) => v && v / max > 0.45;
  return (
    <Box sx={{ overflowX: "auto" }}>
      <Box
        component="table"
        sx={{ borderCollapse: "separate", borderSpacing: "2px", fontSize: 11, minWidth: "100%" }}
      >
        <thead>
          <tr>
            <Box component="th" sx={{ position: "sticky", bgcolor: "background.paper", textAlign: "start", pl: 1, fontWeight: 600, minWidth: 110 }} style={{ right: 0 }}>
              واحد
            </Box>
            {columns.map((c) => (
              <Box component="th" key={c} sx={{ fontWeight: 400, color: "text.secondary", px: 0.25, whiteSpace: "nowrap" }} dir="ltr">
                {shortMonth(c)}
              </Box>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.code ?? r.name}>
              <Box component="td" sx={{ position: "sticky", bgcolor: "background.paper", whiteSpace: "nowrap", pl: 1 }} style={{ right: 0 }}>
                {r.name}
              </Box>
              {r.values.map((v, i) => (
                <Box
                  component="td"
                  key={i}
                  title={`${r.name} — ${columns[i]}: ${fa(v)} ترک کار`}
                  sx={{
                    textAlign: "center",
                    minWidth: 26,
                    height: 24,
                    borderRadius: "4px",
                    bgcolor: shade(v),
                    color: darkText(v) ? "#fff" : "text.primary",
                    border: v ? "none" : "1px solid",
                    borderColor: "divider",
                  }}
                >
                  {v ? fa(v) : ""}
                </Box>
              ))}
            </tr>
          ))}
        </tbody>
      </Box>
    </Box>
  );
}
