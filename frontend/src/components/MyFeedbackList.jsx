/**
 * «پیام‌های من» در صفحه‌ی انتقادات و پیشنهادات: پیام‌های خودِ کاربر با وضعیت پیگیری و گفتگو با بازبین.
 * فقط صاحب پیام این فهرست را می‌بیند (GET /feedback/mine). باز کردن یک پیام، «دیده شد» را ثبت می‌کند
 * (فقط برای نشانگر خودِ کاربر؛ به بازبین نشان داده نمی‌شود).
 * ورودی: onUnreadChange(count) برای به‌روزرسانی نشانگر تب.
 */
import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Card,
  Chip,
  CircularProgress,
  Collapse,
  IconButton,
  Stack,
  Typography,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import FeedbackThread, { FEEDBACK_STATUS_COLORS, FEEDBACK_STATUS_LABELS } from "./FeedbackThread";
import { fetchMyFeedback, fetchMyFeedbackThread, replyToMyFeedback } from "../api/feedback";

const CATEGORY_LABELS = { complaint: "انتقاد", suggestion: "پیشنهاد", comment: "نظر" };

// تذکر بالای کادر پاسخ فرستنده‌ی ناشناس — سیستم نمی‌تواند جلوی لو رفتن هویت از روی متن را بگیرد
const ANONYMOUS_REPLY_NOTE =
  "پیام شما ناشناس است. توجه کنید که نحوه‌ی نوشتن یا اشاره به جزئیات می‌تواند هویت شما را برای خواننده مشخص کند.";

export default function MyFeedbackList({ onUnreadChange }) {
  const [items, setItems] = useState(null); // null = در حال بارگذاری
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null); // پیام باز‌شده
  const [threads, setThreads] = useState({}); // id → { message, replies }

  useEffect(() => {
    fetchMyFeedback()
      .then(setItems)
      .catch((err) => setError(err.response?.data?.detail || "دریافت پیام‌ها با خطا مواجه شد."));
  }, []);

  // نشانگر تب (تعداد پاسخ‌های دیده‌نشده) از روی فهرست؛ جدا از setState تا در حین رندر والد را به‌روز نکند
  useEffect(() => {
    if (items) onUnreadChange?.(items.filter((m) => m.has_new_reply).length);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items]);

  // گفتگوی به‌روز را ذخیره و خلاصه‌ی کارت (وضعیت، تعداد پاسخ، پاسخ جدید) را همگام می‌کند
  function applyThread(id, data) {
    setThreads((prev) => ({ ...prev, [id]: data }));
    setItems((prev) => prev?.map((m) => (m.id === id ? { ...m, ...data.message } : m)) ?? prev);
  }

  async function toggle(id) {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    try {
      applyThread(id, await fetchMyFeedbackThread(id));
    } catch (err) {
      setError(err.response?.data?.detail || "دریافت گفتگو با خطا مواجه شد.");
    }
  }

  if (items === null && !error) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Stack spacing={1.5}>
      {error && <Alert severity="error">{error}</Alert>}
      {items?.length === 0 && (
        <Card variant="outlined" sx={{ p: 4, borderRadius: 2, textAlign: "center" }}>
          <Typography variant="body2" color="text.secondary">
            هنوز پیامی نفرستاده‌اید.
          </Typography>
        </Card>
      )}
      {items?.map((m) => {
        const open = openId === m.id;
        const thread = threads[m.id];
        return (
          <Card key={m.id} variant="outlined" sx={{ borderRadius: 2 }}>
            <Box
              onClick={() => toggle(m.id)}
              sx={{ p: 2, cursor: "pointer", "&:hover": { bgcolor: "action.hover" } }}
            >
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="subtitle2" fontWeight={700} noWrap>
                    {m.title || CATEGORY_LABELS[m.category] || "پیام"}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(m.created_at).toLocaleString("fa-IR")}
                  </Typography>
                </Box>
                <IconButton size="small" sx={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .2s" }}>
                  <ExpandMoreIcon />
                </IconButton>
              </Stack>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
                <Chip size="small" variant="outlined" color="primary" label={CATEGORY_LABELS[m.category] || m.category} />
                <Chip size="small" label={FEEDBACK_STATUS_LABELS[m.status] || m.status} color={FEEDBACK_STATUS_COLORS[m.status] || "default"} />
                {m.is_anonymous_requested && <Chip size="small" variant="outlined" label="ناشناس" />}
                {m.reply_count > 0 && <Chip size="small" variant="outlined" label={`${m.reply_count.toLocaleString("fa-IR")} پاسخ`} />}
                {m.has_new_reply && <Chip size="small" color="error" label="پاسخ جدید" />}
              </Stack>
            </Box>
            <Collapse in={open} unmountOnExit>
              <Box sx={{ px: 2, pb: 2 }}>
                <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", mb: 2, p: 1.5, borderRadius: 2, bgcolor: "action.hover" }}>
                  {m.message}
                </Typography>
                {thread ? (
                  <FeedbackThread
                    replies={thread.replies}
                    canReply
                    closed={m.status === "closed"}
                    senderNote={m.is_anonymous_requested ? ANONYMOUS_REPLY_NOTE : undefined}
                    emptyText="هنوز پاسخی دریافت نکرده‌اید. وقتی بازبین پاسخ دهد، همین‌جا نمایش داده می‌شود."
                    onSend={async (body) => applyThread(m.id, await replyToMyFeedback(m.id, body))}
                  />
                ) : (
                  <Box sx={{ display: "flex", justifyContent: "center", py: 2 }}>
                    <CircularProgress size={20} />
                  </Box>
                )}
              </Box>
            </Collapse>
          </Card>
        );
      })}
    </Stack>
  );
}
