import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  IconButton,
  MenuItem,
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
  deleteFeedback,
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
 * پاسخ می‌بیند؛ دارنده مجوز (غیر Admin)، برای پیام‌های ناشناسِ بدون
 * الفاظ نامناسب، sender_name را null دریافت می‌کند - در این حالت فقط
 * «ناشناس» نمایش داده می‌شود (بدون برچسب اضافه «درخواست ناشناس‌ماندن»،
 * طبق بازخورد صریح).
 *
 * فیلترها (فرستنده/سایت/بازه تاریخ) به Backend فرستاده می‌شوند - فیلتر
 * واقعی سمت سرور، نه فقط مخفی‌کردن ردیف‌ها در Frontend.
 *
 * تب «مدیریت کلمات نامناسب» فقط برای Admin واقعی نمایش داده می‌شود.
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

      {tab === "messages" && <FeedbackMessagesList canDelete={Boolean(user?.is_superuser)} />}
      {tab === "prohibited-words" && user?.is_superuser && <ProhibitedWordsManager />}
    </Box>
  );
}

function FeedbackMessagesList({ canDelete }) {
  const [allMessages, setAllMessages] = useState(null); // بدون فیلتر - فقط برای ساخت گزینه‌های فیلتر
  const [messages, setMessages] = useState(null);
  const [error, setError] = useState("");
  const [senderFilter, setSenderFilter] = useState("");
  const [siteFilter, setSiteFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  useEffect(() => {
    fetchFeedback()
      .then(setAllMessages)
      .catch((err) => setError(err.response?.data?.detail || "دریافت پیام‌ها ناموفق بود."));
  }, []);

  useEffect(() => {
    setError("");
    fetchFeedback({
      senderId: senderFilter || undefined,
      siteId: siteFilter || undefined,
      dateFrom: dateFrom ? new Date(dateFrom).toISOString() : undefined,
      dateTo: dateTo ? new Date(dateTo + "T23:59:59").toISOString() : undefined,
    })
      .then(setMessages)
      .catch((err) => setError(err.response?.data?.detail || "دریافت پیام‌ها ناموفق بود."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [senderFilter, siteFilter, dateFrom, dateTo]);

  const senderOptions = useMemo(() => {
    if (!allMessages) return [];
    const map = new Map();
    for (const m of allMessages) {
      if (m.sender_id) map.set(m.sender_id, m.sender_name);
    }
    return Array.from(map.entries());
  }, [allMessages]);

  const siteOptions = useMemo(() => {
    if (!allMessages) return [];
    const map = new Map();
    for (const m of allMessages) {
      if (m.site_id) map.set(m.site_id, m.site_name);
    }
    return Array.from(map.entries());
  }, [allMessages]);

  async function handleDelete(id) {
    if (!window.confirm("این پیام برای همیشه حذف شود؟")) return;
    try {
      await deleteFeedback(id);
      setMessages((prev) => prev.filter((m) => m.id !== id));
      setAllMessages((prev) => prev?.filter((m) => m.id !== id) ?? prev);
    } catch (err) {
      setError(err.response?.data?.detail || "حذف ناموفق بود.");
    }
  }

  return (
    <Box>
      <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap sx={{ mb: 2.5 }}>
        {senderOptions.length > 0 && (
          <TextField
            select
            size="small"
            label="فرستنده"
            value={senderFilter}
            onChange={(e) => setSenderFilter(e.target.value)}
            sx={{ minWidth: 160 }}
          >
            <MenuItem value="">همه</MenuItem>
            {senderOptions.map(([id, name]) => (
              <MenuItem key={id} value={id}>
                {name}
              </MenuItem>
            ))}
          </TextField>
        )}
        {siteOptions.length > 0 && (
          <TextField
            select
            size="small"
            label="سایت"
            value={siteFilter}
            onChange={(e) => setSiteFilter(e.target.value)}
            sx={{ minWidth: 160 }}
          >
            <MenuItem value="">همه</MenuItem>
            {siteOptions.map(([id, name]) => (
              <MenuItem key={id} value={id}>
                {name}
              </MenuItem>
            ))}
          </TextField>
        )}
        <TextField
          size="small"
          type="date"
          label="از تاریخ"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          InputLabelProps={{ shrink: true }}
        />
        <TextField
          size="small"
          type="date"
          label="تا تاریخ"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          InputLabelProps={{ shrink: true }}
        />
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {messages === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : messages.length === 0 ? (
        <Card variant="outlined" sx={{ p: 4, borderRadius: 2, textAlign: "center" }}>
          <Typography variant="body2" color="text.secondary">
            پیامی یافت نشد.
          </Typography>
        </Card>
      ) : (
        <Stack spacing={1.5}>
          {messages.map((m) => (
            <Card key={m.id} variant="outlined" sx={{ borderRadius: 2, p: 2 }}>
              {/* ردیف اول: نام فرستنده (سمت راست) + تاریخ (سمت چپ، مکان همیشه ثابت،
                  مستقل از طول نام فرستنده یا تعداد برچسب‌ها) */}
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                <Typography
                  variant="body2"
                  fontWeight={700}
                  sx={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                >
                  {m.sender_name || "ناشناس"}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0, whiteSpace: "nowrap" }}>
                  {new Date(m.created_at).toLocaleString("fa-IR")}
                </Typography>
              </Stack>

              {/* ردیف دوم: برچسب‌های وضعیت (فقط اگر لازم باشد) + دکمه حذف */}
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 0.5, mb: 1 }}>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  {m.site_name && <Chip size="small" label={m.site_name} variant="outlined" />}
                  {m.contains_profanity && (
                    <Chip size="small" label="حاوی الفاظ نامناسب — هویت آشکار شد" color="warning" />
                  )}
                </Stack>
                {canDelete && (
                  <IconButton size="small" color="error" onClick={() => handleDelete(m.id)} aria-label="حذف پیام">
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                )}
              </Stack>

              {m.title && (
                <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 0.5 }}>
                  {m.title}
                </Typography>
              )}
              <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
                {m.message}
              </Typography>
            </Card>
          ))}
        </Stack>
      )}
    </Box>
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
