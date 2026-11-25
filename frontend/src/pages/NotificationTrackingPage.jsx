import { useEffect, useMemo, useState } from "react";
import {
  useMediaQuery, Alert, Card, Grid, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle,
  LinearProgress, MenuItem, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { apiClient } from "../api/client";

import SearchField from "../components/SearchField";
import useDebounced from "../hooks/useDebounced";

const states = {
  pending: "در انتظار ارسال", accepted: "پذیرفته‌شده توسط سرویس پوش",
  sent: "ارسال‌شده", partial: "ارسال ناقص", failed: "ناموفق", skipped: "ردشده از صف",
  expired: "منقضی", cancelled: "لغوشده", no_devices: "بدون دستگاه",
  no_targets: "بدون گیرنده", not_accepted: "پذیرفته نشد", stale: "اشتراک منقضی",
  ineligible: "فاقد شرایط ارسال",
};
const sources = { dispatch: "صف عمومی پرتال", office: "اتوماسیون اداری" };
const date = value => value ? new Date(value).toLocaleString("fa-IR") : "—";
const reasons = {
  awaiting_eligible_devices: "در انتظار دستگاه واجد شرایط",
  retry_window_elapsed: "مهلت تلاش مجدد پایان یافت",
  network_or_transport_error: "خطای ارتباط با سرویس پوش",
  see_server_logs: "جزئیات بیشتر در گزارش فنی سرور",
};
function messageReference({ message }) {
  const { module, event_type, record_id, event_id } = message;
  const record = record_id ? ` · شمارهٔ ${record_id}` : " · مرجع ثبت نشده";
  const event = event_id && /^\d{1,12}$/.test(event_id) ? ` · ${module === "بازخورد" && event_type === "پاسخ" ? "پاسخ" : "رویداد"} ${event_id}` : "";
  return `${module} · ${event_type}${record}${event}`;
}
function Recipient({ row }) {
  return <Typography variant="body2">
    {row.user_id != null ? `شناسه کاربر: ${row.user_id}` : row.multiple_users ? "چند گیرنده" : "شناسه کاربر: —"}
    {row.personnel_code && ` · کد پرسنلی: ${row.personnel_code}`}
  </Typography>;
}
function useReport(path, query, offset, refresh) {
  const [result, setResult] = useState({});
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setResult({});
    apiClient.get(path, { params: { ...query, offset }, signal: controller.signal })
      .then(({ data }) => { if (active) setResult({ data }); })
      .catch(() => { if (active) setResult({ error: true }); });
    return () => { active = false; controller.abort(); };
  }, [path, query, offset, refresh]);
  return result;
}

function Pages({ offset, move, more }) {
  return <Stack direction="row" spacing={2} alignItems="center" justifyContent="center">
    <Button disabled={!offset} onClick={() => move(offset - 30)}>قبلی</Button>
    <Typography>صفحهٔ {(1 + offset / 30).toLocaleString("fa-IR")}</Typography>
    <Button disabled={!more} onClick={() => move(offset + 30)}>بعدی</Button>
  </Stack>;
}
function Status({ value }) {
  const accepted = ["sent", "accepted"].includes(value);
  return <Chip size="small" variant="outlined"
    sx={{ height: "auto", maxWidth: "100%", "& .MuiChip-label": { whiteSpace: "normal", py: 0.4 } }}
    label={accepted ? "سرویس پذیرفت؛ تحویل به گوشی تأیید نشده" : states[value] || value}
    color={({ accepted: "info", sent: "info", failed: "error", partial: "warning" })[value] || "default"} />;
}
function Detail({ event, close, code, mobile }) {
  const params = useMemo(() => ({ personnel_code: code || undefined }), [code]);
  const [offset, move] = useState(0);
  const [refresh, reload] = useState(0);
  const { data, error } = useReport(`/notification-tracking/${event.source}/${event.id}`, params, offset, refresh);
  return <Dialog open fullScreen={mobile} onClose={close} fullWidth maxWidth="md">
    <DialogTitle>جزئیات ارسال شمارهٔ {event.id}</DialogTitle>
    <DialogContent dividers>
      <Stack spacing={2}>
        <Typography fontWeight={700}>{messageReference(event)}</Typography>
        <Typography variant="caption">وضعیت کل ارسال</Typography><Status value={event.status} />
        <Typography variant="caption">کلید فنی رویداد</Typography>
        <Typography dir="ltr" sx={{ overflowWrap: "anywhere" }}>{event.key}</Typography>
        {error && <Alert severity="error">دریافت جزئیات ناموفق بود.</Alert>}
        {!error && !data && <LinearProgress />}
        {data && <>
          {data.target_count != null && <Typography>تعداد مخاطبان: {data.target_count} · بدون دستگاه: {data.no_device_count}</Typography>}
          {data.single_user_id != null && <Typography>شناسهٔ کاربر مقصد: {data.single_user_id} · کد پرسنلی: {data.personnel_code ?? "—"}</Typography>}
          {data.single_user_id == null && data.employee_id != null && <Typography>شناسهٔ پرسنل: {data.employee_id} · کد پرسنلی: {data.personnel_code ?? "—"}</Typography>}
          {code && data.single_user_id == null && data.matched_user_ids?.map(uid =>
            <Typography key={uid}>شناسه کاربر: {uid} · کد پرسنلی: {code}</Typography>)}
          {data.attempts != null && <Typography>تلاش‌های ثبت‌شده برای رویداد: {data.attempts}</Typography>}
          {data.deadline_at && <Typography>پایان اعتبار: {date(data.deadline_at)}</Typography>}
          {data.last_error && <Typography>آخرین نتیجه: {reasons[data.last_error] || data.last_error}</Typography>}
          {data.items.length ? mobile ? data.items.map(d =>
            <Card variant="outlined" sx={{ p: 1.5 }} key={d.id ?? d.subscription_id}>
              <Stack spacing={1} alignItems="flex-start">
                <Typography fontWeight={700}>اشتراک شمارهٔ {d.subscription_id}</Typography>
                <Recipient row={d} /><Status value={d.status} />
                {d.attempts != null && <Typography variant="body2">تعداد تلاش: {d.attempts}</Typography>}
                {d.accepted_at && <Typography variant="body2">زمان پذیرش: {date(d.accepted_at)}</Typography>}
                {d.status === "pending" && d.next_attempt_at && <Typography variant="body2">تلاش بعدی: {date(d.next_attempt_at)}</Typography>}
                {d.last_error && <Typography variant="body2">علت: {reasons[d.last_error] || d.last_error}</Typography>}
              </Stack>
            </Card>) : <TableContainer><Table size="small">
            <TableHead><TableRow>{["اشتراک", "شناسه کاربر", "کد پرسنلی", "وضعیت دستگاه", "تلاش", "زمان پذیرش", "تلاش بعدی", "علت"].map(t => <TableCell key={t}>{t}</TableCell>)}</TableRow></TableHead>
            <TableBody>{data.items.map(d => <TableRow key={d.id ?? d.subscription_id}>
              <TableCell>{d.subscription_id}</TableCell><TableCell>{d.user_id ?? "—"}</TableCell><TableCell>{d.personnel_code ?? "—"}</TableCell>
              <TableCell><Status value={d.status} /></TableCell><TableCell>{d.attempts ?? "—"}</TableCell>
              <TableCell>{date(d.accepted_at)}</TableCell><TableCell>{d.status === "pending" ? date(d.next_attempt_at) : "—"}</TableCell>
              <TableCell>{reasons[d.last_error] || d.last_error || "—"}</TableCell></TableRow>)}</TableBody>
          </Table></TableContainer> : <Typography>در این گزارش سابقهٔ ارسال به دستگاه پیدا نشد.</Typography>}
          {(offset > 0 || data.has_more) && <Pages offset={offset} more={data.has_more} move={move} />}
        </>}
      </Stack>
    </DialogContent><DialogActions><Button onClick={() => reload(n => n + 1)}>تازه‌سازی</Button><Button onClick={close}>بستن</Button></DialogActions>
  </Dialog>;
}
export default function NotificationTrackingPage() {
  const mobile = useMediaQuery(theme => theme.breakpoints.down("md"));
  const [filters, setFilters] = useState({ code: "", q: "", source: "", state: "" });
  const q = useDebounced(filters.q.trim(), 300);
  const code = useDebounced(filters.code.trim(), 300);
  const query = useMemo(() => ({ q, personnel_code: code || undefined, source: filters.source || undefined, state: filters.state }),
    [code, q, filters.source, filters.state]);
  const [offset, move] = useState(0);
  const [refresh, reload] = useState(0);
  const [event, select] = useState(null);
  const { data, error } = useReport("/notification-tracking", query, offset, refresh);
  const field = name => ({ value: filters[name], onChange: e => { move(0); setFilters({ ...filters, [name]: e.target.value }); } });
  return <Stack spacing={2}>
    <Typography variant="h5" component="h1">ردیابی اعلان ها</Typography>
    <Typography color="text.secondary">زمان پذیرش نشان می‌دهد سرویس پوش پیام را پذیرفته است. نمایش روی گوشی یا خواندن پیام جداگانه تأیید نمی‌شود.</Typography>
    <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <Grid container spacing={1.5} alignItems="center">
        <Grid item xs={12} sm={6} md={3}>
          <SearchField label="کد پرسنلی" placeholder="کد کامل پرسنلی…"
            value={filters.code} inputProps={{ maxLength: 64 }}
            onChange={code => { move(0); setFilters({ ...filters, code }); }} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <SearchField label="جست‌وجو" placeholder="شناسه ارسال یا کلید رویداد…"
            value={filters.q} inputProps={{ maxLength: 100 }}
            onChange={q => { move(0); setFilters({ ...filters, q }); }} />
        </Grid>
        <Grid item xs={6} sm={3} md={2}>
          <TextField fullWidth select size="small" SelectProps={{ displayEmpty: true }} InputLabelProps={{ shrink: true }} label="صف" {...field("source")}>
            <MenuItem value="">همه</MenuItem>{Object.entries(sources).map(([k,v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}</TextField>
        </Grid>
        <Grid item xs={6} sm={3} md={2}>
          <TextField fullWidth select size="small" SelectProps={{ displayEmpty: true }} InputLabelProps={{ shrink: true }} label="وضعیت ارسال" {...field("state")}>
            <MenuItem value="">همه</MenuItem>{Object.entries(states).filter(([k]) => !["stale","ineligible"].includes(k)).map(([k,v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}</TextField>
        </Grid>
        <Grid item><Button onClick={() => reload(n => n + 1)}>تازه‌سازی</Button></Grid>
      </Grid>
    </Card>
    {error && <Alert severity="error">دریافت گزارش ناموفق بود. دوباره تلاش کنید.</Alert>}
    {!data && !error && <LinearProgress />}
    {data && <Card variant="outlined" sx={{ borderRadius: 2 }}>{mobile ? <Stack spacing={1} sx={{ p: 1 }}>
        {data.items.map(row => <Card variant="outlined" key={row.source + row.id} sx={{ p: 1.5 }}>
          <Stack spacing={1} alignItems="flex-start" sx={{ overflowWrap: "anywhere" }}>
            <Typography variant="caption">{sources[row.source]} · ارسال شمارهٔ {row.id} · {date(row.created_at)}</Typography>
            <Typography fontWeight={700}>{messageReference(row)}</Typography>
            <Recipient row={row} /><Typography variant="caption">وضعیت کل ارسال</Typography><Status value={row.status} />
            {row.status === "pending" && <Typography variant="body2">تلاش بعدی: {date(row.next_attempt_at)}</Typography>}
            <Button onClick={() => select(row)}>جزئیات</Button>
          </Stack>
        </Card>)}
      </Stack> : <TableContainer><Table size="small">
      <TableHead><TableRow>{["شناسه", "پیام مرتبط", "گیرنده", "زمان ثبت", "وضعیت کل ارسال", "تلاش بعدی", ""].map(t => <TableCell key={t}>{t}</TableCell>)}</TableRow></TableHead>
      <TableBody>{data.items.map(row => <TableRow hover key={row.source + row.id}>
        <TableCell>{row.id}</TableCell><TableCell sx={{ overflowWrap: "anywhere" }}>{messageReference(row)}</TableCell><TableCell><Recipient row={row} /></TableCell>
        <TableCell>{date(row.created_at)}</TableCell><TableCell><Status value={row.status} /></TableCell>
        <TableCell>{row.status === "pending" ? date(row.next_attempt_at) : "—"}</TableCell>
        <TableCell><Button onClick={() => select(row)}>جزئیات</Button></TableCell>
      </TableRow>)}</TableBody></Table></TableContainer>}
      {!data.items.length && <Typography sx={{ p: 2 }}>اعلانی با این مشخصات پیدا نشد.</Typography>}
      <Pages offset={offset} move={move} more={data.has_more} />
    </Card>}
    {event && <Detail event={event} mobile={mobile} code={code} close={() => select(null)} />}
  </Stack>;
}
