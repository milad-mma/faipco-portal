import { useEffect, useMemo, useState } from "react";
import { Box, Card, CircularProgress, Grid, LinearProgress, Stack, Tab, Tabs, Typography } from "@mui/material";
import MemoryOutlinedIcon from "@mui/icons-material/MemoryOutlined";
import DnsOutlinedIcon from "@mui/icons-material/DnsOutlined";
import StorageOutlinedIcon from "@mui/icons-material/StorageOutlined";
import { fetchServerStats } from "../api/system";
import UsageBarChart from "./UsageBarChart";
import { gregorianToJalali, JALALI_MONTH_NAMES } from "../utils/jalaliDate";

function formatDateTimeFa(isoString) {
  const d = new Date(isoString);
  const { jd, jm } = gregorianToJalali(d);
  const time = d.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
  return `${jd} ${JALALI_MONTH_NAMES[jm - 1]}، ساعت ${time}`;
}

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

function findPeak(rawData, metricKey) {
  if (rawData.length === 0) return null;
  const peak = rawData.reduce((max, cur) => (cur[metricKey] > max[metricKey] ? cur : max), rawData[0]);
  return peak;
}

function MetricSummary({ icon, title, currentLabel, currentValue, currentPercent, color, peakValue, peakLabel }) {
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
        <Typography variant="caption" color="text.secondary">
          بیشترین مصرف (۷ روز اخیر): <strong>{peakValue}</strong> — {peakLabel}
        </Typography>
      )}
    </Card>
  );
}

const TIME_TABS = [
  { key: "24h", label: "۲۴ ساعت اخیر" },
  { key: "7d", label: "۷ روز اخیر" },
];

export default function ServerStatsCard() {
  const [rawData, setRawData] = useState(null);
  const [timeTab, setTimeTab] = useState("24h");

  useEffect(() => {
    fetchServerStats()
      .then(setRawData)
      .catch(() => setRawData([]));
  }, []);

  const latest = rawData && rawData.length > 0 ? rawData[rawData.length - 1] : null;

  const peaks = useMemo(() => {
    if (!rawData || rawData.length === 0) return null;
    const cpuPeak = findPeak(rawData, "cpu_percent");
    const ramPeak = findPeak(rawData, "ram_percent");
    const diskPeak = findPeak(rawData, "disk_percent");
    return { cpu: cpuPeak, ram: ramPeak, disk: diskPeak };
  }, [rawData]);

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
                peakValue={peaks?.disk ? `${peaks.disk.disk_percent}٪` : null}
                peakLabel={peaks?.disk ? formatDateTimeFa(peaks.disk.recorded_at) : ""}
              />
            </Grid>
          </Grid>

          <Tabs
            value={timeTab}
            onChange={(_, value) => setTimeTab(value)}
            sx={{ mb: 1, minHeight: 36, "& .MuiTab-root": { minHeight: 36, py: 0.5 } }}
          >
            {TIME_TABS.map((tab) => (
              <Tab key={tab.key} value={tab.key} label={tab.label} />
            ))}
          </Tabs>

          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Typography variant="caption" color="text.secondary" gutterBottom display="block">
                روند CPU (٪)
              </Typography>
              <UsageBarChart data={chartFor("cpu_percent")} color="#3A6EA5" />
            </Grid>
            <Grid item xs={12} md={4}>
              <Typography variant="caption" color="text.secondary" gutterBottom display="block">
                روند RAM (٪)
              </Typography>
              <UsageBarChart data={chartFor("ram_percent")} color="#2F855A" />
            </Grid>
            <Grid item xs={12} md={4}>
              <Typography variant="caption" color="text.secondary" gutterBottom display="block">
                روند دیسک (٪)
              </Typography>
              <UsageBarChart data={chartFor("disk_percent")} color="#C97A2B" />
            </Grid>
          </Grid>
        </>
      )}
    </Card>
  );
}
