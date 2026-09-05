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

export default function NoticeReadersDialog({ noticeId, onClose }) {
  const [readers, setReaders] = useState([]);
  const [isResending, setIsResending] = useState(false);
  const [resendResult, setResendResult] = useState(null); // { success, message } | null
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (noticeId) {
      setReaders([]);
      setResendResult(null);
      setLoadError("");
      // ⚠️ رفع یک باگ واقعی: قبلاً بدون .catch بود — اگر Backend خطای ۴۰۳
      // می‌داد (مثلاً برای کسی با notices.site_report نه notices.view)،
      // این خطا بی‌صدا بلعیده می‌شد و readers همچنان [] (مقدار اولیه)
      // می‌ماند — دقیقاً همان چیزی که به‌اشتباه «هنوز کسی نخوانده» تعبیر
      // می‌شد، در حالی که واقعاً یعنی «اجازه مشاهده نداری».
      fetchNoticeReaders(noticeId)
        .then(setReaders)
        .catch((err) => setLoadError(err.response?.data?.detail || "دریافت اطلاعات با خطا مواجه شد."));
    }
  }, [noticeId]);

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
