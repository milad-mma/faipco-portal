import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ArrowForwardOutlinedIcon from "@mui/icons-material/ArrowForwardOutlined";
import { submitFeedback } from "../api/feedback";

const CATEGORY_LABELS = {
  complaint: "انتقاد",
  suggestion: "پیشنهاد",
  comment: "نظر",
};

const ANONYMITY_NOTICE_TEXT =
  "همکار گرامی، اطمینان خاطر داشته باشید که انتقادات، پیشنهادات و نظرات شما به‌صورت کاملاً محرمانه و ناشناس ثبت شده و صرفاً در اختیار مدیر این واحد قرار خواهد گرفت. بدیهی است حفظ محرمانگی و ناشناس بودن پیام‌ها، مشروط به رعایت شئونات و ادبیات مناسب در بیان نظرات است. در صورت استفاده از الفاظ رکیک، توهین‌آمیز یا ناسزا، پیام به صورت خودکار توسط سامانه بررسی شده و از حالت محرمانه و ناشناس خارج شده و هویت ارسال‌کننده قابل شناسایی خواهد بود. در این صورت، مسئولیت و عواقب ناشی از محتوای پیام بر عهده ارسال‌کننده خواهد بود.";

/**
 * صفحه ارسال انتقاد/پیشنهاد - کارت «انتقادات و پیشنهادات» در داشبورد
 * شخصی به این صفحه هدایت می‌کند (طبق درخواست صریح، دیگر دیالوگ‌باکس
 * نیست).
 *
 * عنوان و متن پیام هر دو اجباری هستند (هم در Frontend، هم در Backend -
 * FeedbackSubmitIn با min_length=1).
 *
 * طبق درخواست صریح: خودِ تیک‌زدن چک‌باکس «ارسال به‌صورت ناشناس» کافی
 * نیست - قبل از این‌که چک‌باکس واقعاً فعال شود، باید متن اطمینان‌بخشی
 * نمایش داده شود و کاربر «موافقم» را بزند؛ اگر انصراف بدهد، چک‌باکس
 * همچنان غیرفعال می‌ماند.
 */
export default function FeedbackSubmitPage() {
  const navigate = useNavigate();
  const [category, setCategory] = useState("");
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [noticeDialogOpen, setNoticeDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  function handleAnonymousCheckboxChange(e) {
    if (e.target.checked) {
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
      await submitFeedback({ category, title: title.trim(), message: message.trim(), isAnonymous });
      setSuccess(true);
      setCategory("");
      setTitle("");
      setMessage("");
      setIsAnonymous(false);
    } catch (err) {
      setError(err.response?.data?.detail || "ارسال پیام ناموفق بود.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        انتقادات و پیشنهادات
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        نظر، انتقاد یا پیشنهاد خود را با ما در میان بگذارید.
      </Typography>

      <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
        {success ? (
          <Stack spacing={2} alignItems="flex-start">
            <Alert severity="success" sx={{ width: "100%" }}>
              پیام شما با موفقیت ثبت شد. سپاس از وقتی که گذاشتید.
            </Alert>
            <Button startIcon={<ArrowForwardOutlinedIcon />} onClick={() => navigate("/")}>
              بازگشت به داشبورد
            </Button>
          </Stack>
        ) : (
          <Stack spacing={2.5}>
            <TextField
              select
              label="موضوع"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              fullWidth
              required
              disabled={isSubmitting}
            >
              {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="عنوان پیام"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              fullWidth
              required
              disabled={isSubmitting}
              inputProps={{ maxLength: 255 }}
            />
            <TextField
              label="متن پیام"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              multiline
              minRows={6}
              fullWidth
              required
              disabled={isSubmitting}
              inputProps={{ maxLength: 5000 }}
            />
            <FormControlLabel
              control={
                <Checkbox checked={isAnonymous} onChange={handleAnonymousCheckboxChange} disabled={isSubmitting} />
              }
              label="ارسال به‌صورت ناشناس"
            />
            {error && <Alert severity="error">{error}</Alert>}
            <Stack direction="row" spacing={1.5}>
              <Button
                variant="contained"
                onClick={handleSubmit}
                disabled={isSubmitting || !category || !title.trim() || !message.trim()}
                startIcon={isSubmitting ? <CircularProgress size={16} color="inherit" /> : null}
              >
                {isSubmitting ? "در حال ارسال..." : "ارسال"}
              </Button>
              <Button onClick={() => navigate("/")} disabled={isSubmitting}>
                انصراف
              </Button>
            </Stack>
          </Stack>
        )}
      </Card>

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
    </Box>
  );
}
