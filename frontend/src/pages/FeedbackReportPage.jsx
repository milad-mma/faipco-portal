/**
 * صفحه گزارش «انتقادات و پیشنهادات» در پنل ادمین.
 * شامل فهرست صفحه‌بندی‌شده پیام‌ها با فیلتر سمت سرور (فرستنده/سایت/موضوع/ناشناس/بازه تاریخ شمسی)
 * و برای Admin، تب مدیریت کلمات نامناسب که ناشناس بودن پیام را لغو می‌کنند.
 */
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
  TablePagination,
  TableRow,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import PillTabs from "../components/PillTabs";
import { useAuth } from "../context/AuthContext";
import JalaliDateSelect from "../components/JalaliDateSelect";
import { jalaliToGregorian } from "../utils/jalaliDate";
import {
  addProhibitedPhrase,
  deleteFeedback,
  deleteProhibitedPhrase,
  fetchFeedback,
  fetchProhibitedPhrases,
} from "../api/feedback";

const CATEGORY_LABELS = {  // برچسب فارسی دسته‌های پیام
  complaint: "انتقاد",
  suggestion: "پیشنهاد",
  comment: "نظر",
};

/**
 * کامپوننت اصلی صفحه؛ برای Admin، یا دارنده مجوز feedback.view (سایت‌محور) یا feedback.view_all (سراسری).
 *
 * منطق محرمانگی در Backend پیاده شده و این صفحه فقط پاسخ API را نمایش می‌دهد: Admin همیشه
 * sender_name واقعی را می‌گیرد؛ برای دارنده مجوز (غیر Admin)، در پیام‌های ناشناسِ بدون الفاظ
 * نامناسب sender_name برابر null است و «ناشناس» نمایش داده می‌شود.
 *
 * فیلترها به Backend فرستاده می‌شوند (فیلتر سمت سرور) و فیلتر تاریخ با دراپ‌داون روز/ماه/سال شمسی است.
 * تب «مدیریت کلمات نامناسب» فقط برای Admin نمایش داده می‌شود.
 */
export default function FeedbackReportPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState("messages");  // "messages" | "prohibited-words"

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

      {/* تب‌ها فقط برای Admin (کاربر عادی فقط فهرست پیام‌ها را می‌بیند) */}
      {user?.is_superuser && (
        <PillTabs
          value={tab}
          onChange={setTab}
          tabs={[
            { key: "messages", label: "پیام‌ها" },
            { key: "prohibited-words", label: "مدیریت کلمات نامناسب" },
          ]}
        />
      )}

      {tab === "messages" && <FeedbackMessagesList canDelete={Boolean(user?.is_superuser)} />}
      {tab === "prohibited-words" && user?.is_superuser && <ProhibitedWordsManager />}
    </Box>
  );
}

const EMPTY_DATE_PARTS = { year: null, month: null, day: null };  // مقدار اولیه/خالی فیلتر تاریخ شمسی

/**
 * فهرست صفحه‌بندی‌شده پیام‌ها با فیلترهای سمت سرور.
 * ورودی: canDelete (نمایش دکمه حذف هر پیام؛ فقط برای Admin).
 */
function FeedbackMessagesList({ canDelete }) {
  const [allMessages, setAllMessages] = useState(null); // بدون فیلتر - فقط برای ساخت گزینه‌های فیلتر
  const [messages, setMessages] = useState(null);  // پیام‌های صفحه فعلی؛ null = در حال بارگذاری
  const [total, setTotal] = useState(0);  // تعداد کل پیام‌های منطبق با فیلتر (برای صفحه‌بندی)
  const [page, setPage] = useState(0);  // شماره صفحه از صفر (سرور از ۱ می‌شمارد)
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [error, setError] = useState("");
  const [senderFilter, setSenderFilter] = useState("");
  const [siteFilter, setSiteFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [anonymousFilter, setAnonymousFilter] = useState(""); // "" | "true" | "false"
  const [dateFromParts, setDateFromParts] = useState(EMPTY_DATE_PARTS);
  const [dateToParts, setDateToParts] = useState(EMPTY_DATE_PARTS);

  useEffect(() => {
    // فقط برای ساختن گزینه‌های دراپ‌داون فرستنده/سایت، نه نمایش جدول؛ یک صفحه
    // بزرگ (۲۰۰ مورد) گرفته می‌شود تا فهرست گزینه‌ها تقریباً کامل باشد.
    // جدول به‌طور جداگانه و صفحه‌بندی‌شده بارگذاری می‌شود.
    fetchFeedback({ page: 1, pageSize: 200 })
      .then((data) => setAllMessages(data.items))
      .catch((err) => setError(err.response?.data?.detail || "دریافت پیام‌ها با خطا مواجه شد."));
  }, []);

  // ابتدای بازه: فقط وقتی هر سه بخش (روز/ماه/سال) انتخاب شده باشند با ساعت ۰۰:۰۰
  // به ISO تبدیل و به‌عنوان فیلتر اعمال می‌شود؛ انتخاب ناقص فیلتر نمی‌کند.
  const dateFromIso = useMemo(() => {
    const { year, month, day } = dateFromParts;
    if (!year || !month || !day) return undefined;
    const d = jalaliToGregorian(year, month, day, 0, 0);
    return d.toISOString();
  }, [dateFromParts]);

  // پایان بازه: تاریخ شمسی کامل با ساعت ۲۳:۵۹ به ISO تبدیل می‌شود؛ انتخاب ناقص = بدون فیلتر
  const dateToIso = useMemo(() => {
    const { year, month, day } = dateToParts;
    if (!year || !month || !day) return undefined;
    const d = jalaliToGregorian(year, month, day, 23, 59);
    return d.toISOString();
  }, [dateToParts]);

  // بارگذاری صفحه فعلی پیام‌ها با فیلترهای انتخاب‌شده؛ با تغییر هر فیلتر یا صفحه دوباره اجرا می‌شود
  useEffect(() => {
    setError("");
    fetchFeedback({
      senderId: senderFilter || undefined,
      siteId: siteFilter || undefined,
      category: categoryFilter || undefined,
      isAnonymous: anonymousFilter === "" ? undefined : anonymousFilter === "true",
      dateFrom: dateFromIso,
      dateTo: dateToIso,
      page: page + 1,
      pageSize: rowsPerPage,
    })
      .then((data) => {
        setMessages(data.items);
        setTotal(data.total);
      })
      .catch((err) => setError(err.response?.data?.detail || "دریافت پیام‌ها با خطا مواجه شد."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [senderFilter, siteFilter, categoryFilter, anonymousFilter, dateFromIso, dateToIso, page, rowsPerPage]);

  // با تغییر هر فیلتر به صفحه اول برمی‌گردد تا کاربر روی صفحه‌ای که دیگر ردیفی
  // ندارد نماند.
  useEffect(() => {
    setPage(0);
  }, [senderFilter, siteFilter, categoryFilter, anonymousFilter, dateFromIso, dateToIso]);

  // گزینه‌های یکتای فیلتر فرستنده به‌صورت [sender_id, sender_name] از پیام‌های بدون فیلتر
  const senderOptions = useMemo(() => {
    if (!allMessages) return [];
    const map = new Map();
    for (const m of allMessages) {
      if (m.sender_id) map.set(m.sender_id, m.sender_name);
    }
    return Array.from(map.entries());
  }, [allMessages]);

  // گزینه‌های یکتای فیلتر سایت به‌صورت [site_id, site_name]
  const siteOptions = useMemo(() => {
    if (!allMessages) return [];
    const map = new Map();
    for (const m of allMessages) {
      if (m.site_id) map.set(m.site_id, m.site_name);
    }
    return Array.from(map.entries());
  }, [allMessages]);

  // پس از تأیید کاربر، پیام را حذف و از هر دو فهرست (جدول و منبع گزینه‌ها) برمی‌دارد
  async function handleDelete(id) {
    if (!window.confirm("این پیام برای همیشه حذف شود؟")) return;
    try {
      await deleteFeedback(id);
      setMessages((prev) => prev.filter((m) => m.id !== id));
      setAllMessages((prev) => prev?.filter((m) => m.id !== id) ?? prev);
    } catch (err) {
      setError(err.response?.data?.detail || "حذف با خطا مواجه شد.");
    }
  }

  return (
    <Box>
      {/* نوار فیلترها: ردیف اول دراپ‌داون‌ها، ردیف دوم بازه تاریخ شمسی */}
      <Stack spacing={1.5} sx={{ mb: 2.5 }}>
        <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap alignItems="center">
          {/* فیلتر فرستنده/سایت فقط وقتی گزینه‌ای وجود دارد نمایش داده می‌شود */}
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
            select
            size="small"
            label="موضوع"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            sx={{ minWidth: 130 }}
          >
            <MenuItem value="">همه</MenuItem>
            {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
              <MenuItem key={value} value={value}>
                {label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            size="small"
            label="ناشناس"
            value={anonymousFilter}
            onChange={(e) => setAnonymousFilter(e.target.value)}
            sx={{ minWidth: 130 }}
          >
            <MenuItem value="">همه</MenuItem>
            <MenuItem value="true">فقط ناشناس</MenuItem>
            <MenuItem value="false">فقط غیرناشناس</MenuItem>
          </TextField>
        </Stack>

        <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap alignItems="center">
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
              از تاریخ:
            </Typography>
            <JalaliDateSelect
              year={dateFromParts.year}
              month={dateFromParts.month}
              day={dateFromParts.day}
              onChange={setDateFromParts}
            />
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0 }}>
              تا تاریخ:
            </Typography>
            <JalaliDateSelect
              year={dateToParts.year}
              month={dateToParts.month}
              day={dateToParts.day}
              onChange={setDateToParts}
            />
          </Stack>
        </Stack>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* حالت‌های بارگذاری، خالی، یا فهرست کارت پیام‌ها به‌همراه صفحه‌بندی */}
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
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
                <Typography
                  variant="body2"
                  fontWeight={700}
                  sx={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                >
                  {m.sender_name || "ناشناس"}
                  {/* وقتی نام واقعی نمایش داده می‌شود (Admin، یا پیام حاوی الفاظ نامناسب)
                      ولی فرستنده درخواست ناشناس ماندن داشته، برچسب «(ناشناس)» این را نشان می‌دهد. */}
                  {m.sender_name && m.is_anonymous_requested && (
                    <Typography component="span" variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
                      {" "}
                      (ناشناس)
                    </Typography>
                  )}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0, whiteSpace: "nowrap" }}>
                  {new Date(m.created_at).toLocaleString("fa-IR")}
                </Typography>
              </Stack>

              {/* برچسب‌های موضوع/سایت/الفاظ نامناسب و دکمه حذف */}
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 0.5, mb: 1 }}>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                  <Chip
                    size="small"
                    label={CATEGORY_LABELS[m.category] || m.category}
                    color="primary"
                    variant="outlined"
                  />
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
          {/* صفحه‌بندی سمت سرور؛ تغییر تعداد در صفحه به صفحه اول برمی‌گرداند */}
          <TablePagination
            component="div"
            count={total}
            page={page}
            onPageChange={(_, newPage) => setPage(newPage)}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={(e) => {
              setRowsPerPage(parseInt(e.target.value, 10));
              setPage(0);
            }}
            rowsPerPageOptions={[10, 25, 50, 100]}
            labelRowsPerPage="تعداد در هر صفحه:"
            labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
          />
        </Stack>
      )}
    </Box>
  );
}

/**
 * مدیریت فهرست کلمات/عبارات نامناسب (فقط Admin): نمایش، افزودن و حذف.
 * پیامی که یکی از این عبارات را داشته باشد، حتی اگر ناشناس ارسال شده باشد هویت فرستنده‌اش آشکار می‌شود.
 */
function ProhibitedWordsManager() {
  const [phrases, setPhrases] = useState(null);  // فهرست عبارات؛ null = در حال بارگذاری
  const [newPhrase, setNewPhrase] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  // فهرست عبارات را از سرور می‌گیرد
  function loadPhrases() {
    fetchProhibitedPhrases()
      .then(setPhrases)
      .catch((err) => setError(err.response?.data?.detail || "دریافت فهرست با خطا مواجه شد."));
  }

  // بارگذاری اولیه فهرست
  useEffect(() => {
    loadPhrases();
  }, []);

  // عبارت جدید (trim شده) را اضافه و فهرست را تازه می‌کند
  async function handleAdd() {
    if (!newPhrase.trim()) return;
    setIsSaving(true);
    setError("");
    try {
      await addProhibitedPhrase(newPhrase.trim());
      setNewPhrase("");
      loadPhrases();
    } catch (err) {
      setError(err.response?.data?.detail || "افزودن با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  // عبارت را حذف و فهرست را تازه می‌کند
  async function handleDelete(id) {
    try {
      await deleteProhibitedPhrase(id);
      loadPhrases();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف با خطا مواجه شد.");
    }
  }

  return (
    <Card variant="outlined" sx={{ borderRadius: 2, p: 3 }}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        اگر متن یک پیام حاوی هرکدام از این کلمات/عبارات باشد، آن پیام حتی اگر «ناشناس» ارسال شده باشد،
        هویت فرستنده‌اش برای دارنده مجوز مشاهده هم آشکار می‌شود.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* فرم افزودن عبارت جدید */}
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

      {/* جدول عبارات (یا حالت بارگذاری/خالی) */}
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
