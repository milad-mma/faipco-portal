import { useEffect, useState } from "react";
import {
  Alert, Box, Button, Chip, Dialog, DialogActions, DialogContent, DialogTitle,
  LinearProgress, MenuItem, Paper, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { apiClient } from "../api/client";

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
const empty = {};
function Pages({ offset, move, more }) {
  return <Stack direction="row" spacing={2} alignItems="center" justifyContent="center">
    <Button disabled={!offset} onClick={() => move(offset - 30)}>قبلی</Button>
    <Typography>صفحهٔ {(1 + offset / 30).toLocaleString("fa-IR")}</Typography>
    <Button disabled={!more} onClick={() => move(offset + 30)}>بعدی</Button>
  </Stack>;
}
function Status({ value }) {
  return <Chip size="small" label={states[value] || value}
    color={({ accepted: "success", sent: "success", failed: "error", partial: "warning" })[value] || "default"} />;
}
function Detail({ event, close }) {
  const [offset, move] = useState(0);
  const [refresh, reload] = useState(0);
  const { data, error } = useReport(`/notification-tracking/${event.source}/${event.id}`, empty, offset, refresh);
  return <Dialog open onClose={close} fullWidth maxWidth="md">
    <DialogTitle>جزئیات ارسال شمارهٔ {event.id}</DialogTitle>
    <DialogContent dividers>
      <Stack spacing={2}>
        <Typography dir="ltr" sx={{ overflowWrap: "anywhere" }}>{event.key}</Typography>
        {error && <Alert severity="error">دریافت جزئیات ناموفق بود.</Alert>}
        {!error && !data && <LinearProgress />}
        {data && <>
          {data.target_count != null && <Typography>تعداد مخاطبان: {data.target_count} · بدون دستگاه: {data.no_device_count}</Typography>}
          {data.single_user_id != null && <Typography>شناسهٔ کاربر مقصد: {data.single_user_id}</Typography>}
          {data.employee_id != null && <Typography>شناسهٔ پرسنل: {data.employee_id}</Typography>}
          {data.attempts != null && <Typography>تلاش‌های ثبت‌شده برای رویداد: {data.attempts}</Typography>}
          {data.deadline_at && <Typography>پایان اعتبار: {date(data.deadline_at)}</Typography>}
          {data.last_error && <Typography>آخرین نتیجه: {reasons[data.last_error] || data.last_error}</Typography>}
          {data.items.length ? <TableContainer><Table size="small">
            <TableHead><TableRow>{["اشتراک", "شناسه کاربر", "وضعیت دستگاه", "تلاش", "زمان پذیرش", "تلاش بعدی", "علت"].map(t => <TableCell key={t}>{t}</TableCell>)}</TableRow></TableHead>
            <TableBody>{data.items.map(d => <TableRow key={d.subscription_id}>
              <TableCell>{d.subscription_id}</TableCell><TableCell>{d.user_id ?? "—"}</TableCell>
              <TableCell><Status value={d.status} /></TableCell><TableCell>{d.attempts ?? "—"}</TableCell>
              <TableCell>{date(d.accepted_at)}</TableCell><TableCell>{d.status === "pending" ? date(d.next_attempt_at) : "—"}</TableCell>
              <TableCell>{reasons[d.last_error] || d.last_error || "—"}</TableCell></TableRow>)}</TableBody>
          </Table></TableContainer> : <Typography>برای این رویداد سابقهٔ دستگاه ثبت نشده است.</Typography>}
          {(offset > 0 || data.has_more) && <Pages offset={offset} more={data.has_more} move={move} />}
        </>}
      </Stack>
    </DialogContent><DialogActions><Button onClick={() => reload(n => n + 1)}>تازه‌سازی</Button><Button onClick={close}>بستن</Button></DialogActions>
  </Dialog>;
}
export default function NotificationTrackingPage() {
  const [filters, setFilters] = useState({ q: "", source: "", state: "" });
  const [query, setQuery] = useState(empty);
  const [offset, move] = useState(0);
  const [refresh, reload] = useState(0);
  const [event, select] = useState(null);
  const { data, error } = useReport("/notification-tracking", query, offset, refresh);
  const field = name => ({ value: filters[name], onChange: e => setFilters({ ...filters, [name]: e.target.value }) });
  return <Stack spacing={2}>
    <Typography variant="h5" component="h1">ردیابی اعلان ها</Typography>
    <Typography color="text.secondary">زمان پذیرش نشان می‌دهد سرویس پوش پیام را پذیرفته است. نمایش روی گوشی یا خواندن پیام جداگانه تأیید نمی‌شود.</Typography>
    <Box component="form" onSubmit={e => { e.preventDefault(); move(0); setQuery({ ...filters, source: filters.source || undefined }); }}
      sx={{ display: "flex", gap: 1.5, flexWrap: "wrap", alignItems: "center" }}>
      <TextField size="small" label="شناسه ارسال یا کلید رویداد" inputProps={{ maxLength: 100 }} {...field("q")} />
      <TextField select size="small" label="صف" {...field("source")} sx={{ minWidth: 145 }}>
        <MenuItem value="">همه</MenuItem>{Object.entries(sources).map(([k,v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}</TextField>
      <TextField select size="small" label="وضعیت ارسال" {...field("state")} sx={{ minWidth: 150 }}>
        <MenuItem value="">همه</MenuItem>{Object.entries(states).filter(([k]) => !["stale","ineligible"].includes(k)).map(([k,v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}</TextField>
      <Button type="submit" variant="contained">جست‌وجو</Button><Button onClick={() => reload(n => n + 1)}>تازه‌سازی</Button>
    </Box>
    {error && <Alert severity="error">دریافت گزارش ناموفق بود. دوباره تلاش کنید.</Alert>}
    {!data && !error && <LinearProgress />}
    {data && <Paper variant="outlined"><TableContainer><Table>
      <TableHead><TableRow>{["شناسه", "صف و کلید رویداد", "زمان ثبت", "وضعیت", "تلاش بعدی", ""].map(t => <TableCell key={t}>{t}</TableCell>)}</TableRow></TableHead>
      <TableBody>{data.items.map(row => <TableRow key={row.source + row.id}>
        <TableCell>{row.id}</TableCell><TableCell>{sources[row.source]}<Typography variant="body2" dir="ltr" sx={{ overflowWrap: "anywhere" }}>{row.key}</Typography></TableCell>
        <TableCell>{date(row.created_at)}</TableCell><TableCell><Status value={row.status} /></TableCell>
        <TableCell>{row.status === "pending" ? date(row.next_attempt_at) : "—"}</TableCell>
        <TableCell><Button onClick={() => select(row)}>جزئیات</Button></TableCell>
      </TableRow>)}</TableBody></Table></TableContainer>
      {!data.items.length && <Typography sx={{ p: 2 }}>اعلانی با این مشخصات پیدا نشد.</Typography>}
      <Pages offset={offset} move={move} more={data.has_more} />
    </Paper>}
    {event && <Detail event={event} close={() => select(null)} />}
  </Stack>;
}
