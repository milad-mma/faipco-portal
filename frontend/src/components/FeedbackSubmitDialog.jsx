import { useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { submitFeedback } from "../api/feedback";

const ANONYMITY_NOTICE_TEXT =
  "همکار گرامی، اطمینان خاطر داشته باشید که انتقادات، پیشنهادات و نظرات شما به‌صورت کاملاً محرمانه و ناشناس ثبت شده و صرفاً در اختیار مدیر این واحد قرار خواهد گرفت. بدیهی است حفظ محرمانگی و ناشناس بودن پیام‌ها، مشروط به رعایت شئونات و ادبیات مناسب در بیان نظرات است. در صورت استفاده از الفاظ رکیک، توهین‌آمیز یا ناسزا، پیام از حالت محرمانه و ناشناس خارج شده و هویت ارسال‌کننده قابل شناسایی خواهد بود. در این صورت، مسئولیت و عواقب ناشی از محتوای پیام بر عهده ارسال‌کننده خواهد بود.";

/**
 * دیالوگ ارسال انتقاد/پیشنهاد - کارت «انتقادات و پیشنهادات» در داشبورد
 * شخصی این را باز می‌کند.
 *
 * طبق درخواست صریح: خودِ تیک‌زدن چک‌باکس «ارسال به‌صورت ناشناس» کافی
 * نیست - قبل از این‌که چک‌باکس واقعاً فعال شود، باید متن اطمینان‌بخشی
 * (دقیقاً همان متن درخواستی) نمایش داده شود و کاربر «موافقم» را بزند؛
 * اگر انصراف بدهد، چک‌باکس همچنان غیرفعال می‌ماند.
 */
export default function FeedbackSubmitDialog({ open, onClose }) {
  const [message, setMessage] = useState("");
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [noticeDialogOpen, setNoticeDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  function handleClose() {
    if (isSubmitting) return;
    setMessage("");
    setIsAnonymous(false);
    setError("");
    setSuccess(false);
    onClose();
  }

  function handleAnonymousCheckboxChange(e) {
    if (e.target.checked) {
      // چک‌باکس هنوز فعال نمی‌شود - اول باید متن اطمینان‌بخشی تأیید شود
      setNoticeDialogOpen(true);
    } else {
      setIsAnonymous(false);
    }
  }

  function handleAgreeToNotice() {
    setIsAnonymous(true);
    setNoticeDialogOpen(false);
  }

  async function handleSubmit() {
    setError("");
    setIsSubmitting(true);
    try {
      await submitFeedback({ message: message.trim(), isAnonymous });
      setSuccess(true);
      setMessage("");
      setIsAnonymous(false);
    } catch (err) {
      setError(err.response?.data?.detail || "ارسال پیام ناموفق بود.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <Dialog open={open} onClose={handleClose} fullWidth maxWidth="sm">
        <DialogTitle>انتقادات و پیشنهادات</DialogTitle>
        <DialogContent>
          {success ? (
            <Alert severity="success" sx={{ mt: 1 }}>
              پیام شما با موفقیت ثبت شد. سپاس از وقتی که گذاشتید.
            </Alert>
          ) : (
            <Stack spacing={2} sx={{ mt: 1 }}>
              <Typography variant="body2" color="text.secondary">
                نظر، انتقاد یا پیشنهاد خود را بنویسید.
              </Typography>
              <TextField
                label="متن پیام"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                multiline
                minRows={5}
                fullWidth
                disabled={isSubmitting}
                inputProps={{ maxLength: 5000 }}
              />
              <FormControlLabel
                control={<Checkbox checked={isAnonymous} onChange={handleAnonymousCheckboxChange} disabled={isSubmitting} />}
                label="ارسال به‌صورت ناشناس"
              />
              {error && <Alert severity="error">{error}</Alert>}
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={isSubmitting}>
            {success ? "بستن" : "انصراف"}
          </Button>
          {!success && (
            <Button
              variant="contained"
              onClick={handleSubmit}
              disabled={isSubmitting || !message.trim()}
              startIcon={isSubmitting ? <CircularProgress size={16} color="inherit" /> : null}
            >
              {isSubmitting ? "در حال ارسال..." : "ارسال"}
            </Button>
          )}
        </DialogActions>
      </Dialog>

      <Dialog open={noticeDialogOpen} onClose={() => setNoticeDialogOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>ارسال ناشناس</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ whiteSpace: "pre-line", lineHeight: 2 }}>
            {ANONYMITY_NOTICE_TEXT}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNoticeDialogOpen(false)}>انصراف</Button>
          <Button variant="contained" onClick={handleAgreeToNotice}>
            موافقم
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
