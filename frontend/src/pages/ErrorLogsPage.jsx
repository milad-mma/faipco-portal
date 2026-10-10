/**
 * «گزارش خطاها» (مجوز system.logs؛ docs/error-logs.md): خطاهای سرور، درخواست‌های کند، خطاهای مرورگر کاربران و خطاهای
 * اپ اندروید در یک فهرست. خطاهای یکسان یک ردیف با تعداد و آخرین زمان‌اند؛ هر ردیف توضیح ساده‌ی فارسی (اگر شناخته‌شده
 * باشد)، جزئیات فنی کامل و رخدادهای اخیر با کد پیگیری دارد. جست‌وجو با کد پیگیری‌ای که کاربر در پیام خطا دیده هم کار
 * می‌کند. پایین صفحه: ایمیل هشدار خطاهای جدید (فقط اگر ایمیل سامانه تنظیم شده باشد).
 *
 * تشخیص (diagnosis از سرور؛ backend/app/services/error_diagnosis.py): هر خطا یک برچسب رنگی «مشکل از کجاست» و یک جمله‌ی
 * «کار شما» دارد. تب پیش‌فرض «نیاز به اقدام» فقط نارنجی/قرمز/نامشخص‌ها را نشان می‌دهد؛ «کاری لازم نیست» (اینترنت کاربر،
 * کندی گذرا) جداست و بعد از ۲۴ ساعت بی‌رخداد خودکار «حل شد» می‌شود.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  MenuItem,
  Pagination,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import RefreshOutlinedIcon from "@mui/icons-material/RefreshOutlined";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import ReplayOutlinedIcon from "@mui/icons-material/ReplayOutlined";
import LightbulbOutlinedIcon from "@mui/icons-material/LightbulbOutlined";
import PillTabs from "../components/PillTabs";
import {
  fetchErrorAlertSettings,
  fetchErrorLog,
  fetchErrorLogs,
  reopenErrorLog,
  resolveAllErrorLogs,
  resolveErrorLog,
  saveErrorAlertSettings,
  sendTestErrorAlert,
} from "../api/errorLogs";
import { monoFontSx } from "../theme";

const PAGE_SIZE = 50;
// رنگ و نشانه‌ی هر سطح تشخیص
const LEVEL_STYLE = {
  ok: { severity: "success", emoji: "🟢", label: "کاری لازم نیست" },
  warn: { severity: "warning", emoji: "🟠", label: "نیاز به اقدام" },
  critical: { severity: "error", emoji: "🔴", label: "نیاز به اقدام فوری" },
  unknown: { severity: "info", emoji: "⚪", label: "نامشخص" },
};
// تب‌ها: وضعیت و فیلتر تشخیص
const TABS = [
  { key: "action", label: "نیاز به اقدام", state: "open", attention: "action" },
  { key: "ok", label: "کاری لازم نیست", state: "open", attention: "ok" },
  { key: "resolved", label: "حل‌شده", state: "resolved" },
  { key: "all", label: "همه", state: "all" },
];

/** کادر «مشکل از کجاست / کار شما». compact: فقط عنوان و یک خط (برای کارت فهرست). */
function DiagnosisBox({ diagnosis, compact = false }) {
  if (!diagnosis) return null;
  const style = LEVEL_STYLE[diagnosis.level] || LEVEL_STYLE.unknown;
  return (
    <Alert severity={style.severity} icon={false} sx={{ py: compact ? 0.25 : 1, px: compact ? 1.25 : 2, mt: compact ? 0.75 : 0 }}>
      <Typography variant={compact ? "body2" : "subtitle2"} fontWeight={800}>
        {style.emoji} مشکل از: {diagnosis.title}
        {diagnosis.subject ? ` — کاربر ${diagnosis.subject}` : ""}
      </Typography>
      <Typography
        variant={compact ? "caption" : "body2"}
        sx={
          compact
            ? { display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }
            : { mt: 0.5 }
        }
      >
        کار شما: {diagnosis.action}
      </Typography>
    </Alert>
  );
}
const KIND_COLORS = { error: "error", slow: "warning", client: "info", android: "secondary" };

const fmt = (value) => (value ? new Date(value).toLocaleString("fa-IR") : "—");
const faNum = (n) => Number(n || 0).toLocaleString("fa-IR");

function SummaryChips({ summary }) {
  const items = [
    ["error", "خطای سرور"],
    ["slow", "درخواست کند"],
    ["client", "خطای مرورگر"],
    ["android", "خطای اپ"],
  ];
  return (
    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
      {items.map(([key, label]) => {
        const s = summary?.[key];
        return (
          <Chip
            key={key}
            color={s?.groups ? KIND_COLORS[key] : "default"}
            variant={s?.groups ? "filled" : "outlined"}
            label={`${label}: ${faNum(s?.groups)} مورد باز (${faNum(s?.occurrences)} بار) در ۲۴ ساعت`}
          />
        );
      })}
    </Stack>
  );
}

function DetailDialog({ id, onClose, onChanged }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    setData(null);
    setError("");
    let ignore = false; // کلیک سریع روی چند ردیف: جواب ردیف قبلی روی ردیف جدید ننشیند
    fetchErrorLog(id)
      .then((result) => {
        if (!ignore) setData(result);
      })
      .catch((e) => {
        if (!ignore) setError(e.response?.data?.detail || "دریافت جزئیات ناموفق بود.");
      });
    return () => {
      ignore = true;
    };
  }, [id]);

  async function toggleResolved() {
    setBusy(true);
    try {
      const updated = data.resolved ? await reopenErrorLog(id) : await resolveErrorLog(id);
      setData((d) => ({ ...d, ...updated }));
      onChanged();
    } catch (e) {
      setError(e.response?.data?.detail || "ذخیره ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={Boolean(id)} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>جزئیات خطا</DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {!data && !error && <CircularProgress size={24} />}
        {data && (
          <Stack spacing={2}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip size="small" color={KIND_COLORS[data.kind]} label={data.kind_label} />
              <Chip size="small" variant="outlined" label={data.category_label} />
              {data.resolved ? <Chip size="small" color="success" label="حل‌شده" /> : <Chip size="small" label="باز" />}
              <Chip size="small" variant="outlined" label={`${faNum(data.count)} بار`} />
            </Stack>
            <DiagnosisBox diagnosis={data.diagnosis} />
            <Typography sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{data.message}</Typography>
            {data.hint && !data.diagnosis?.action?.includes(data.hint) && (
              <Alert severity="info" icon={<LightbulbOutlinedIcon />}>
                {data.hint}
              </Alert>
            )}
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 1 }}>
              <Typography variant="body2">اولین بار: {fmt(data.first_seen)}</Typography>
              <Typography variant="body2">آخرین بار: {fmt(data.last_seen)}</Typography>
              <Typography variant="body2">منبع: {data.source || "—"}</Typography>
              <Typography variant="body2">آخرین درخواست: {data.last_request || "—"}</Typography>
              <Typography variant="body2">آخرین کاربر: {data.last_user_label || "—"}</Typography>
              <Typography variant="body2" sx={monoFontSx}>
                IP: {data.last_ip || "—"}
              </Typography>
            </Box>
            {data.last_context && (
              <Box component="pre" dir="ltr" sx={{ m: 0, p: 1.5, borderRadius: 1, bgcolor: "action.hover", fontSize: 12, overflowX: "auto" }}>
                {JSON.stringify(data.last_context, null, 2)}
              </Box>
            )}
            {data.detail && (
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                  جزئیات فنی (برای پشتیبانی)
                </Typography>
                <Box
                  component="pre"
                  dir="ltr"
                  sx={{ m: 0, p: 1.5, borderRadius: 1, bgcolor: "action.hover", fontSize: 12, maxHeight: 320, overflow: "auto", whiteSpace: "pre-wrap", wordBreak: "break-all" }}
                >
                  {data.detail}
                </Box>
              </Box>
            )}
            <Box>
              <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                آخرین رخدادها
              </Typography>
              <Stack spacing={0.75}>
                {data.occurrences.map((o, i) => (
                  <Box key={i} sx={{ p: 1, borderRadius: 1, border: 1, borderColor: "divider" }}>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
                      <Typography variant="caption">{fmt(o.occurred_at)}</Typography>
                      {o.request_id && <Chip size="small" variant="outlined" label={`کد پیگیری: ${o.request_id}`} sx={monoFontSx} />}
                      {o.user_label && <Typography variant="caption">کاربر: {o.user_label}</Typography>}
                      {o.ip && (
                        <Typography variant="caption" sx={monoFontSx}>
                          {o.ip}
                        </Typography>
                      )}
                    </Stack>
                    {o.request && (
                      <Typography variant="caption" color="text.secondary" sx={{ display: "block", wordBreak: "break-all" }}>
                        {o.request}
                      </Typography>
                    )}
                  </Box>
                ))}
                {data.occurrences.length === 0 && (
                  <Typography variant="caption" color="text.secondary">
                    رخدادی ثبت نشده است.
                  </Typography>
                )}
              </Stack>
            </Box>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {data && (
          <Button
            onClick={toggleResolved}
            disabled={busy}
            startIcon={data.resolved ? <ReplayOutlinedIcon /> : <CheckCircleOutlineIcon />}
            color={data.resolved ? "inherit" : "success"}
          >
            {data.resolved ? "باز کردن دوباره" : "حل شد"}
          </Button>
        )}
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}

function AlertSettingsCard({ retentionDays }) {
  const [cfg, setCfg] = useState(null);
  const [recipientsText, setRecipientsText] = useState("");
  const [message, setMessage] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchErrorAlertSettings()
      .then((data) => {
        setCfg(data);
        setRecipientsText((data.recipients || []).join("\n"));
      })
      .catch(() => setMessage({ severity: "error", text: "دریافت تنظیمات هشدار ناموفق بود." }));
  }, []);

  async function save() {
    setBusy(true);
    setMessage(null);
    try {
      const recipients = recipientsText.split(/[\s,،;]+/).map((s) => s.trim()).filter(Boolean);
      const data = await saveErrorAlertSettings({ enabled: cfg.enabled, recipients });
      setCfg(data);
      setRecipientsText(data.recipients.join("\n"));
      setMessage({ severity: "success", text: "ذخیره شد." });
    } catch (e) {
      setMessage({ severity: "error", text: e.response?.data?.detail || "ذخیره ناموفق بود." });
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    setBusy(true);
    setMessage(null);
    try {
      const res = await sendTestErrorAlert();
      setMessage({ severity: "success", text: `ایمیل آزمایشی به ${faNum(res.sent)} گیرنده فرستاده شد.` });
    } catch (e) {
      setMessage({ severity: "error", text: e.response?.data?.detail || "ارسال ناموفق بود." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card variant="outlined" sx={{ p: 2.5, borderRadius: 2, mt: 3 }}>
      <Typography fontWeight={700} sx={{ mb: 0.5 }}>
        ایمیل هشدار خطاهای جدید
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        وقتی خطای جدیدی در سرور، اپ اندروید یا صفحه‌ای که از کار افتاده رخ دهد (یا خطای «حل‌شده» دوباره رخ دهد)، به این
        آدرس‌ها ایمیل می‌شود. تکرار همان خطا دوباره ایمیل نمی‌شود. درخواست‌های کند و قطعی اینترنت کاربران ایمیل نمی‌شوند.
      </Typography>
      {!cfg ? (
        <CircularProgress size={20} />
      ) : (
        <Stack spacing={1.5}>
          {!cfg.smtp_ready && (
            <Alert severity="warning">
              ایمیل سامانه (SMTP) در «تنظیمات سامانه» فعال یا کامل نیست؛ تا تنظیم نشود هیچ هشداری فرستاده نمی‌شود.
            </Alert>
          )}
          <FormControlLabel
            control={<Switch checked={cfg.enabled} onChange={(e) => setCfg({ ...cfg, enabled: e.target.checked })} />}
            label="ارسال هشدار فعال باشد"
          />
          <TextField
            label="گیرندگان (هر آدرس در یک خط)"
            value={recipientsText}
            onChange={(e) => setRecipientsText(e.target.value)}
            multiline
            minRows={2}
            inputProps={{ dir: "ltr" }}
            fullWidth
          />
          <Typography variant="caption" color="text.secondary">
            درخواستی که بیش از {faNum(cfg.slow_request_seconds)} ثانیه طول بکشد «درخواست کند» ثبت می‌شود. گزارش‌ها بعد از{" "}
            {faNum(retentionDays || 30)} روز خودکار پاک می‌شوند.
          </Typography>
          {message && <Alert severity={message.severity}>{message.text}</Alert>}
          <Stack direction="row" spacing={1}>
            <Button variant="contained" onClick={save} disabled={busy}>
              ذخیره
            </Button>
            <Button onClick={test} disabled={busy || !cfg.smtp_ready || !cfg.recipients.length}>
              ارسال ایمیل آزمایشی
            </Button>
          </Stack>
        </Stack>
      )}
    </Card>
  );
}

export default function ErrorLogsPage() {
  const [tab, setTab] = useState("action");
  const tabDef = TABS.find((t) => t.key === tab) || TABS[0];
  const state = tabDef.state;
  const [kind, setKind] = useState("");
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState(""); // متن جست‌وجوی اعمال‌شده (با کمی تأخیر)
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadSeq = useRef(0); // فقط جواب آخرین درخواست نمایش داده شود (تغییر سریع فیلترها)
  const load = useCallback(() => {
    setError("");
    const seq = ++loadSeq.current;
    fetchErrorLogs({
      state,
      attention: tabDef.attention,
      kind: kind || undefined,
      category: category || undefined,
      q: query || undefined,
      page,
      page_size: PAGE_SIZE,
    })
      .then((result) => {
        if (seq === loadSeq.current) setData(result);
      })
      .catch((e) => {
        if (seq === loadSeq.current) setError(e.response?.data?.detail || "دریافت گزارش خطاها ناموفق بود.");
      });
  }, [state, tabDef.attention, kind, category, query, page]);

  useEffect(() => {
    load();
  }, [load]);

  // جست‌وجو ۴۰۰ میلی‌ثانیه بعد از آخرین حرف
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(q.trim());
      setPage(1);
    }, 400);
    return () => clearTimeout(timer);
  }, [q]);

  // برگشت به تب ← تازه‌سازی
  useEffect(() => {
    const onVisible = () => document.visibilityState === "visible" && load();
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [load]);

  async function resolveOne(id) {
    try {
      await resolveErrorLog(id);
      load();
    } catch (e) {
      setError(e.response?.data?.detail || "ذخیره ناموفق بود.");
    }
  }

  async function resolveAll() {
    setBusy(true);
    try {
      await resolveAllErrorLogs({ kind: kind || undefined, category: category || undefined, attention: tabDef.attention });
      load();
    } catch (e) {
      setError(e.response?.data?.detail || "ذخیره ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box>
      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
        <Typography variant="h5" fontWeight={700}>
          گزارش خطاها
        </Typography>
        <Tooltip title="تازه‌سازی">
          <IconButton onClick={load}>
            <RefreshOutlinedIcon />
          </IconButton>
        </Tooltip>
      </Stack>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        هر خطا یک تشخیص دارد: «مشکل از کجاست» و «کار شما». فقط تب «نیاز به اقدام» را دنبال کنید؛ بقیه یا کاری
        لازم ندارند یا خودکار حل می‌شوند. کاربر کد پیگیری را که در پیام خطا دیده بفرستد، همین‌جا جست‌وجو کنید.
      </Typography>

      {/* خلاصه‌ی اصلی: چند مورد واقعاً نیاز به اقدام دارد */}
      {data?.attention && (
        <Alert
          severity={data.attention.action ? "warning" : "success"}
          sx={{ mb: 2 }}
          action={
            data.attention.action && tab !== "action" ? (
              <Button color="inherit" size="small" onClick={() => (setTab("action"), setPage(1))}>
                نمایش
              </Button>
            ) : null
          }
        >
          {data.attention.action
            ? `${faNum(data.attention.action)} مورد نیاز به اقدام دارد.`
            : "هیچ موردی نیاز به اقدام ندارد. پرتال سالم است."}
          {data.attention.ok ? ` (${faNum(data.attention.ok)} مورد «کاری لازم نیست» هم باز است که خودکار حل می‌شود.)` : ""}
        </Alert>
      )}

      <SummaryChips summary={data?.summary} />

      <PillTabs
        tabs={TABS.map((t) => ({
          key: t.key,
          label:
            t.key === "action" && data?.attention
              ? `${t.label} (${faNum(data.attention.action)})`
              : t.key === "ok" && data?.attention
                ? `${t.label} (${faNum(data.attention.ok)})`
                : t.label,
        }))}
        value={tab}
        onChange={(k) => {
          setTab(k);
          setPage(1);
        }}
        sx={{ maxWidth: 640 }}
      />

      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mb: 2 }}>
        <TextField
          size="small"
          label="جست‌وجو (متن، کاربر، مسیر یا کد پیگیری)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          sx={{ minWidth: 280 }}
        />
        <TextField
          select
          size="small"
          label="نوع"
          value={kind}
          onChange={(e) => {
            setKind(e.target.value);
            setPage(1);
          }}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value="">همه</MenuItem>
          {(data?.kinds || []).map((k) => (
            <MenuItem key={k.key} value={k.key}>
              {k.label}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="بخش"
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            setPage(1);
          }}
          sx={{ minWidth: 200 }}
        >
          <MenuItem value="">همه</MenuItem>
          {(data?.categories || []).map((c) => (
            <MenuItem key={c.key} value={c.key}>
              {c.label}
            </MenuItem>
          ))}
        </TextField>
        {/* با جست‌وجوی فعال پنهان است: «همه» در سرور فقط با نوع و بخش فیلتر می‌شود، نه متن جست‌وجو */}
        {/* «حل شدن همه» فقط همان تب (نیاز به اقدام / کاری لازم نیست) و همان نوع/بخش؛ با جست‌وجوی فعال پنهان است */}
        {state === "open" && !query && data?.total > 0 && (
          <Button onClick={resolveAll} disabled={busy} startIcon={<CheckCircleOutlineIcon />} color="success">
            حل شدن همه‌ی موارد این فیلتر
          </Button>
        )}
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {!data ? (
        <CircularProgress />
      ) : data.items.length === 0 ? (
        <Alert severity="success">
          {tab === "action" ? "هیچ موردی نیاز به اقدام ندارد." : tab === "ok" ? "موردی نیست." : "موردی پیدا نشد."}
        </Alert>
      ) : (
        <Stack spacing={1.25}>
          {data.items.map((item) => (
            <Card
              key={item.id}
              variant="outlined"
              sx={{ p: 1.75, borderRadius: 2, cursor: "pointer", "&:hover": { bgcolor: "action.hover" }, opacity: item.resolved ? 0.7 : 1 }}
              onClick={() => setOpenId(item.id)}
            >
              <Stack direction="row" spacing={1} alignItems="flex-start" justifyContent="space-between">
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mb: 0.75 }}>
                    <Chip size="small" color={KIND_COLORS[item.kind]} label={item.kind_label} />
                    <Chip size="small" variant="outlined" label={item.category_label} />
                    <Chip size="small" variant="outlined" label={`${faNum(item.count)} بار`} />
                    {item.resolved && <Chip size="small" color="success" variant="outlined" label="حل‌شده" />}
                  </Stack>
                  <Typography
                    variant="body2"
                    sx={{ wordBreak: "break-word", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}
                  >
                    {item.message}
                  </Typography>
                  <DiagnosisBox diagnosis={item.diagnosis} compact />
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
                    آخرین بار: {fmt(item.last_seen)}
                    {item.last_user_label ? ` · کاربر: ${item.last_user_label}` : ""}
                    {item.last_request ? ` · ${item.last_request}` : ""}
                  </Typography>
                </Box>
                {!item.resolved && (
                  <Tooltip title="حل شد">
                    <IconButton
                      size="small"
                      color="success"
                      onClick={(e) => {
                        e.stopPropagation();
                        resolveOne(item.id);
                      }}
                    >
                      <CheckCircleOutlineIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
              </Stack>
            </Card>
          ))}
          {data.total > PAGE_SIZE && (
            <Stack alignItems="center" sx={{ mt: 1 }}>
              <Pagination count={Math.ceil(data.total / PAGE_SIZE)} page={page} onChange={(_, v) => setPage(v)} color="primary" />
            </Stack>
          )}
        </Stack>
      )}

      <AlertSettingsCard retentionDays={data?.retention_days} />
      <DetailDialog id={openId} onClose={() => setOpenId(null)} onChanged={load} />
    </Box>
  );
}
