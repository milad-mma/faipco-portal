import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Box,
  Card,
  useMediaQuery,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import NotificationsActiveOutlinedIcon from "@mui/icons-material/NotificationsActiveOutlined";
import { fetchNoticeReaders, resendNoticePush } from "../api/notices";
import Status from "./NotificationStatus";
import { apiClient } from "../api/client";
import { monoFontSx } from "../theme";

function personName(person) {
  return [person.first_name, person.last_name].filter(Boolean).join(" ") || person.username || String(person.user_id);
}

const formatDate = value => value ? new Date(value).toLocaleString("fa-IR") : "—";

function DeliveryCard({ row }) {
  const fields = [
    ["اشتراک دستگاه", row.subscription_id ?? "—"],
    ["زمان ثبت", formatDate(row.created_at)],
    ["تعداد تلاش‌ها", row.attempts ?? "—"],
    ["زمان پذیرش", formatDate(row.accepted_at)],
    ["رسید دستگاه", formatDate(row.received_at)],
    ["کلیک روی اعلان", formatDate(row.opened_at)],
  ];
  if (row.status === "pending") fields.push(["تلاش بعدی", formatDate(row.next_attempt_at)]);

  return (
    <Card component="article" variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={1.5} alignItems="flex-start">
        <Typography component="h3" variant="subtitle1" fontWeight={700}>
          {row.initial ? "انتشار اولیه" : "ارسال مجدد"} · شمارهٔ {row.job_id}
        </Typography>
        {row.status ? <Status value={row.status} /> : <Typography variant="body2">سابقهٔ دستگاه ثبت نشده</Typography>}
        <Box component="dl" sx={{ width: "100%", m: 0 }}>
          {fields.map(([label, value]) => (
            <Box key={label} sx={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between",
              columnGap: 1.5, py: 0.5, overflowWrap: "anywhere" }}>
              <Typography component="dt" variant="body2" color="text.secondary">{label}</Typography>
              <Typography component="dd" variant="body2" sx={{ m: 0 }}><bdi>{value}</bdi></Typography>
            </Box>
          ))}
        </Box>
      </Stack>
    </Card>
  );
}

function RecipientReport({ noticeId, person, onClose }) {
  const mobile = useMediaQuery(theme => theme.breakpoints.down("md"));
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    apiClient.get(`/notices/${noticeId}/recipients/${person.user_id}/deliveries`, { signal: controller.signal })
      .then(({ data }) => setRows(data))
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [noticeId, person.user_id]);

  return <Dialog open onClose={onClose} fullWidth maxWidth="md" fullScreen={mobile}>
    <DialogTitle sx={{ overflowWrap: "anywhere" }}>گزارش اعلان این اطلاعیه برای {personName(person)}</DialogTitle>
    <DialogContent dividers sx={{ px: { xs: 1.5, sm: 3 } }}>
      {error ? <Alert severity="error">دریافت گزارش اعلان ناموفق بود.</Alert>
        : !rows ? <LinearProgress />
        : !rows.length ? <Typography>برای این فرد در این اطلاعیه سابقهٔ ارسالی ثبت نشده است.</Typography>
        : mobile ? <Stack spacing={1.5}>
          {rows.map(row => <DeliveryCard key={row.delivery_id ?? `job-${row.job_id}`} row={row} />)}
        </Stack>
        : <TableContainer><Table size="small">
          <TableHead><TableRow>{["ارسال", "زمان ثبت", "اشتراک دستگاه", "وضعیت", "تلاش‌ها", "زمان پذیرش", "رسید دستگاه", "کلیک روی اعلان", "تلاش بعدی"].map(label =>
            <TableCell key={label}>{label}</TableCell>)}</TableRow></TableHead>
          <TableBody>{rows.map(row => <TableRow key={row.delivery_id || `job-${row.job_id}`}>
            <TableCell>{row.initial ? "انتشار اولیه" : "ارسال مجدد"} (#{row.job_id})</TableCell>
            <TableCell>{formatDate(row.created_at)}</TableCell>
            <TableCell>{row.subscription_id ?? "—"}</TableCell>
            <TableCell>{row.status ? <Status value={row.status} /> : "سابقهٔ دستگاه ثبت نشده"}</TableCell>
            <TableCell>{row.attempts ?? "—"}</TableCell>
            <TableCell>{formatDate(row.accepted_at)}</TableCell>
            <TableCell>{formatDate(row.received_at)}</TableCell>
            <TableCell>{formatDate(row.opened_at)}</TableCell>
            <TableCell>{row.status === "pending" ? formatDate(row.next_attempt_at) : "—"}</TableCell>
          </TableRow>)}</TableBody>
        </Table></TableContainer>}
    </DialogContent>
    <DialogActions sx={{ pb: "max(8px, env(safe-area-inset-bottom))" }}><Button fullWidth={mobile} onClick={onClose}>بازگشت به فهرست افراد</Button></DialogActions>
  </Dialog>;
}

/**
 * دیالوگ فهرست کسانی که یک اطلاعیه را خوانده‌اند (نام، کد پرسنلی، زمان مشاهده).
 * ورودی: noticeId (شناسه‌ی اطلاعیه؛ مقدار خالی = دیالوگ بسته) و onClose.
 * دکمه‌ی «ارسال مجدد اعلان» هم دارد که Push را فقط برای کسانی که هنوز نخوانده‌اند دوباره می‌فرستد.
 */
export default function NoticeReadersDialog({ noticeId, unread, onClose }) {
  const [readers, setReaders] = useState(null);
  const [person, setPerson] = useState(null);
  const [isResending, setIsResending] = useState(false);  // در حال ارسال مجدد اعلان
  const [resendResult, setResendResult] = useState(null); // { success, message } | null
  const [loadError, setLoadError] = useState("");  // خطای دریافت فهرست (مثلاً 403)؛ جدا از «فهرست خالی» نمایش داده می‌شود

  // با باز شدن دیالوگ برای یک اطلاعیه، وضعیت قبلی پاک و فهرست خوانندگان دریافت می‌شود
  useEffect(() => {
    if (noticeId) {
      let active = true;
      setReaders(null);
      setResendResult(null);
      setLoadError("");
      // خطای سرور (مثلاً 403 برای کاربر بدون مجوز مشاهده) در loadError ذخیره می‌شود تا با
      // «هنوز کسی نخوانده» اشتباه گرفته نشود.
      fetchNoticeReaders(noticeId, unread)
        .then(data => { if (active) setReaders(data); })
        .catch((err) => active && setLoadError(err.response?.data?.detail || "دریافت اطلاعات با خطا مواجه شد."));
      return () => { active = false; };
    }
  }, [noticeId, unread]);

  // پس از تأیید کاربر، اعلان را برای خوانندگان‌نشده دوباره می‌فرستد و نتیجه را نمایش می‌دهد
  async function handleResendClick() {
    const confirmed = window.confirm(
      "این اعلان فقط برای کسانی که هنوز این اطلاعیه را نخوانده‌اند دوباره ارسال می‌شود — کسانی که قبلاً دیده‌اند، اعلان جدیدی دریافت نمی‌کنند. ادامه می‌دهید؟"
    );
    if (!confirmed) return;

    setResendResult(null);
    setIsResending(true);
    try {
      const { sent_count } = await resendNoticePush(noticeId);
      setResendResult({
        success: true,
        message:
          sent_count > 0
            ? `ارسال مجدد اعلان برای ${sent_count} نفر در صف ثبت شد.`
            : "همه مخاطبان این اطلاعیه را قبلاً دیده‌اند — چیزی برای ارسال مجدد نبود.",
      });
    } catch (err) {
      setResendResult({ success: false, message: err.response?.data?.detail || "ارسال مجدد اعلان با خطا مواجه شد." });
    } finally {
      setIsResending(false);
    }
  }

  return (
    <Dialog open={Boolean(noticeId)} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{unread ? "چه کسانی این اطلاعیه را ندیده‌اند" : "چه کسانی این اطلاعیه را دیده‌اند"}</DialogTitle>
      <DialogContent>
        {/* محتوا: خطا، پیام خالی بودن، یا جدول خوانندگان */}
        {loadError ? (
          <Alert severity="error">{loadError}</Alert>
        ) : !readers ? <LinearProgress /> : readers.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
            {unread ? "هیچ مخاطب ندیده‌ای در این فهرست نیست." : "هنوز کسی این اطلاعیه را باز نکرده است."}
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>نام</TableCell>
                  <TableCell>کد پرسنلی</TableCell>
                  {!unread && <TableCell>زمان مشاهده</TableCell>}
                </TableRow>
              </TableHead>
              <TableBody>
                {readers.map((r) => (
                  <TableRow key={r.user_id}>
                    <TableCell>
                      <Button size="small" onClick={() => setPerson(r)}>{personName(r)}</Button>
                    </TableCell>
                    <TableCell sx={monoFontSx}>{r.personnel_code || "—"}</TableCell>
                    {!unread && <TableCell sx={monoFontSx}>{new Date(r.read_at).toLocaleString("fa-IR")}</TableCell>}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DialogContent>
      <DialogActions sx={{ p: 2.5, flexDirection: "column", alignItems: "stretch", gap: 1 }}>
        {/* نتیجه‌ی ارسال مجدد و دکمه‌های پایین دیالوگ */}
        {resendResult && (
          <Alert severity={resendResult.success ? "success" : "error"}>{resendResult.message}</Alert>
        )}
        <Stack direction="row" spacing={1}>
          <Button
            startIcon={<NotificationsActiveOutlinedIcon />}
            onClick={handleResendClick}
            disabled={isResending}
          >
            {isResending ? "در حال ارسال..." : "ارسال مجدد اعلان"}
          </Button>
          <Button onClick={onClose}>بستن</Button>
        </Stack>
      </DialogActions>
      {person && <RecipientReport noticeId={noticeId} person={person} onClose={() => setPerson(null)} />}
    </Dialog>
  );
}
