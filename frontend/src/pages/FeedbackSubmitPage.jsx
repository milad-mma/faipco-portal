/**
 * صفحه ارسال انتقاد/پیشنهاد/نظر توسط پرسنل.
 * فرم شامل موضوع، عنوان و متن (همه اجباری) و گزینه ارسال ناشناس است؛
 * فعال شدن ارسال ناشناس منوط به تأیید متن اطلاع‌رسانی محرمانگی است.
 */
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
import BackLink from "../components/BackLink";
import { submitFeedback } from "../api/feedback";

const CATEGORY_LABELS = {  // برچسب فارسی دسته‌های پیام (کلید = مقدار ارسالی به سرور)
  complaint: "انتقاد",
  suggestion: "پیشنهاد",
  comment: "نظر",
};

// متن اطلاع‌رسانی شرایط محرمانگی که پیش از فعال شدن ارسال ناشناس نمایش داده می‌شود
const ANONYMITY_NOTICE_TEXT =
  "همکار گرامی، اطمینان خاطر داشته باشید که انتقادات، پیشنهادات و نظرات شما به‌صورت کاملاً محرمانه و ناشناس ثبت شده و صرفاً در اختیار مدیر این واحد قرار خواهد گرفت. بدیهی است حفظ محرمانگی و ناشناس بودن پیام‌ها، مشروط به رعایت شئونات و ادبیات مناسب در بیان نظرات است. در صورت استفاده از الفاظ رکیک، توهین‌آمیز یا ناسزا، پیام به صورت خودکار توسط سامانه بررسی شده و از حالت محرمانه و ناشناس خارج شده و هویت ارسال‌کننده قابل شناسایی خواهد بود. در این صورت، مسئولیت و عواقب ناشی از محتوای پیام بر عهده ارسال‌کننده خواهد بود.";

/**
 * کامپوننت صفحه ارسال پیام؛ کارت «انتقادات و پیشنهادات» در داشبورد شخصی به این صفحه هدایت می‌کند.
 * عنوان و متن پیام اجباری‌اند (در Backend هم FeedbackSubmitIn با min_length=1 بررسی می‌کند).
 * تیک «ارسال ناشناس» ابتدا دیالوگ متن محرمانگی را باز می‌کند و فقط با «موافقم» فعال می‌شود.
 */
export default function FeedbackSubmitPage() {
  const navigate = useNavigate();
  const [category, setCategory] = useState("");
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [noticeDialogOpen, setNoticeDialogOpen] = useState(false);  // باز بودن دیالوگ متن محرمانگی
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);  // true = پیام ثبت شد و فرم جای خود را به پیام موفقیت می‌دهد

  // تیک زدن فقط دیالوگ تأیید را باز می‌کند؛ برداشتن تیک مستقیماً حالت ناشناس را خاموش می‌کند
  function handleAnonymousCheckboxChange(e) {
    if (e.target.checked) {
      setNoticeDialogOpen(true);
    } else {
      setIsAnonymous(false);
    }
  }

  // پس از «موافقم» حالت ناشناس را فعال و دیالوگ را می‌بندد
  function handleAgreeToNotice() {
    setIsAnonymous(true);
    setNoticeDialogOpen(false);
  }

  // پیام را (با trim عنوان/متن) به سرور می‌فرستد؛ در صورت موفقیت فرم را خالی و پیام موفقیت را نمایش می‌دهد
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
      setError(err.response?.data?.detail || "ارسال پیام با خطا مواجه شد.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <BackLink to="/my-dashboard" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        انتقادات و پیشنهادات
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        نظر، انتقاد یا پیشنهاد خود را با ما در میان بگذارید.
      </Typography>

      {/* کارت فرم: پس از ارسال موفق، پیام موفقیت و دکمه بازگشت جایگزین فرم می‌شود */}
      <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
        {success ? (
          <Stack spacing={2} alignItems="flex-start">
            <Alert severity="success" sx={{ width: "100%" }}>
              پیام شما با موفقیت ثبت شد. سپاس از وقتی که گذاشتید.
            </Alert>
            <Button startIcon={<ArrowForwardOutlinedIcon />} onClick={() => navigate("/my-dashboard")}>
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
            {/* چک‌باکس ارسال ناشناس؛ تیک زدن آن ابتدا دیالوگ محرمانگی را باز می‌کند */}
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

      {/* دیالوگ متن محرمانگی با دکمه‌های «انصراف» و «موافقم» */}
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
