import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
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
import { monoFontSx } from "../theme";

/**
 * دیالوگ فهرست کسانی که یک اطلاعیه را خوانده‌اند (نام، کد پرسنلی، زمان مشاهده).
 * ورودی: noticeId (شناسه‌ی اطلاعیه؛ مقدار خالی = دیالوگ بسته) و onClose.
 * دکمه‌ی «ارسال مجدد اعلان» هم دارد که Push را فقط برای کسانی که هنوز نخوانده‌اند دوباره می‌فرستد.
 */
export default function NoticeReadersDialog({ noticeId, onClose }) {
  const [readers, setReaders] = useState([]);
  const [isResending, setIsResending] = useState(false);  // در حال ارسال مجدد اعلان
  const [resendResult, setResendResult] = useState(null); // { success, message } | null
  const [loadError, setLoadError] = useState("");  // خطای دریافت فهرست (مثلاً 403)؛ جدا از «فهرست خالی» نمایش داده می‌شود

  // با باز شدن دیالوگ برای یک اطلاعیه، وضعیت قبلی پاک و فهرست خوانندگان دریافت می‌شود
  useEffect(() => {
    if (noticeId) {
      setReaders([]);
      setResendResult(null);
      setLoadError("");
      // خطای سرور (مثلاً 403 برای کاربر بدون مجوز مشاهده) در loadError ذخیره می‌شود تا با
      // «هنوز کسی نخوانده» اشتباه گرفته نشود.
      fetchNoticeReaders(noticeId)
        .then(setReaders)
        .catch((err) => setLoadError(err.response?.data?.detail || "دریافت اطلاعات با خطا مواجه شد."));
    }
  }, [noticeId]);

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
            ? `اعلان مجدداً برای ${sent_count} نفر ارسال شد.`
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
      <DialogTitle>چه کسانی این اطلاعیه را دیده‌اند</DialogTitle>
      <DialogContent>
        {/* محتوا: خطا، پیام خالی بودن، یا جدول خوانندگان */}
        {loadError ? (
          <Alert severity="error">{loadError}</Alert>
        ) : readers.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 2 }}>
            هنوز کسی این اطلاعیه را باز نکرده است.
          </Typography>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>نام</TableCell>
                  <TableCell>کد پرسنلی</TableCell>
                  <TableCell>زمان مشاهده</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {readers.map((r) => (
                  <TableRow key={r.user_id}>
                    <TableCell>
                      {r.first_name ? `${r.first_name} ${r.last_name}` : "—"}
                    </TableCell>
                    <TableCell sx={monoFontSx}>{r.personnel_code || "—"}</TableCell>
                    <TableCell sx={monoFontSx}>{new Date(r.read_at).toLocaleString("fa-IR")}</TableCell>
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
    </Dialog>
  );
}
