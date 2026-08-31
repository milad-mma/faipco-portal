import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  IconButton,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { useAuth } from "../context/AuthContext";
import {
  addProhibitedPhrase,
  deleteProhibitedPhrase,
  fetchFeedback,
  fetchProhibitedPhrases,
} from "../api/feedback";

/**
 * صفحه مشاهده «انتقادات و پیشنهادات» در پنل ادمین - برای Admin واقعی، یا
 * دارنده مجوز feedback.view (سایت‌محور) یا feedback.view_all (سراسری).
 *
 * منطق محرمانگی کاملاً در Backend پیاده شده - این صفحه فقط هرچه API
 * برگرداند را نمایش می‌دهد. Admin واقعی همیشه sender_name واقعی را در
 * پاسخ می‌بیند (به‌همراه is_anonymous_requested که نشان می‌دهد کاربر
 * خودش خواستار ناشناس‌ماندن بوده)؛ دارنده مجوز (غیر Admin)، برای پیام‌های
 * ناشناسِ بدون الفاظ نامناسب، sender_name را null دریافت می‌کند.
 *
 * تب «مدیریت کلمات نامناسب» فقط برای Admin واقعی نمایش داده می‌شود - طبق
 * درخواست صریح، حتی دارنده مجوز مشاهده هم نباید این فهرست را ویرایش کند.
 */
export default function FeedbackReportPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState("messages");

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        انتقادات و پیشنهادات
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {user?.is_superuser
          ? "همه پیام‌های سازمان — فرستنده همیشه قابل‌مشاهده است."
          : "پیام‌های سایت(های) تحت مدیریت شما — پیام‌های ناشناس بدون فرستنده نمایش داده می‌شوند."}
      </Typography>

      {user?.is_superuser && (
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
          <Tab value="messages" label="پیام‌ها" />
          <Tab value="prohibited-words" label="مدیریت کلمات نامناسب" />
        </Tabs>
      )}

      {tab === "messages" && <FeedbackMessagesList />}
      {tab === "prohibited-words" && user?.is_superuser && <ProhibitedWordsManager />}
    </Box>
  );
}

function FeedbackMessagesList() {
  const [messages, setMessages] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchFeedback()
      .then(setMessages)
      .catch((err) => setError(err.response?.data?.detail || "دریافت پیام‌ها ناموفق بود."));
  }, []);

  if (error) return <Alert severity="error">{error}</Alert>;

  if (messages === null) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (messages.length === 0) {
    return (
      <Card variant="outlined" sx={{ p: 4, borderRadius: 2, textAlign: "center" }}>
        <Typography variant="body2" color="text.secondary">
          هنوز پیامی ثبت نشده است.
        </Typography>
      </Card>
    );
  }

  return (
    <Stack spacing={1.5}>
      {messages.map((m) => (
        <Card key={m.id} variant="outlined" sx={{ borderRadius: 2, p: 2 }}>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="flex-start"
            sx={{ mb: 1 }}
            flexWrap="wrap"
            rowGap={1}
          >
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Typography variant="body2" fontWeight={700}>
                {m.sender_name || "ناشناس"}
                {m.site_name ? ` — ${m.site_name}` : ""}
              </Typography>
              {m.is_anonymous_requested && <Chip size="small" label="درخواست ناشناس‌ماندن" color="default" />}
              {m.contains_profanity && (
                <Chip size="small" label="حاوی الفاظ نامناسب — هویت آشکار شد" color="warning" />
              )}
            </Stack>
            <Typography variant="caption" color="text.secondary">
              {new Date(m.created_at).toLocaleString("fa-IR")}
            </Typography>
          </Stack>
          <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
            {m.message}
          </Typography>
        </Card>
      ))}
    </Stack>
  );
}

function ProhibitedWordsManager() {
  const [phrases, setPhrases] = useState(null);
  const [newPhrase, setNewPhrase] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  function loadPhrases() {
    fetchProhibitedPhrases()
      .then(setPhrases)
      .catch((err) => setError(err.response?.data?.detail || "دریافت فهرست ناموفق بود."));
  }

  useEffect(() => {
    loadPhrases();
  }, []);

  async function handleAdd() {
    if (!newPhrase.trim()) return;
    setIsSaving(true);
    setError("");
    try {
      await addProhibitedPhrase(newPhrase.trim());
      setNewPhrase("");
      loadPhrases();
    } catch (err) {
      setError(err.response?.data?.detail || "افزودن ناموفق بود.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(id) {
    try {
      await deleteProhibitedPhrase(id);
      loadPhrases();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف ناموفق بود.");
    }
  }

  return (
    <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        اگر متن یک پیام حاوی هرکدام از این کلمات/عبارات باشد، آن پیام حتی اگر «ناشناس» ارسال شده باشد،
        هویت فرستنده‌اش برای دارنده مجوز مشاهده هم آشکار می‌شود.
      </Typography>

      <Stack direction="row" spacing={1.5} sx={{ mb: 3 }}>
        <TextField
          size="small"
          fullWidth
          placeholder="یک کلمه یا عبارت..."
          value={newPhrase}
          onChange={(e) => setNewPhrase(e.target.value)}
          disabled={isSaving}
        />
        <Button variant="contained" onClick={handleAdd} disabled={isSaving || !newPhrase.trim()}>
          افزودن
        </Button>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {phrases === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress size={24} />
        </Box>
      ) : phrases.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          فهرست خالی است.
        </Typography>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>عبارت</TableCell>
                <TableCell align="left">عملیات</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {phrases.map((p) => (
                <TableRow key={p.id} hover>
                  <TableCell>{p.phrase}</TableCell>
                  <TableCell align="left">
                    <IconButton size="small" color="error" onClick={() => handleDelete(p.id)} aria-label="حذف">
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Card>
  );
}
