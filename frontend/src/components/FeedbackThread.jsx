/**
 * گفتگوی یک پیام «انتقادات و پیشنهادات» — مشترک بین بازبین (گزارش) و فرستنده (پیام‌های من).
 *
 * ناشناس بودن در Backend اعمال می‌شود: برای بازبین، author_name پاسخ‌های فرستنده null می‌آید و اینجا
 * «فرستنده» نمایش داده می‌شود؛ پاسخ بازبین همیشه با نام خودش. هیچ «خوانده شد»ی به بازبین نشان داده نمی‌شود.
 *
 * ورودی: replies (فهرست پاسخ‌ها)، canReply، onSend(body) → Promise، closed (گفتگو بسته است)،
 * senderNote (تذکر ناشناس بودن برای فرستنده)، emptyText.
 */
import { useState } from "react";
import { Alert, Box, Button, CircularProgress, Stack, TextField, Typography } from "@mui/material";
import SendOutlinedIcon from "@mui/icons-material/SendOutlined";

export const FEEDBACK_STATUS_LABELS = {
  new: "جدید",
  in_review: "در دست بررسی",
  answered: "پاسخ داده شد",
  closed: "بسته",
};
export const FEEDBACK_STATUS_COLORS = { new: "warning", in_review: "info", answered: "success", closed: "default" };

export default function FeedbackThread({ replies, canReply, onSend, closed, senderNote, emptyText }) {
  const [body, setBody] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");

  async function handleSend() {
    const text = body.trim();
    if (!text) return;
    setError("");
    setIsSending(true);
    try {
      await onSend(text);
      setBody("");
    } catch (err) {
      setError(err.response?.data?.detail || "ارسال پاسخ با خطا مواجه شد.");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <Stack spacing={1.5}>
      {replies.length === 0 ? (
        <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ py: 1 }}>
          {emptyText || "هنوز پاسخی ثبت نشده است."}
        </Typography>
      ) : (
        <Stack spacing={1}>
          {replies.map((r) => (
            <Box
              key={r.id}
              sx={{
                alignSelf: r.is_mine ? "flex-start" : "flex-end",
                maxWidth: "88%",
                px: 1.5,
                py: 1,
                borderRadius: 2,
                bgcolor: r.is_mine ? "primary.main" : "action.hover",
                color: r.is_mine ? "primary.contrastText" : "text.primary",
              }}
            >
              <Stack direction="row" justifyContent="space-between" spacing={1.5} sx={{ mb: 0.25 }}>
                <Typography variant="caption" fontWeight={700}>
                  {r.is_mine ? "شما" : r.author_name || (r.is_from_sender ? "فرستنده" : "بازبین")}
                </Typography>
                <Typography variant="caption" sx={{ opacity: 0.75, whiteSpace: "nowrap" }}>
                  {new Date(r.created_at).toLocaleString("fa-IR")}
                </Typography>
              </Stack>
              <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
                {r.body}
              </Typography>
            </Box>
          ))}
        </Stack>
      )}

      {closed && (
        <Alert severity="info" icon={false}>
          این گفتگو بسته شده است.
        </Alert>
      )}

      {canReply && !closed && (
        <Stack spacing={1}>
          {senderNote && (
            <Typography variant="caption" color="text.secondary">
              {senderNote}
            </Typography>
          )}
          <TextField
            multiline
            minRows={2}
            maxRows={6}
            size="small"
            placeholder="پاسخ خود را بنویسید..."
            value={body}
            onChange={(e) => setBody(e.target.value)}
            disabled={isSending}
            inputProps={{ maxLength: 5000 }}
            fullWidth
          />
          {error && <Alert severity="error">{error}</Alert>}
          <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
            <Button
              variant="contained"
              size="small"
              onClick={handleSend}
              disabled={isSending || !body.trim()}
              startIcon={isSending ? <CircularProgress size={14} color="inherit" /> : <SendOutlinedIcon />}
            >
              ارسال پاسخ
            </Button>
          </Box>
        </Stack>
      )}
    </Stack>
  );
}
