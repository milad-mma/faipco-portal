import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import RefreshOutlinedIcon from "@mui/icons-material/RefreshOutlined";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import BackLink from "../components/BackLink";
import PillTabs from "../components/PillTabs";
import { useAuth } from "../context/AuthContext";
import {
  GroupedBarChart,
  HBarChart,
  Heatmap,
  LineChart,
  StackedBarChart,
  useChartColors,
} from "../components/turnover/TurnoverCharts";
import {
  createTurnoverCategory,
  deleteTurnoverCategory,
  downloadTurnoverExport,
  fetchTurnoverCategories,
  fetchTurnoverReport,
  setTurnoverAliasCategory,
  updateTurnoverCategory,
} from "../api/turnoverReport";

/**
 * صفحه‌ی «گزارش جذب و ترک کار» (مسیر /reports/turnover، مجوز reports.turnover).
 * داده مستقیماً از دیتابیس منبع هر سایت خوانده می‌شود (پرسنل قطع‌همکاری‌شده در پرتال نیستند) و فقط
 * شمارش و درصد نمایش داده می‌شود. تب دوم دسته‌بندی متن‌های آزاد «علت ترک کار» است.
 */

const GROUP_LABEL = {
  voluntary: "به خواست کارگر",
  involuntary: "به خواست کارفرما",
  probation: "فسخ در دوره‌ی آزمایشی",
  other: "سایر (بازنشستگی، ازکارافتادگی، فوت)",
  excluded: "خارج از آمار",
  uncategorized: "دسته‌بندی نشده",
};
const GROUP_ORDER = ["voluntary", "involuntary", "probation", "other", "uncategorized"];

const fa = (v, digits = 0) =>
  v === null || v === undefined ? "—" : Number(v).toLocaleString("fa-IR", { maximumFractionDigits: digits });
const pct = (v) => (v === null || v === undefined ? "—" : `${fa(v, 1)}٪`);

// تولید فهرست ماه‌ها بین دو «YYYY/MM»
function monthsBetween(from, to) {
  if (!from || !to) return [];
  let [y, m] = from.split("/").map(Number);
  const [ty, tm] = to.split("/").map(Number);
  const out = [];
  while (y < ty || (y === ty && m <= tm)) {
    out.push(`${y}/${String(m).padStart(2, "0")}`);
    m += 1;
    if (m > 12) {
      m = 1;
      y += 1;
    }
  }
  return out;
}

function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

// کارت یک بخش گزارش با عنوان و توضیح کوتاه
function Section({ title, subtitle, children, action }) {
  return (
    <Card variant="outlined" sx={{ borderRadius: 2, p: { xs: 1.5, sm: 2 }, height: "100%" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1} sx={{ mb: 1.5 }}>
        <Box>
          <Typography fontWeight={800}>{title}</Typography>
          {subtitle && (
            <Typography variant="caption" color="text.secondary">
              {subtitle}
            </Typography>
          )}
        </Box>
        {action}
      </Stack>
      {children}
    </Card>
  );
}

// کاشی شاخص: عدد بزرگ، عنوان و تعریف در Tooltip
function Kpi({ label, value, hint, sub }) {
  return (
    <Card variant="outlined" sx={{ borderRadius: 2, p: 1.5, height: "100%" }}>
      <Stack direction="row" spacing={0.5} alignItems="center">
        <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
          {label}
        </Typography>
        {hint && (
          <Tooltip title={hint} arrow enterTouchDelay={0}>
            <InfoOutlinedIcon sx={{ fontSize: 15, color: "text.disabled" }} />
          </Tooltip>
        )}
      </Stack>
      <Typography variant="h5" fontWeight={800} sx={{ mt: 0.5 }}>
        {value}
      </Typography>
      {sub && (
        <Typography variant="caption" color="text.secondary">
          {sub}
        </Typography>
      )}
    </Card>
  );
}

// ---------- تب گزارش ----------

function ReportTab({ onGoCategories }) {
  const colors = useChartColors();
  const [filters, setFilters] = useState({ site_id: "", from_month: "", to_month: "", department: "", gender: "" });
  const [report, setReport] = useState(null);
  const [bounds, setBounds] = useState(null); // { start, end } کل بازه‌ی قابل انتخاب
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [openReason, setOpenReason] = useState(null);
  const latest = useRef(0); // فقط پاسخ آخرین درخواست اعمال می‌شود (تغییر سریع فیلترها)

  function load(refresh = false) {
    const requestId = ++latest.current;
    setLoading(true);
    setError("");
    fetchTurnoverReport({ ...filters, refresh: refresh || undefined })
      .then((data) => {
        if (requestId !== latest.current) return;
        setReport(data);
        if (data.range && !filters.from_month && !filters.to_month) {
          setBounds({ start: data.range.start_month, end: data.range.to_month });
        }
      })
      .catch((err) => requestId === latest.current && setError(err.response?.data?.detail || "دریافت گزارش با خطا مواجه شد."))
      .finally(() => requestId === latest.current && setLoading(false));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  async function handleExport() {
    setExporting(true);
    try {
      const blob = await downloadTurnoverExport(filters);
      saveBlob(blob, `turnover_${new Date().toISOString().slice(0, 10)}.xlsx`);
    } catch {
      setError("خروجی Excel با خطا مواجه شد.");
    } finally {
      setExporting(false);
    }
  }

  const set = (key) => (e) => setFilters((f) => ({ ...f, [key]: e.target.value, ...(key === "site_id" ? { department: "", from_month: "", to_month: "" } : {}) }));
  const monthOptions = useMemo(() => monthsBetween(bounds?.start, bounds?.end), [bounds]);

  if (!report && loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }
  if (!report) return <Alert severity="error">{error}</Alert>;
  if (report.not_configured) {
    return (
      <Alert severity="info">
        برای هیچ‌یک از سایت‌های در دسترس شما، ستون‌های «تاریخ استخدام» و «تاریخ ترک کار» در «تنظیمات سایت ← نگاشت
        پرسنل» تنظیم نشده است. بعد از تنظیم (کاراوب: Emp_Date و End_Date)، گزارش اینجا نمایش داده می‌شود.
      </Alert>
    );
  }

  const k = report.kpis;
  const labels = report.monthly.map((m) => m.month);
  const warnings = report.warnings || {};
  const uncategorized = k.by_group.uncategorized || 0;
  const cohorts = report.cohorts.slice(-6);

  return (
    <Box sx={{ opacity: loading ? 0.6 : 1, transition: "opacity .2s" }}>
      {/* فیلترها در یک ردیف بالای نمودارها */}
      <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap alignItems="center" sx={{ mb: 2 }}>
        {report.sites.length > 1 && (
          <TextField select size="small" label="سایت" value={filters.site_id} onChange={set("site_id")} sx={{ minWidth: 170 }}>
            <MenuItem value="">همه‌ی سایت‌ها</MenuItem>
            {report.sites.map((s) => (
              <MenuItem key={s.id} value={s.id}>
                {s.name}
              </MenuItem>
            ))}
          </TextField>
        )}
        <TextField select size="small" label="از ماه" value={filters.from_month || report.range.from_month} onChange={set("from_month")} sx={{ minWidth: 120 }}>
          {monthOptions.map((m) => (
            <MenuItem key={m} value={m} dir="ltr">
              {m}
            </MenuItem>
          ))}
        </TextField>
        <TextField select size="small" label="تا ماه" value={filters.to_month || report.range.to_month} onChange={set("to_month")} sx={{ minWidth: 120 }}>
          {monthOptions.map((m) => (
            <MenuItem key={m} value={m} dir="ltr">
              {m}
            </MenuItem>
          ))}
        </TextField>
        <TextField select size="small" label="واحد" value={filters.department} onChange={set("department")} sx={{ minWidth: 170 }}>
          <MenuItem value="">همه‌ی واحدها</MenuItem>
          {report.department_options.map((d) => (
            <MenuItem key={d.code} value={d.code}>
              {d.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField select size="small" label="جنسیت" value={filters.gender} onChange={set("gender")} sx={{ minWidth: 110 }}>
          <MenuItem value="">همه</MenuItem>
          <MenuItem value={1}>مرد</MenuItem>
          <MenuItem value={2}>زن</MenuItem>
        </TextField>
        <Box sx={{ flex: 1 }} />
        <Tooltip title="داده برای ۵ دقیقه نگه داشته می‌شود؛ این دکمه همین حالا از دیتابیس منبع می‌خواند">
          <span>
            <Button size="small" startIcon={loading ? <CircularProgress size={14} /> : <RefreshOutlinedIcon />} onClick={() => load(true)} disabled={loading}>
              به‌روزرسانی
            </Button>
          </span>
        </Tooltip>
        <Button size="small" variant="outlined" startIcon={exporting ? <CircularProgress size={14} /> : <DownloadOutlinedIcon />} onClick={handleExport} disabled={exporting}>
          خروجی Excel
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {uncategorized > 0 && (
        <Alert
          severity="warning"
          sx={{ mb: 2 }}
          action={onGoCategories && <Button color="inherit" size="small" onClick={onGoCategories}>دسته‌بندی</Button>}
        >
          علت {fa(uncategorized)} ترک کار در این بازه در هیچ دسته‌ای نیست؛ در نرخ کل حساب می‌شوند ولی در «به خواست کارگر/کارفرما» نه.
        </Alert>
      )}
      {(warnings.missing_term || warnings.missing_hire || warnings.excluded || warnings.unassigned_unit) && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {warnings.unassigned_unit
            ? `${fa(warnings.unassigned_unit)} نفر (شاغل یا ترک‌کرده) در واحدی هستند که زیر هیچ واحد ریشه‌ی سایت‌ها نیست یا دیگر وجود ندارد و در آمار نیامدند. `
            : ""}
          {warnings.excluded ? `${fa(warnings.excluded)} رکورد با علت «خارج از آمار» (مثل کد پرسنلی اشتباه) کنار گذاشته شد. ` : ""}
          {warnings.missing_term ? `${fa(warnings.missing_term)} نفر غیرفعال‌اند ولی تاریخ ترک کار ندارند و حساب نشدند. ` : ""}
          {warnings.missing_hire ? `${fa(warnings.missing_hire)} رکورد تاریخ استخدام ندارد و حساب نشد.` : ""}
        </Alert>
      )}

      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        بازه‌ی گزارش: {report.range.from_month} تا {report.range.to_month} ({fa(k.months)} ماه) — شروع آمار: {report.range.start_month}
      </Typography>

      {/* شاخص‌ها */}
      <Grid container spacing={1.5} sx={{ mb: 2.5 }}>
        {[
          ["پرسنل ابتدا / انتهای دوره", `${fa(k.start_headcount)} ← ${fa(k.end_headcount)}`, "پرسنل شاغل روز اول بازه و روز آخر بازه", `میانگین ${fa(k.avg_headcount, 1)} نفر`],
          ["استخدام", fa(k.hires), "تعداد استخدام با تاریخ استخدام داخل بازه", `نرخ جذب سالانه‌شده ${pct(k.hire_rate_annualized)}`],
          ["ترک کار", fa(k.separations), "تعداد قطع همکاری با تاریخ ترک کار داخل بازه (بدون موارد خارج از آمار)", `خالص ${k.net > 0 ? "+" : ""}${fa(k.net)}`],
          ["نرخ ترک کار (سالانه‌شده)", pct(k.turnover_rate_annualized), "میانگین نرخ ماهانه × ۱۲. نرخ ماهانه = ترک کار ماه ÷ میانگین پرسنل ماه × ۱۰۰ (استاندارد SHRM)", `کل دوره ${pct(k.turnover_rate_period)}`],
          ["ترک به خواست کارگر", pct(k.voluntary_rate_annualized), "استعفا و ترک کار — سالانه‌شده", `${fa(k.by_group.voluntary)} نفر`],
          ["ترک به خواست کارفرما", pct(k.involuntary_rate_annualized), "عدم تمدید، تعدیل، اخراج — سالانه‌شده", `${fa(k.by_group.involuntary)} نفر`],
          ["ترک در ۹۰ روز اول", pct(k.exit_within_90_share), "سهم ترک‌کرده‌هایی که کمتر از ۹۰ روز (سقف دوره‌ی آزمایشی ماده ۱۱) خدمت داشتند", `۳۰ روز اول ${pct(k.exit_within_30_share)}`],
          ["ریزش نیروی جدید (۹۰ روز)", pct(k.new_hire_90d_attrition), "از استخدام‌های بازه که حداقل ۹۰ روز از استخدامشان گذشته، چند درصد در همان ۹۰ روز رفته‌اند", `پایه ${fa(k.new_hire_90d_base)} نفر`],
          ["ماندگاری سال اول", pct(k.first_year_retention), "از استخدام‌های بازه که حداقل یک سال از استخدامشان گذشته، چند درصد بعد از ۳۶۵ روز هنوز مانده‌اند", `پایه ${fa(k.first_year_base)} نفر`],
          ["نسبت جایگزینی", k.replacement_ratio === null ? "—" : fa(k.replacement_ratio, 2), "استخدام ÷ ترک کار؛ کمتر از ۱ یعنی سازمان در حال کوچک شدن است", null],
          ["میانگین مدت خدمت هنگام ترک", k.avg_tenure_at_exit_months === null ? "—" : `${fa(k.avg_tenure_at_exit_months, 1)} ماه`, "میانگین فاصله‌ی استخدام تا ترک کار در ترک‌کرده‌های بازه", `ترک در سال اول ${pct(k.exit_within_365_share)}`],
        ].map(([label, value, hint, sub]) => (
          <Grid item xs={6} sm={4} md={3} key={label}>
            <Kpi label={label} value={value} hint={hint} sub={sub} />
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} lg={6}>
          <Section title="استخدام و ترک کار ماهانه">
            <GroupedBarChart
              labels={labels}
              series={[
                { name: "استخدام", color: colors.hires, values: report.monthly.map((m) => m.hires) },
                { name: "ترک کار", color: colors.separations, values: report.monthly.map((m) => m.separations) },
              ]}
            />
          </Section>
        </Grid>
        <Grid item xs={12} lg={6}>
          <Section title="تعداد پرسنل آخر ماه">
            <LineChart
              labels={labels}
              series={[{ name: "پرسنل آخر ماه", color: colors.blue, values: report.monthly.map((m) => m.end_headcount) }]}
              yFormat={(v) => fa(v)}
            />
          </Section>
        </Grid>
        <Grid item xs={12} lg={6}>
          <Section title="نرخ ترک کار" subtitle="نرخ ماهانه و نرخ متحرک ۱۲ماهه (جمع ۱۲ نرخ ماهانه‌ی اخیر = نرخ سالانه‌ی واقعی تا آن ماه)">
            <LineChart
              labels={labels}
              series={[
                { name: "نرخ ماهانه (٪)", color: colors.orange, values: report.monthly.map((m) => m.turnover_rate) },
                { name: "متحرک ۱۲ماهه (٪)", color: colors.blue, dashed: true, values: report.monthly.map((m) => m.rolling12_rate) },
              ]}
              yFormat={(v) => `${fa(v, 1)}٪`}
            />
          </Section>
        </Grid>
        <Grid item xs={12} lg={6}>
          <Section title="ترک کار به تفکیک گروه" subtitle="به خواست کارگر، کارفرما، فسخ آزمایشی و سایر">
            <StackedBarChart
              labels={labels}
              series={GROUP_ORDER.map((g) => ({ name: GROUP_LABEL[g], color: colors.groups[g], values: report.monthly.map((m) => m.by_group[g]) }))}
            />
          </Section>
        </Grid>

        <Grid item xs={12} md={6}>
          <Section title="علت ترک کار" subtitle="با کلیک روی هر دسته، متن‌های ثبت‌شده در منبع نمایش داده می‌شود">
            <Stack spacing={1}>
              {report.reasons.map((r) => (
                <Box key={r.category_id ?? "none"}>
                  <Box sx={{ cursor: "pointer" }} onClick={() => setOpenReason(openReason === r.title ? null : r.title)}>
                    <HBarChart
                      items={[{ key: r.title, label: r.title, value: r.count, note: pct(r.share), color: colors.groups[r.group] || colors.gray }]}
                    />
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 0.25 }}>
                      <Typography variant="caption" color="text.secondary" sx={{ flex: 1 }}>
                        {GROUP_LABEL[r.group]}
                        {r.legal_basis ? ` — ${r.legal_basis}` : ""}
                      </Typography>
                      <ExpandMoreIcon sx={{ fontSize: 16, color: "text.disabled", transform: openReason === r.title ? "rotate(180deg)" : "none" }} />
                    </Stack>
                  </Box>
                  <Collapse in={openReason === r.title}>
                    <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 0.75 }}>
                      {r.texts.map((t) => (
                        <Chip key={t.text} size="small" variant="outlined" label={`${t.text} (${fa(t.count)})`} />
                      ))}
                    </Stack>
                  </Collapse>
                </Box>
              ))}
              {!report.reasons.length && <Typography variant="body2" color="text.secondary">ترک کاری در این بازه نیست</Typography>}
            </Stack>
          </Section>
        </Grid>
        <Grid item xs={12} md={6}>
          <Section title="مدت خدمت هنگام ترک" subtitle="ترک‌های زودهنگام معمولاً نشانه‌ی مشکل در جذب یا آموزش ابتدایی‌اند">
            <HBarChart
              items={report.tenure_buckets.map((b) => ({ key: b.key, label: b.label, value: b.count, note: pct(b.share) }))}
              color={colors.orange}
            />
          </Section>
        </Grid>

        <Grid item xs={12} lg={6}>
          <Section title="منحنی ماندگاری گروه‌های استخدامی" subtitle="هر خط یک فصل استخدام؛ درصد باقی‌مانده بعد از ۳۰، ۹۰، ۱۸۰ و ۳۶۵ روز (نقطه‌ی بدون داده یعنی هنوز آن مدت نگذشته)">
            {cohorts.length ? (
              <>
                <LineChart
                  labels={["۳۰ روز", "۹۰ روز", "۱۸۰ روز", "۳۶۵ روز"]}
                  xFormat={(l) => l}
                  yMax={100}
                  yFormat={(v) => `${fa(v)}٪`}
                  valueFormat={(v) => (v === null || v === undefined ? "هنوز نگذشته" : `${fa(v, 1)}٪`)}
                  series={cohorts.map((c, i) => ({ name: `${c.label} (${fa(c.size)} نفر)`, color: colors.categorical[i], values: c.points.map((p) => p.retention) }))}
                />
              </>
            ) : (
              <Typography variant="body2" color="text.secondary">استخدامی در این بازه نیست</Typography>
            )}
          </Section>
        </Grid>
        <Grid item xs={12} lg={6}>
          <Section title="ترکیب جمعیتی ترک‌کرده‌ها" subtitle="تعداد ترک کار (و استخدام در همان بازه)">
            <Grid container spacing={2}>
              {[
                ["جنسیت", report.demographics.gender],
                ["سن هنگام ترک", report.demographics.age],
                ["مدرک تحصیلی", report.demographics.education],
              ].map(([title, rows]) => (
                <Grid item xs={12} sm={6} key={title}>
                  <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
                    {title}
                  </Typography>
                  <HBarChart items={rows.map((r) => ({ key: String(r.key), label: r.label, value: r.separations, note: `استخدام ${fa(r.hires)}` }))} color={colors.orange} maxItems={8} />
                </Grid>
              ))}
              <Grid item xs={12} sm={6}>
                <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
                  ۱۰ سمت با بیشترین ترک کار
                </Typography>
                <HBarChart items={report.demographics.positions.map((r) => ({ key: String(r.key), label: r.label, value: r.separations, note: `استخدام ${fa(r.hires)}` }))} color={colors.orange} />
              </Grid>
            </Grid>
          </Section>
        </Grid>

        <Grid item xs={12}>
          <Section title="واحدها" subtitle="واحد هر نفر آخرین واحد ثبت‌شده در منبع است؛ برای واحدهای کمتر از ۵ نفر نرخ نمایش داده نمی‌شود">
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {["واحد", "استخدام", "ترک کار", "به خواست کارگر", "به خواست کارفرما", "میانگین پرسنل", "پرسنل انتهای دوره", "نرخ ترک سالانه‌شده"].map((h) => (
                      <TableCell key={h} sx={{ fontWeight: 700, whiteSpace: "nowrap" }}>{h}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.departments.map((d) => (
                    <TableRow key={d.code ?? d.name} hover>
                      <TableCell>{d.name}</TableCell>
                      <TableCell>{fa(d.hires)}</TableCell>
                      <TableCell>{fa(d.separations)}</TableCell>
                      <TableCell>{fa(d.voluntary)}</TableCell>
                      <TableCell>{fa(d.involuntary)}</TableCell>
                      <TableCell>{fa(d.avg_headcount, 1)}</TableCell>
                      <TableCell>{fa(d.end_headcount)}</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>{pct(d.turnover_rate_annualized)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Section>
        </Grid>
        <Grid item xs={12}>
          <Section title="نقشه‌ی حرارتی ترک کار (واحد × ماه)" subtitle="۱۵ واحد با بیشترین ترک کار؛ رنگ پررنگ‌تر یعنی ترک بیشتر">
            <Heatmap columns={report.heatmap.months} rows={report.heatmap.rows} />
          </Section>
        </Grid>

        <Grid item xs={12} md={5}>
          <Section title="خلاصه‌ی سالانه">
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {["سال", "استخدام", "ترک کار", "خالص", "نرخ ترک"].map((h) => (
                      <TableCell key={h} sx={{ fontWeight: 700 }}>{h}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.yearly.map((y) => (
                    <TableRow key={y.year}>
                      <TableCell>
                        {y.year}
                        {y.months < 12 && (
                          <Typography component="span" variant="caption" color="text.secondary"> ({fa(y.months)} ماه)</Typography>
                        )}
                      </TableCell>
                      <TableCell>{fa(y.hires)}</TableCell>
                      <TableCell>{fa(y.separations)}</TableCell>
                      <TableCell>{y.net > 0 ? "+" : ""}{fa(y.net)}</TableCell>
                      <TableCell>
                        {pct(y.turnover_rate)}
                        {y.months < 12 && (
                          <Typography component="span" variant="caption" color="text.secondary"> (سالانه‌شده {pct(y.turnover_rate_annualized)})</Typography>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Section>
        </Grid>
        <Grid item xs={12} md={7}>
          <Section title="جدول ماهانه">
            <TableContainer sx={{ maxHeight: 420 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    {["ماه", "اول ماه", "استخدام", "ترک", "آخر ماه", "کارگر", "کارفرما", "نرخ ترک", "متحرک ۱۲ماهه"].map((h) => (
                      <TableCell key={h} sx={{ fontWeight: 700, whiteSpace: "nowrap" }}>{h}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {report.monthly.map((m) => (
                    <TableRow key={m.month} hover>
                      <TableCell dir="ltr" sx={{ textAlign: "end" }}>{m.month}</TableCell>
                      <TableCell>{fa(m.start_headcount)}</TableCell>
                      <TableCell>{fa(m.hires)}</TableCell>
                      <TableCell>{fa(m.separations)}</TableCell>
                      <TableCell>{fa(m.end_headcount)}</TableCell>
                      <TableCell>{fa(m.by_group.voluntary)}</TableCell>
                      <TableCell>{fa(m.by_group.involuntary)}</TableCell>
                      <TableCell>{pct(m.turnover_rate)}</TableCell>
                      <TableCell>{pct(m.rolling12_rate)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Section>
        </Grid>
        <Grid item xs={12}>
          <Alert severity="info" icon={false}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 0.5 }}>تعریف‌ها</Typography>
            <Typography variant="body2" component="div" sx={{ lineHeight: 2 }}>
              پرسنل اول ماه: استخدام قبل از روز اول ماه و هنوز شاغل در آن روز. میانگین پرسنل ماه = (اول ماه + آخر ماه) ÷ ۲.
              نرخ ترک ماهانه = ترک کار ماه ÷ میانگین پرسنل × ۱۰۰؛ نرخ یک دوره جمع نرخ‌های ماهانه و نرخ سالانه‌شده میانگین
              نرخ ماهانه × ۱۲ است (استاندارد SHRM). گروه‌ها طبق طبقه‌بندی استاندارد خروج کارکنان و دسته‌ها بر اساس قانون کار
              (ماده ۲۱، ماده ۱۱ و ماده ۲۷) هستند. رکوردهای «خارج از آمار» (مثل کد پرسنلی اشتباه) نه استخدام حساب می‌شوند نه
              ترک کار. داده مستقیماً از دیتابیس منبع خوانده می‌شود و هیچ نام یا کد پرسنلی در این گزارش نیست.
            </Typography>
          </Alert>
        </Grid>
      </Grid>
    </Box>
  );
}

// ---------- تب دسته‌بندی علت‌ها ----------

const EMPTY_CAT = { title: "", group: "voluntary", legal_basis: "", sort_order: 0 };

function CategoriesTab() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(null); // شناسه‌ی متنی که در حال ذخیره است
  const [edit, setEdit] = useState(null); // { id?, ...EMPTY_CAT }

  function load() {
    setError("");
    fetchTurnoverCategories()
      .then(setData)
      .catch((err) => setError(err.response?.data?.detail || "دریافت دسته‌ها با خطا مواجه شد."));
  }
  useEffect(load, []);

  async function assign(alias, categoryId) {
    setSaving(alias.id);
    try {
      await setTurnoverAliasCategory(alias.id, categoryId);
      setData((d) => ({ ...d, aliases: d.aliases.map((a) => (a.id === alias.id ? { ...a, category_id: categoryId || null } : a)) }));
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره با خطا مواجه شد.");
    } finally {
      setSaving(null);
    }
  }

  async function saveCategory() {
    try {
      const payload = { ...edit, legal_basis: edit.legal_basis || null, sort_order: Number(edit.sort_order) || 0 };
      delete payload.id;
      delete payload.key;
      if (edit.id) await updateTurnoverCategory(edit.id, payload);
      else await createTurnoverCategory(payload);
      setEdit(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail?.[0]?.msg || err.response?.data?.detail || "ذخیره‌ی دسته با خطا مواجه شد.");
    }
  }

  async function removeCategory(cat) {
    if (!window.confirm(`دسته‌ی «${cat.title}» حذف شود؟ متن‌های آن «دسته‌بندی نشده» می‌شوند.`)) return;
    try {
      await deleteTurnoverCategory(cat.id);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف با خطا مواجه شد.");
    }
  }

  if (!data) return error ? <Alert severity="error">{error}</Alert> : <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}><CircularProgress /></Box>;
  const canManage = data.can_manage;
  const uncategorized = data.aliases.filter((a) => !a.category_id && (a.count ?? 1) > 0);

  return (
    <Stack spacing={2}>
      {error && <Alert severity="error">{error}</Alert>}
      {data.count_error && <Alert severity="warning">تعداد متن‌ها محاسبه نشد: {data.count_error}</Alert>}
      <Alert severity="info">
        علت ترک کار در منبع متن آزاد است. هر متن مختلف (بعد از یکسان‌سازی املا مثل «استعفاء» = «استعفا») یک ردیف پایین
        دارد که باید به یک دسته وصل شود. متن‌های تازه خودکار با وضعیت «دسته‌بندی نشده» اضافه می‌شوند.
        {!canManage && " برای تغییر دسته‌بندی مجوز «ویرایش دسته‌بندی علت‌های ترک کار» لازم است."}
      </Alert>

      <Section title={`متن‌های علت ترک کار${uncategorized.length ? ` — ${fa(uncategorized.length)} مورد دسته‌بندی نشده` : ""}`}>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>متن در منبع</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>تعداد</TableCell>
                <TableCell sx={{ fontWeight: 700, minWidth: 220 }}>دسته</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.aliases.map((a) => (
                <TableRow key={a.id} sx={!a.category_id ? { bgcolor: "rgba(237,161,0,0.08)" } : undefined}>
                  <TableCell>{a.text || "(بدون علت)"}</TableCell>
                  <TableCell>{a.count === null ? "—" : fa(a.count)}</TableCell>
                  <TableCell>
                    <TextField
                      select
                      size="small"
                      fullWidth
                      value={a.category_id || ""}
                      onChange={(e) => assign(a, e.target.value)}
                      disabled={!canManage || saving === a.id}
                    >
                      <MenuItem value="">
                        <em>دسته‌بندی نشده</em>
                      </MenuItem>
                      {data.categories.map((c) => (
                        <MenuItem key={c.id} value={c.id}>
                          {c.title} — {GROUP_LABEL[c.group]}
                        </MenuItem>
                      ))}
                    </TextField>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Section>

      <Section
        title="دسته‌ها"
        subtitle="گروه هر دسته تعیین می‌کند در کدام نرخ (به خواست کارگر، کارفرما، ...) حساب شود"
        action={canManage && <Button size="small" startIcon={<AddOutlinedIcon />} onClick={() => setEdit({ ...EMPTY_CAT })}>دسته‌ی جدید</Button>}
      >
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                {["دسته", "گروه", "مبنای قانونی", ""].map((h) => (
                  <TableCell key={h} sx={{ fontWeight: 700 }}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {data.categories.map((c) => (
                <TableRow key={c.id}>
                  <TableCell>{c.title}</TableCell>
                  <TableCell>{GROUP_LABEL[c.group]}</TableCell>
                  <TableCell>{c.legal_basis || "—"}</TableCell>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>
                    {canManage && (
                      <>
                        <IconButton size="small" onClick={() => setEdit({ ...c, legal_basis: c.legal_basis || "" })} aria-label="ویرایش">
                          <EditOutlinedIcon fontSize="small" />
                        </IconButton>
                        <IconButton size="small" color="error" onClick={() => removeCategory(c)} aria-label="حذف">
                          <DeleteOutlineOutlinedIcon fontSize="small" />
                        </IconButton>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Section>

      <Dialog open={Boolean(edit)} onClose={() => setEdit(null)} fullWidth maxWidth="sm">
        <DialogTitle>{edit?.id ? "ویرایش دسته" : "دسته‌ی جدید"}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2}>
            <TextField label="عنوان" value={edit?.title || ""} onChange={(e) => setEdit({ ...edit, title: e.target.value })} inputProps={{ maxLength: 120 }} />
            <TextField select label="گروه آماری" value={edit?.group || "voluntary"} onChange={(e) => setEdit({ ...edit, group: e.target.value })}>
              {Object.entries(GROUP_LABEL)
                .filter(([k]) => k !== "uncategorized")
                .map(([k, l]) => (
                  <MenuItem key={k} value={k}>{l}</MenuItem>
                ))}
            </TextField>
            <TextField label="مبنای قانونی (اختیاری)" value={edit?.legal_basis || ""} onChange={(e) => setEdit({ ...edit, legal_basis: e.target.value })} inputProps={{ maxLength: 255 }} />
            <TextField label="ترتیب نمایش" type="number" value={edit?.sort_order ?? 0} onChange={(e) => setEdit({ ...edit, sort_order: e.target.value })} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEdit(null)}>انصراف</Button>
          <Button variant="contained" onClick={saveCategory} disabled={!edit?.title?.trim()}>ذخیره</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

export default function TurnoverReportPage() {
  const { user } = useAuth();
  const canSeeReport = Boolean(user?.can_view_turnover_report);
  const [tab, setTab] = useState(canSeeReport ? "report" : "categories"); // دارنده‌ی فقط مجوز دسته‌بندی مستقیم به تب دسته‌ها می‌رود
  const [reportKey, setReportKey] = useState(0); // با برگشت از دسته‌بندی، گزارش دوباره محاسبه می‌شود
  const canSeeCategories = user?.can_view_turnover_report || user?.can_manage_turnover_categories;

  function changeTab(next) {
    if (next === "report" && tab === "categories") setReportKey((k) => k + 1);
    setTab(next);
  }

  return (
    <Box sx={{ maxWidth: 1400, mx: "auto" }}>
      <BackLink to="/" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        گزارش جذب و ترک کار
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        روند استخدام، ترک کار، نرخ‌ها، علت‌ها و ماندگاری نیروی جدید — مستقیم از اطلاعات کاراوب
      </Typography>
      {canSeeCategories && canSeeReport && (
        <PillTabs
          tabs={[
            { key: "report", label: "گزارش" },
            { key: "categories", label: "دسته‌بندی علت‌ها" },
          ]}
          value={tab}
          onChange={changeTab}
          sx={{ mb: 2, maxWidth: 420 }}
        />
      )}
      {tab === "report" ? <ReportTab key={reportKey} onGoCategories={canSeeCategories ? () => setTab("categories") : null} /> : <CategoriesTab />}
    </Box>
  );
}
