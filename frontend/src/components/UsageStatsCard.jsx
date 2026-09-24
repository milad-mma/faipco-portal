/**
 * کارت «میزان استفاده از پرتال»: نمودار میله‌ای تعداد درخواست‌های کاربران واردشده به تفکیک روز، هفته، ماه
 * (شمسی) یا ساعت شبانه‌روز. بدون ورودی (props)؛ داده‌ی خام روزانه/ساعتی را از سرور می‌گیرد و در فرانت تجمیع می‌کند.
 */
import { useEffect, useMemo, useState } from "react";
import { Card, CircularProgress, Stack, Tab, Tabs, Typography } from "@mui/material";
import BarChartOutlinedIcon from "@mui/icons-material/BarChartOutlined";
import { fetchUsageStats } from "../api/system";
import UsageBarChart from "./UsageBarChart";
import { gregorianToJalali, JALALI_MONTH_NAMES } from "../utils/jalaliDate";
import PillTabs from "./PillTabs";

// تاریخ ISO میلادی (YYYY-MM-DD) را به برچسب «روز ماه شمسی» تبدیل می‌کند
function toJalaliDayLabel(isoDate) {
  const [y, m, d] = isoDate.split("-").map(Number);
  const { jm, jd } = gregorianToJalali(new Date(y, m - 1, d));
  return `${jd} ${JALALI_MONTH_NAMES[jm - 1]}`;
}

// کلید و برچسب هفته‌ی شمسی تقریبی (برای گروه‌بندی، نه استاندارد رسمی): تعداد روزهای سپری‌شده از
// ابتدای سال شمسی تقسیم بر ۷. فرمول روز سال (jd - 1) با فرمول jdays در jalaliDate.js هماهنگ است
// تا نتیجه با بقیه‌ی محاسبات پروژه یکی باشد.
function toJalaliWeekKey(isoDate) {
  const [y, m, d] = isoDate.split("-").map(Number);
  const { jy, jm, jd } = gregorianToJalali(new Date(y, m - 1, d));
  const dayOfYear = jm <= 6 ? (jm - 1) * 31 + (jd - 1) : 186 + (jm - 7) * 30 + (jd - 1);
  const weekNumber = Math.ceil((dayOfYear + 1) / 7);
  return { key: `${jy}-W${weekNumber}`, label: `هفته ${weekNumber} (${jy})` };
}

/** روزهای میلادی داده‌ی خام را به هفته‌ی شمسی گروه‌بندی و جمع می‌کند؛ خروجی: ۱۲ هفته‌ی آخر [{label, value}] */
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

// جمع درخواست‌ها به تفکیک روز؛ خروجی: ۱۴ روز آخر با برچسب شمسی
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

// جمع درخواست‌ها به تفکیک ماه شمسی؛ خروجی مرتب بر اساس سال-ماه
function aggregateByMonth(rawData) {
  const map = new Map();
  rawData.forEach(({ date, request_count }) => {
    const [y, m, d] = date.split("-").map(Number);
    const { jy, jm } = gregorianToJalali(new Date(y, m - 1, d));
    // گروه‌بندی بر اساس ماه شمسی واقعی انجام می‌شود نه برش رشته‌ی تاریخ میلادی، چون مرز ماه‌های شمسی
    // با ماه‌های میلادی هم‌راستا نیست و یک ماه شمسی به دو ماه میلادی می‌افتد.
    const monthKey = `${jy}-${String(jm).padStart(2, "0")}`;
    if (!map.has(monthKey)) {
      map.set(monthKey, { label: `${JALALI_MONTH_NAMES[jm - 1]} ${jy}`, value: 0, sortKey: monthKey });
    }
    map.get(monthKey).value += request_count;
  });
  return Array.from(map.values()).sort((a, b) => (a.sortKey > b.sortKey ? 1 : -1));
}

// جمع درخواست‌ها در ۲۴ دسته‌ی ساعت شبانه‌روز (تجمیع همه‌ی روزها)
function aggregateByHour(rawData) {
  const buckets = Array.from({ length: 24 }, () => 0);
  rawData.forEach(({ hour, request_count }) => {
    buckets[hour] += request_count;
  });
  return buckets.map((value, hour) => ({ label: `${String(hour).padStart(2, "0")}`, value }));
}

const TABS = [  // تب‌های نوع تجمیع نمودار
  { key: "daily", label: "روزانه" },
  { key: "weekly", label: "هفتگی" },
  { key: "monthly", label: "ماهانه" },
  { key: "hourly", label: "بر اساس ساعت روز" },
];

export default function UsageStatsCard() {
  const [rawData, setRawData] = useState(null);  // داده‌ی خام از سرور: [{date, hour, request_count}]؛ null = در حال بارگذاری
  const [activeTab, setActiveTab] = useState("daily");

  // دریافت داده هنگام mount؛ در صورت خطا آرایه‌ی خالی
  useEffect(() => {
    fetchUsageStats()
      .then(setRawData)
      .catch(() => setRawData([]));
  }, []);

  // داده‌ی نمودار بر اساس تب فعال
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

  // آیا آخرین میله بازه‌ی جاری و ناتمام است (امروز / هفته‌ی جاری / ماه جاری)؛ در این صورت کم‌رنگ
  // نمایش داده می‌شود تا کمتر بودنش با افت واقعی اشتباه نشود. تب ساعتی بازه‌ی ناتمام ندارد.
  const partialLast = useMemo(() => {
    if (!rawData || rawData.length === 0 || activeTab === "hourly") return false;
    const now = new Date();
    const todayIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    const lastDate = rawData.reduce((max, row) => (row.date && row.date > max ? row.date : max), "");
    if (!lastDate) return false;
    if (activeTab === "daily") return lastDate === todayIso;
    if (activeTab === "weekly") return toJalaliWeekKey(lastDate).key === toJalaliWeekKey(todayIso).key;
    if (activeTab === "monthly") {
      const a = gregorianToJalali(new Date(`${lastDate}T00:00:00`));
      const b = gregorianToJalali(now);
      return a.jy === b.jy && a.jm === b.jm;
    }
    return false;
  }, [rawData, activeTab]);

  // پرترافیک‌ترین ساعت شبانه‌روز؛ اگر هیچ درخواستی نباشد null
  const busiestHour = useMemo(() => {
    if (!rawData || rawData.length === 0) return null;
    const buckets = aggregateByHour(rawData);
    const busiest = buckets.reduce((max, cur) => (cur.value > max.value ? cur : max), buckets[0]);
    return busiest.value > 0 ? busiest : null;
  }, [rawData]);

  return (
    <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
      {/* عنوان کارت */}
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
        <BarChartOutlinedIcon fontSize="small" color="action" />
        <Typography variant="subtitle1" fontWeight={700}>
          میزان استفاده از پرتال
        </Typography>
      </Stack>
      {/* توضیح و پرترافیک‌ترین ساعت */}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        تعداد درخواست‌های واقعی کاربران وارد‌شده به پرتال — نه بازدید صفحه، تعداد تعامل واقعی با سرور.
        {busiestHour && (
          <>
            {" "}
            پرترافیک‌ترین ساعت شبانه‌روز معمولاً <strong>{busiestHour.label}:۰۰</strong> است.
          </>
        )}
      </Typography>

      {/* انتخاب نوع تجمیع */}
<PillTabs
            value={activeTab}
            onChange={setActiveTab}
            tabs={TABS.map((t) => ({ key: t.key, label: t.label }))}
            sx={{ mb: 2 }}
          />

      {/* اسپینر بارگذاری یا نمودار میله‌ای */}
      {rawData === null ? (
        <Stack alignItems="center" justifyContent="center" sx={{ height: 160 }}>
          <CircularProgress size={28} />
        </Stack>
      ) : (
        <UsageBarChart
          data={chartData}
          partialLast={partialLast}
          unit=" درخواست"
          emptyMessage="هنوز داده‌ای برای این بازه ثبت نشده"
        />
      )}
    </Card>
  );
}
