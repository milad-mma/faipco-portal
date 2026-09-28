/**
 * صفحه گزارش «پرسنل آنلاین» (آزمایشی).
 * دو نوع گزارش: «آنلاین در اپ» (هر پرسنلی که پرتال را باز کرده، بدون نیاز به GPS) و «حضور در محدوده
 * (GPS)» (بازه‌هایی که اپ باز بوده و موقعیت داخل محدوده‌ی مجاز سایت بوده)؛ با فیلتر سایت، پرسنل و
 * «فقط آنلاین‌های فعلی» و صفحه‌بندی سمت سرور.
 */
import { useEffect, useState } from "react";
import PillTabs from "../components/PillTabs";
import {
  Alert,
  Autocomplete,
  Box,
  Chip,
  CircularProgress,
  FormControlLabel,
  Pagination,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import { fetchPresenceSessions } from "../api/attendance";
import { fetchEmployees } from "../api/employees";
import SiteFilterSelect from "../components/SiteFilterSelect";
import { monoFontSx } from "../theme";
import { searchFilterOptions } from "../utils/searchText";

const PAGE_SIZE = 50;  // تعداد ردیف در هر صفحه

// مدت بر حسب ثانیه را به متن فارسی (ساعت/دقیقه/ثانیه) تبدیل می‌کند؛ null = «—»
function formatDuration(seconds) {
  if (seconds == null) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h} ساعت ${m} دقیقه`;
  if (m > 0) return `${m} دقیقه ${s} ثانیه`;
  return `${s} ثانیه`;
}

// کامپوننت صفحه؛ فیلترها و جدول جلسات حضور را مدیریت می‌کند
export default function PresenceReportPage() {
  const [sessions, setSessions] = useState(null);  // جلسات صفحه فعلی؛ null = در حال بارگذاری
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);  // شماره صفحه از ۱
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [selectedSiteId, setSelectedSiteId] = useState(null);
  const [onlyOnline, setOnlyOnline] = useState(false);
  const [kind, setKind] = useState("app"); // "app" = آنلاین در اپ، "gps" = حضور در محدوده

  const [employeeOptions, setEmployeeOptions] = useState([]);  // گزینه‌های Autocomplete پرسنل
  const [employeeSearch, setEmployeeSearch] = useState("");  // متن تایپ‌شده در Autocomplete برای جست‌وجوی پرسنل

  // بارگذاری جلسات حضور با فیلترها و صفحه فعلی
  useEffect(() => {
    setSessions(null);
    fetchPresenceSessions({
      page,
      pageSize: PAGE_SIZE,
      employeeId: selectedEmployee?.id,
      siteId: selectedSiteId,
      onlyOnline,
      kind,
    }).then((data) => {
      setSessions(data.items);
      setTotal(data.total);
    });
  }, [page, selectedEmployee, selectedSiteId, onlyOnline, kind]);

  // جست‌وجوی پرسنل با تأخیر ۳۰۰ میلی‌ثانیه بعد از آخرین حرف (نه یک درخواست برای هر حرف)؛
  // پاسخ جست‌وجوی قدیمی‌تر روی نتیجه‌ی جدیدتر نوشته نمی‌شود
  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      fetchEmployees({ search: employeeSearch, pageSize: 20 })
        .then((data) => !cancelled && setEmployeeOptions(data.items || []))
        .catch(() => {});
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [employeeSearch]);

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        پرسنل آنلاین
      </Typography>
      <Alert severity="warning" icon={<ScienceOutlinedIcon />} sx={{ mb: 1.5 }}>
        این قابلیت آزمایشی است — پایین همین صفحه، توضیح کامل نحوه کار این مانیتورینگ و ارتباطش با GPS
        آمده.
      </Alert>
      <PillTabs
        tabs={[
          { key: "app", label: "آنلاین در اپ (همه‌ی پرسنل)" },
          { key: "gps", label: "حضور در محدوده (GPS)" },
        ]}
        value={kind}
        onChange={(k) => {
          setKind(k);
          setPage(1);
        }}
        sx={{ mb: 2, maxWidth: 560 }}
      />
      <Alert severity="info" sx={{ mb: 3 }}>
        {kind === "app"
          ? "هر ردیف یک بازه‌ی واقعی است که پرسنل پرتال را باز داشته — بدون توجه به موقعیت GPS. هر دستگاه یا تب باز یک ردیف جداست."
          : "هر ردیف یک بازه‌ی واقعی است که پرسنل هم اپ را باز داشته، هم داخل محدوده‌ی مجاز سایت بوده — فقط برای پرسنلی که مجوز ثبت تردد GPS دارند. اگر خارج از محدوده باشد، ردیفی ثبت نمی‌شود."}
      </Alert>

      {/* نوار فیلترها؛ تغییر هر فیلتر صفحه را به ۱ برمی‌گرداند */}
      <Stack direction="row" spacing={2} sx={{ mb: 3 }} flexWrap="wrap" rowGap={2} alignItems="center">
        <SiteFilterSelect
          value={selectedSiteId}
          permission="attendance.view_logs"
          onChange={(value) => {
            setSelectedSiteId(value);
            setPage(1);
          }}
        />
        <Autocomplete
          filterOptions={searchFilterOptions}
          sx={{ minWidth: 260 }}
          options={employeeOptions}
          getOptionLabel={(o) => `${o.first_name} ${o.last_name} (${o.personnel_code})`}
          value={selectedEmployee}
          onChange={(_, value) => {
            setSelectedEmployee(value);
            setPage(1);
          }}
          onInputChange={(_, value) => setEmployeeSearch(value)}
          renderInput={(params) => <TextField {...params} label="فیلتر بر اساس پرسنل" size="small" />}
          isOptionEqualToValue={(o, v) => o.id === v.id}
        />
        <FormControlLabel
          control={
            <Switch
              checked={onlyOnline}
              onChange={(e) => {
                setOnlyOnline(e.target.checked);
                setPage(1);
              }}
            />
          }
          label="فقط کسانی که همین الان آنلاین‌اند"
        />
      </Stack>

      {/* جدول جلسات حضور (یا حالت بارگذاری/خالی) و صفحه‌بندی */}
      {sessions === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : sessions.length === 0 ? (
        <Alert severity="info">هیچ رکوردی پیدا نشد.</Alert>
      ) : (
        <>
          <TableContainer sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>پرسنل</TableCell>
                  <TableCell>وضعیت</TableCell>
                  <TableCell>{kind === "app" ? "دستگاه" : "سایت"}</TableCell>
                  <TableCell>شروع</TableCell>
                  <TableCell>پایان</TableCell>
                  <TableCell>مدت‌زمان</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {sessions.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell>
                      <Typography variant="body2">{s.employee_name}</Typography>
                      <Typography variant="caption" color="text.secondary" sx={monoFontSx}>
                        {s.personnel_code}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {s.is_online_now ? (
                        <Chip size="small" color="success" label="الان آنلاین" />
                      ) : (
                        <Chip size="small" variant="outlined" label="آفلاین شده" />
                      )}
                    </TableCell>
                    <TableCell>{(kind === "app" ? s.client : s.matched_site_name) || "—"}</TableCell>
                    <TableCell sx={monoFontSx}>{new Date(s.connected_at).toLocaleString("fa-IR")}</TableCell>
                    <TableCell sx={monoFontSx}>
                      {s.disconnected_at ? new Date(s.disconnected_at).toLocaleString("fa-IR") : "—"}
                    </TableCell>
                    <TableCell sx={monoFontSx}>
                      {s.disconnected_at
                        ? formatDuration(s.duration_seconds)
                        : `${formatDuration(Math.max(0, Math.round((Date.now() - new Date(s.connected_at).getTime()) / 1000)))} تا الان`}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {total > PAGE_SIZE && (
            <Stack alignItems="center" sx={{ mt: 3 }}>
              <Pagination
                count={Math.ceil(total / PAGE_SIZE)}
                page={page}
                onChange={(_, value) => setPage(value)}
                color="primary"
              />
            </Stack>
          )}
        </>
      )}

      {/* توضیح نحوه کار مانیتورینگ حضور و ارتباط آن با GPS */}
      <Box sx={{ mt: 4, p: 2.5, border: "1px dashed", borderColor: "divider", borderRadius: 2 }}>
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
          دقیقاً چطور کار می‌کند؟ و چه ارتباطی با GPS دارد؟
        </Typography>
        <Typography variant="body2" color="text.secondary" component="div">
          <ul style={{ margin: 0, paddingInlineStart: 20 }}>
            <li>وقتی هر پرسنلی پرتال را باز می‌کند، یک اتصال زنده (WebSocket) به سرور برقرار می‌شود — دقیقاً مثل نشانگر آنلاین یک سیستم چت — و یک ردیف «آنلاین در اپ» باز می‌شود؛ این نوع به GPS نیازی ندارد</li>
            <li>هر ۴۵ ثانیه یک پیام «هنوز باز است» فرستاده می‌شود؛ برای پرسنلی که مجوز ثبت تردد GPS دارند، همراه موقعیت GPS</li>
            <li>سرور فاصله را تا نزدیک‌ترین کارخانه (طبق تنظیمات GPS همان سایت) حساب می‌کند</li>
            <li><strong>فقط اگر داخل محدوده مجاز باشد</strong>، یک ردیف «آنلاین» ثبت/ادامه داده می‌شود؛ به‌محض خروج از محدوده، همان ردیف با زمان دقیق بسته می‌شود — هیچ لاگی برای زمان بیرون از محدوده ثبت نمی‌شود</li>
            <li>لحظه‌ای که اپ بسته شود، اینترنت قطع شود، یا شبکه بی‌صدا از کار بیفتد، سرور خودش این را تشخیص می‌دهد و همان لحظه را «پایان» ثبت می‌کند</li>
            <li>اگر سرور ری‌استارت شود، ردیف‌های باز با زمان آخرین پیام دریافتی بسته می‌شوند (حداکثر چند دقیقه بعد) و دیگر به‌اشتباه «الان آنلاین» نمی‌مانند</li>
            <li>روی گوشی، مرورگر وقتی اپ به پس‌زمینه برود یا صفحه خاموش شود معمولاً اتصال را قطع می‌کند؛ پس این گزارش «باز بودن اپ» را نشان می‌دهد، نه حضور واقعی سر کار</li>
          </ul>
        </Typography>
      </Box>
    </Box>
  );
}
