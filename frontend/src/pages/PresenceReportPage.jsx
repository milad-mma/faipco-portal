import { useEffect, useState } from "react";
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
import { monoFontSx } from "../theme";

const PAGE_SIZE = 50;

function formatDuration(seconds) {
  if (seconds == null) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h} ساعت ${m} دقیقه`;
  if (m > 0) return `${m} دقیقه ${s} ثانیه`;
  return `${s} ثانیه`;
}

export default function PresenceReportPage() {
  const [sessions, setSessions] = useState(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [onlyOnline, setOnlyOnline] = useState(false);

  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [employeeSearch, setEmployeeSearch] = useState("");

  useEffect(() => {
    setSessions(null);
    fetchPresenceSessions({
      page,
      pageSize: PAGE_SIZE,
      employeeId: selectedEmployee?.id,
      onlyOnline,
    }).then((data) => {
      setSessions(data.items);
      setTotal(data.total);
    });
  }, [page, selectedEmployee, onlyOnline]);

  useEffect(() => {
    fetchEmployees({ search: employeeSearch, pageSize: 20 }).then((data) => setEmployeeOptions(data.items || []));
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
      <Alert severity="info" sx={{ mb: 3 }}>
        هر ردیف یک بازه زمانی واقعی است که پرسنل هم اپ را باز داشته، هم داخل محدوده مجاز کارخانه بوده
        — نه یک لحظه تکی. اگر خارج از محدوده باشد، اصلاً هیچ ردیفی ثبت نمی‌شود.
      </Alert>

      <Stack direction="row" spacing={2} sx={{ mb: 3 }} flexWrap="wrap" rowGap={2} alignItems="center">
        <Autocomplete
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
                  <TableCell>سایت</TableCell>
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
                    <TableCell>{s.matched_site_name || "—"}</TableCell>
                    <TableCell sx={monoFontSx}>{new Date(s.connected_at).toLocaleString("fa-IR")}</TableCell>
                    <TableCell sx={monoFontSx}>
                      {s.disconnected_at ? new Date(s.disconnected_at).toLocaleString("fa-IR") : "—"}
                    </TableCell>
                    <TableCell sx={monoFontSx}>{formatDuration(s.duration_seconds)}</TableCell>
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

      <Box sx={{ mt: 4, p: 2.5, border: "1px dashed", borderColor: "divider", borderRadius: 2 }}>
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
          دقیقاً چطور کار می‌کند؟ و چه ارتباطی با GPS دارد؟
        </Typography>
        <Typography variant="body2" color="text.secondary" component="div">
          <ul style={{ margin: 0, paddingInlineStart: 20 }}>
            <li>وقتی پرسنل اپ را باز می‌کند، یک اتصال زنده (WebSocket) به سرور برقرار می‌شود — دقیقاً مثل نشانگر آنلاین یک سیستم چت</li>
            <li>هر ۴۵ ثانیه، مرورگر موقعیت GPS فعلی را از طریق همین اتصال به سرور می‌فرستد</li>
            <li>سرور فاصله را تا نزدیک‌ترین کارخانه (طبق تنظیمات GPS همان سایت) حساب می‌کند</li>
            <li><strong>فقط اگر داخل محدوده مجاز باشد</strong>، یک ردیف «آنلاین» ثبت/ادامه داده می‌شود؛ به‌محض خروج از محدوده، همان ردیف با زمان دقیق بسته می‌شود — هیچ لاگی برای زمان بیرون از محدوده ثبت نمی‌شود</li>
            <li>لحظه‌ای که اپ بسته شود، اینترنت قطع شود، یا شبکه بی‌صدا از کار بیفتد، سرور خودش این را تشخیص می‌دهد و همان لحظه را «پایان» ثبت می‌کند — مدت‌زمان همیشه دقیق است، نه تخمینی</li>
          </ul>
        </Typography>
      </Box>
    </Box>
  );
}
