import { useEffect, useMemo, useState } from "react";
import { Card, CircularProgress, Stack, Tab, Tabs, Typography } from "@mui/material";
import BarChartOutlinedIcon from "@mui/icons-material/BarChartOutlined";
import { fetchUsageStats } from "../api/system";
import UsageLineChart from "./UsageLineChart";
import { gregorianToJalali, JALALI_MONTH_NAMES } from "../utils/jalaliDate";

function toJalaliDayLabel(isoDate) {
  const [y, m, d] = isoDate.split("-").map(Number);
  const { jm, jd } = gregorianToJalali(new Date(y, m - 1, d));
  return `${jd} ${JALALI_MONTH_NAMES[jm - 1]}`;
}

// شماره هفته شمسی تقریبی (برای گروه‌بندی، نه یک استاندارد رسمی) — بر
// اساس تعداد روزهای سپری‌شده از ابتدای سال شمسی، تقسیم بر ۷. فرمول عمداً
// دقیقاً با فرمول jdays در jalaliDate.js هماهنگ نگه داشته شده (jd - 1، نه
// jd) — قبلاً این‌جا یک نسخه جدا و کمی متفاوت نوشته شده بود که می‌توانست
// نتیجه‌اش با بقیه محاسبات این پروژه یک روز فرق کند.
function toJalaliWeekKey(isoDate) {
  const [y, m, d] = isoDate.split("-").map(Number);
  const { jy, jm, jd } = gregorianToJalali(new Date(y, m - 1, d));
  const dayOfYear = jm <= 6 ? (jm - 1) * 31 + (jd - 1) : 186 + (jm - 7) * 30 + (jd - 1);
  const weekNumber = Math.ceil((dayOfYear + 1) / 7);
  return { key: `${jy}-W${weekNumber}`, label: `هفته ${weekNumber} (${jy})` };
}

/** روزهای هفته میلادی (چون داده خام میلادی است) را به هفته شمسی تبدیل و گروه‌بندی می‌کند */
function aggregateByWeek(rawData) {
  const map = new Map();
  rawData.forEach(({ date, request_count }) => {
    const { key, label } = toJalaliWeekKey(date);
    map.set(key, { label, value: (map.get(key)?.value || 0) + request_count, sortKey: key });
  });
  return Array.from(map.values())
    .sort((a, b) => (a.sortKey > b.sortKey ? 1 : -1))
    .slice(-12);
}

function aggregateByDay(rawData) {
  const map = new Map();
  rawData.forEach(({ date, request_count }) => {
    map.set(date, (map.get(date) || 0) + request_count);
  });
  return Array.from(map.entries())
    .sort(([a], [b]) => (a > b ? 1 : -1))
    .slice(-14)
    .map(([date, value]) => ({ label: toJalaliDayLabel(date), value }));
}

function aggregateByMonth(rawData) {
  const map = new Map();
  rawData.forEach(({ date, request_count }) => {
    const [y, m, d] = date.split("-").map(Number);
    const { jy, jm } = gregorianToJalali(new Date(y, m - 1, d));
    // عمداً بر اساس ماه شمسی واقعی گروه‌بندی می‌شود، نه فقط برش رشته تاریخ
    // میلادی — چون ماه‌های شمسی با مرزهای ماه میلادی هم‌راستا نیستند (مثلاً
    // «مرداد» هم به انتهای جولای هم به بخشی از آگوست میلادی می‌افتد)؛ گروه‌بندی
    // بر اساس رشته میلادی باعث می‌شد یک ماه شمسی به دو ستون جدا با برچسب
    // یکسان تقسیم شود.
    const monthKey = `${jy}-${String(jm).padStart(2, "0")}`;
    if (!map.has(monthKey)) {
      map.set(monthKey, { label: `${JALALI_MONTH_NAMES[jm - 1]} ${jy}`, value: 0, sortKey: monthKey });
    }
    map.get(monthKey).value += request_count;
  });
  return Array.from(map.values()).sort((a, b) => (a.sortKey > b.sortKey ? 1 : -1));
}

function aggregateByHour(rawData) {
  const buckets = Array.from({ length: 24 }, () => 0);
  rawData.forEach(({ hour, request_count }) => {
    buckets[hour] += request_count;
  });
  return buckets.map((value, hour) => ({ label: `${String(hour).padStart(2, "0")}`, value }));
}

const TABS = [
  { key: "daily", label: "روزانه" },
  { key: "weekly", label: "هفتگی" },
  { key: "monthly", label: "ماهانه" },
  { key: "hourly", label: "بر اساس ساعت روز" },
];

export default function UsageStatsCard() {
  const [rawData, setRawData] = useState(null);
  const [activeTab, setActiveTab] = useState("daily");

  useEffect(() => {
    fetchUsageStats()
      .then(setRawData)
      .catch(() => setRawData([]));
  }, []);

  const chartData = useMemo(() => {
    if (!rawData) return null;
    switch (activeTab) {
      case "daily":
        return aggregateByDay(rawData);
      case "weekly":
        return aggregateByWeek(rawData);
      case "monthly":
        return aggregateByMonth(rawData);
      case "hourly":
        return aggregateByHour(rawData);
      default:
        return [];
    }
  }, [rawData, activeTab]);

  const busiestHour = useMemo(() => {
    if (!rawData || rawData.length === 0) return null;
    const buckets = aggregateByHour(rawData);
    const busiest = buckets.reduce((max, cur) => (cur.value > max.value ? cur : max), buckets[0]);
    return busiest.value > 0 ? busiest : null;
  }, [rawData]);

  return (
    <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
        <BarChartOutlinedIcon fontSize="small" color="action" />
        <Typography variant="subtitle1" fontWeight={700}>
          میزان استفاده از پرتال
        </Typography>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        تعداد درخواست‌های واقعی کاربران وارد‌شده به پرتال — نه بازدید صفحه، تعداد تعامل واقعی با سرور.
        {busiestHour && (
          <>
            {" "}
            پرترافیک‌ترین ساعت شبانه‌روز معمولاً <strong>{busiestHour.label}:۰۰</strong> است.
          </>
        )}
      </Typography>

      <Tabs
        value={activeTab}
        onChange={(_, value) => setActiveTab(value)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ mb: 2, minHeight: 36, "& .MuiTab-root": { minHeight: 36, py: 0.5 } }}
      >
        {TABS.map((tab) => (
          <Tab key={tab.key} value={tab.key} label={tab.label} />
        ))}
      </Tabs>

      {rawData === null ? (
        <Stack alignItems="center" justifyContent="center" sx={{ height: 160 }}>
          <CircularProgress size={28} />
        </Stack>
      ) : (
        <UsageLineChart data={chartData} emptyMessage="هنوز داده‌ای برای این بازه ثبت نشده" />
      )}
    </Card>
  );
}
