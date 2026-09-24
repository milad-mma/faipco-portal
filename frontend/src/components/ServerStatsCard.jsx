/**
 * کارت مصرف منابع سرور (CPU، RAM، دیسک) در پنل مدیریت سیستم.
 * شامل توابع کمکی تجمیع ساعتی/روزانه، یافتن بیشینه و روند دیسک، کامپوننت داخلی MetricSummary و کامپوننت اصلی ServerStatsCard.
 */
import { useEffect, useMemo, useState } from "react";
import { Box, Card, CircularProgress, Grid, LinearProgress, Stack, Tab, Tabs, Typography } from "@mui/material";
import MemoryOutlinedIcon from "@mui/icons-material/MemoryOutlined";
import DnsOutlinedIcon from "@mui/icons-material/DnsOutlined";
import StorageOutlinedIcon from "@mui/icons-material/StorageOutlined";
import { fetchServerStats } from "../api/system";
import UsageLineChart from "./UsageLineChart";
import { gregorianToJalali, JALALI_MONTH_NAMES } from "../utils/jalaliDate";
import PillTabs from "./PillTabs";

// زمان ISO را به «روز ماه شمسی، ساعت hh:mm» تبدیل می‌کند
function formatDateTimeFa(isoString) {
  const d = new Date(isoString);
  const { jd, jm } = gregorianToJalali(d);
  const time = d.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
  return `${jd} ${JALALI_MONTH_NAMES[jm - 1]}، ساعت ${time}`;
}

// نمونه‌ها را در بازه‌ی hoursBack ساعت اخیر به دسته‌های ساعتی تقسیم و میانگین metricKey هر ساعت را برمی‌گرداند.
// خروجی: [{label (ساعت), value (میانگین با یک رقم اعشار)}] مرتب بر اساس زمان
function aggregateHourly(rawData, metricKey, hoursBack) {
  const cutoff = Date.now() - hoursBack * 60 * 60 * 1000;
  const buckets = new Map(); // key: "YYYY-MM-DDTHH", value: {sum, count, timestamp}
  rawData.forEach((row) => {
    const t = new Date(row.recorded_at).getTime();
    if (t < cutoff) return;
    const bucketKey = row.recorded_at.slice(0, 13); // تا سطح ساعت
    if (!buckets.has(bucketKey)) buckets.set(bucketKey, { sum: 0, count: 0, timestamp: t });
    const bucket = buckets.get(bucketKey);
    bucket.sum += row[metricKey];
    bucket.count += 1;
  });
  return Array.from(buckets.entries())
    .sort(([a], [b]) => (a > b ? 1 : -1))
    .map(([_, bucket]) => {
      const d = new Date(bucket.timestamp);
      const label = d.toLocaleTimeString("fa-IR", { hour: "2-digit" });
      return { label, value: Math.round((bucket.sum / bucket.count) * 10) / 10 };
    });
}

// نمونه‌ها را در بازه‌ی daysBack روز اخیر به دسته‌های روز شمسی تقسیم و میانگین metricKey هر روز را برمی‌گرداند.
// خروجی: [{label (روز ماه شمسی), value}] مرتب بر اساس کلید تاریخ
function aggregateDaily(rawData, metricKey, daysBack) {
  const cutoff = Date.now() - daysBack * 24 * 60 * 60 * 1000;
  const buckets = new Map();
  rawData.forEach((row) => {
    const t = new Date(row.recorded_at).getTime();
    if (t < cutoff) return;
    const { jy, jm, jd } = gregorianToJalali(new Date(row.recorded_at));
    const key = `${jy}-${jm}-${jd}`;
    if (!buckets.has(key)) buckets.set(key, { sum: 0, count: 0, jm, jd, sortKey: key });
    const bucket = buckets.get(key);
    bucket.sum += row[metricKey];
    bucket.count += 1;
  });
  return Array.from(buckets.values())
    .sort((a, b) => (a.sortKey > b.sortKey ? 1 : -1))
    .map((bucket) => ({
      label: `${bucket.jd} ${JALALI_MONTH_NAMES[bucket.jm - 1]}`,
      value: Math.round((bucket.sum / bucket.count) * 10) / 10,
    }));
}

// نمونه‌ای که بیشترین مقدار metricKey را دارد؛ برای آرایه‌ی خالی null
function findPeak(rawData, metricKey) {
  if (rawData.length === 0) return null;
  const peak = rawData.reduce((max, cur) => (cur[metricKey] > max[metricKey] ? cur : max), rawData[0]);
  return peak;
}

/**
 * روند مصرف دیسک از نمونه‌های ذخیره‌شده (حداکثر ۷ روز): میزان افزایش در این بازه و
 * تخمین زمان پر شدن با همان نرخ. خروجی: یک رشته‌ی توضیحی.
 * اگر بازه کمتر از یک روز باشد یا رشد کمتر از ۰٫۱ گیگابایت باشد، تخمینی داده نمی‌شود.
 */
function diskTrend(rawData) {
  const notEnough = "روند دیسک: برای محاسبه، حداقل یک روز داده لازم است";
  if (!rawData || rawData.length < 2) return notEnough;
  const first = rawData[0];
  const last = rawData[rawData.length - 1];
  const days = (new Date(last.recorded_at) - new Date(first.recorded_at)) / 86400000;
  if (days < 1) return notEnough;
  const growth = last.disk_used_gb - first.disk_used_gb;
  const spanLabel = `${Math.round(days).toLocaleString("fa-IR")} روز اخیر`;
  if (growth < 0.1) return `روند دیسک: بدون افزایش محسوس در ${spanLabel}`;
  const perDay = growth / days;
  const free = last.disk_total_gb - last.disk_used_gb;
  const daysLeft = free / perDay;
  const leftLabel =
    daysLeft > 730
      ? "بیش از ۲ سال"
      : daysLeft > 60
        ? `حدود ${Math.round(daysLeft / 30).toLocaleString("fa-IR")} ماه`
        : `حدود ${Math.round(daysLeft).toLocaleString("fa-IR")} روز`;
  return `روند دیسک: ${growth.toFixed(1)} گیگابایت افزایش در ${spanLabel} — با این روند ${leftLabel} تا پر شدن`;
}

/**
 * کارت خلاصه‌ی یک شاخص: عنوان و آیکون، مقدار فعلی، نوار درصد، بیشینه‌ی ۷ روز اخیر و پانویس اختیاری.
 * ورودی: icon، title، currentLabel، currentValue، currentPercent (برای نوار)، color، peakValue، peakLabel، footnote.
 */
function MetricSummary({
  icon,
  title,
  currentLabel,
  currentValue,
  currentPercent,
  color,
  peakValue,
  peakLabel,
  footnote,
}) {
  return (
    <Card variant="outlined" sx={{ p: 2.5, borderRadius: 3, height: "100%" }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
        {icon}
        <Typography variant="subtitle2" fontWeight={700}>
          {title}
        </Typography>
      </Stack>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        {currentValue}
      </Typography>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
        {currentLabel}
      </Typography>
      <LinearProgress
        variant="determinate"
        value={Math.min(currentPercent ?? 0, 100)}
        sx={{ height: 6, borderRadius: 3, mb: 1.5, backgroundColor: `${color}22`, "& .MuiLinearProgress-bar": { backgroundColor: color } }}
      />
      {peakValue && (
        <Typography variant="caption" color="text.secondary" display="block">
          بیشترین مصرف (۷ روز اخیر): <strong>{peakValue}</strong> — {peakLabel}
        </Typography>
      )}
      {footnote && (
        <Typography variant="caption" color="text.secondary" display="block">
          {footnote}
        </Typography>
      )}
    </Card>
  );
}

const TIME_TABS = [  // بازه‌های زمانی قابل انتخاب برای نمودار
  { key: "24h", label: "۲۴ ساعت اخیر" },
  { key: "7d", label: "۷ روز اخیر" },
];

/**
 * کارت اصلی مصرف منابع سرور؛ بدون ورودی (props).
 * نمونه‌های ذخیره‌شده را از سرور می‌گیرد و سه کارت خلاصه (CPU، RAM، دیسک) و نمودار خطی روند CPU/RAM
 * (ساعتی برای ۲۴ ساعت یا روزانه برای ۷ روز) نمایش می‌دهد.
 */
export default function ServerStatsCard() {
  const [rawData, setRawData] = useState(null);  // نمونه‌های مصرف منابع؛ null = در حال بارگذاری
  const [timeTab, setTimeTab] = useState("24h");  // بازه‌ی نمودار: 24h یا 7d

  // دریافت نمونه‌ها هنگام mount؛ در صورت خطا آرایه‌ی خالی
  useEffect(() => {
    fetchServerStats()
      .then(setRawData)
      .catch(() => setRawData([]));
  }, []);

  const latest = rawData && rawData.length > 0 ? rawData[rawData.length - 1] : null;  // آخرین نمونه = وضعیت همین لحظه

  // بیشینه‌ی مصرف هر شاخص در کل نمونه‌ها
  const peaks = useMemo(() => {
    if (!rawData || rawData.length === 0) return null;
    const cpuPeak = findPeak(rawData, "cpu_percent");
    const ramPeak = findPeak(rawData, "ram_percent");
    const diskPeak = findPeak(rawData, "disk_percent");
    return { cpu: cpuPeak, ram: ramPeak, disk: diskPeak };
  }, [rawData]);

  // داده‌ی نمودار یک شاخص بر اساس بازه‌ی انتخاب‌شده (تجمیع ساعتی یا روزانه)
  function chartFor(metricKey) {
    if (!rawData) return null;
    return timeTab === "24h" ? aggregateHourly(rawData, metricKey, 24) : aggregateDaily(rawData, metricKey, 7);
  }

  return (
    <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <DnsOutlinedIcon fontSize="small" color="action" />
        <Typography variant="subtitle1" fontWeight={700}>
          مصرف منابع سرور
        </Typography>
      </Stack>

      {/* بارگذاری / بدون داده / محتوای اصلی */}
      {rawData === null ? (
        <Stack alignItems="center" justifyContent="center" sx={{ height: 160 }}>
          <CircularProgress size={28} />
        </Stack>
      ) : rawData.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          هنوز داده‌ای ثبت نشده — تا ۱۰ دقیقه دیگر اولین نمونه ثبت می‌شود.
        </Typography>
      ) : (
        <>
          {/* سه کارت خلاصه: CPU، RAM و دیسک (دیسک به‌جای بیشینه، روند پر شدن را نشان می‌دهد) */}
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={12} sm={4}>
              <MetricSummary
                icon={<MemoryOutlinedIcon fontSize="small" color="action" />}
                title="پردازنده (CPU)"
                currentValue={`${latest.cpu_percent}٪`}
                currentLabel="مصرف همین لحظه"
                currentPercent={latest.cpu_percent}
                color="#3A6EA5"
                peakValue={peaks?.cpu ? `${peaks.cpu.cpu_percent}٪` : null}
                peakLabel={peaks?.cpu ? formatDateTimeFa(peaks.cpu.recorded_at) : ""}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <MetricSummary
                icon={<MemoryOutlinedIcon fontSize="small" color="action" />}
                title="حافظه (RAM)"
                currentValue={`${(latest.ram_used_mb / 1024).toFixed(1)} از ${(latest.ram_total_mb / 1024).toFixed(1)} گیگابایت`}
                currentLabel={`${latest.ram_percent}٪ استفاده‌شده`}
                currentPercent={latest.ram_percent}
                color="#2F855A"
                peakValue={peaks?.ram ? `${peaks.ram.ram_percent}٪` : null}
                peakLabel={peaks?.ram ? formatDateTimeFa(peaks.ram.recorded_at) : ""}
              />
            </Grid>
            <Grid item xs={12} sm={4}>
              <MetricSummary
                icon={<StorageOutlinedIcon fontSize="small" color="action" />}
                title="فضای دیسک"
                currentValue={`${latest.disk_used_gb.toFixed(0)} از ${latest.disk_total_gb.toFixed(0)} گیگابایت`}
                currentLabel={`${latest.disk_percent}٪ پر شده — ${(latest.disk_total_gb - latest.disk_used_gb).toFixed(0)} گیگابایت آزاد`}
                currentPercent={latest.disk_percent}
                color="#C97A2B"
                footnote={diskTrend(rawData)}
              />
            </Grid>
          </Grid>

          {/* انتخاب بازه‌ی زمانی نمودار */}
<PillTabs
            value={timeTab}
            onChange={setTimeTab}
            tabs={TIME_TABS.map((t) => ({ key: t.key, label: t.label }))}
            sx={{ mb: 2 }}
          />

          {/* نمودار مشترک CPU و RAM (هر دو درصد) با محور ثابت ۰ تا ۱۰۰٪ و خط هشدار ۸۰٪.
              دیسک نمودار ندارد؛ روند و تخمین پر شدنش در کارت خلاصه‌ی دیسک نمایش داده می‌شود. */}
          <Typography variant="caption" color="text.secondary" gutterBottom display="block">
            روند مصرف پردازنده و حافظه (میانگین {timeTab === "24h" ? "هر ساعت" : "هر روز"})
          </Typography>
          <UsageLineChart
            series={[
              { name: "پردازنده (CPU)", color: "#3A6EA5", data: chartFor("cpu_percent") || [] },
              { name: "حافظه (RAM)", color: "#2F855A", data: chartFor("ram_percent") || [] },
            ]}
            yMax={100}
            unit="٪"
            threshold={{ value: 80, label: "۸۰٪" }}
          />
        </>
      )}
    </Card>
  );
}
