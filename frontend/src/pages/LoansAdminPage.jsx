/**
 * مدیریت وام (مسیر /loans/admin؛ docs/loans.md). تب‌ها بر اساس دسترسی کاربر در سایت انتخابی:
 * - «صف و پرداخت» (loans.finance): صف نوبت، خارج از نوبت، پرداخت و تعیین اقساط، ثبت دستی نوبت‌های قبلی،
 *   وام‌های در حال بازپرداخت.
 * - «همه‌ی درخواست‌ها» (loans.view یا finance)
 * - «مقررات» (loans.policy): نسخه‌های مقررات، کپی از سایت دیگر/نمونه
 * - «تنظیمات سایت» (loans.policy): فعال‌سازی و مدیر سایت
 * - «اصلاح سابقه» (loans.finance)
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Radio,
  RadioGroup,
  Snackbar,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
  useMediaQuery,
} from "@mui/material";
import PillTabs from "../components/PillTabs";
import LoanPolicyEditor, { FACTORY_TEMPLATE, STEP_LABELS } from "../components/loans/LoanPolicyEditor";
import {
  AmountField,
  digitsOnly,
  EmployeeSearch,
  GuarantorChips,
  InstallmentsTable,
  LoanStatusChip,
  LoanSteps,
  errText,
  formatDateTime,
  formatRial,
  formatService,
  LoanHistory,
} from "../components/loans/LoanShared";
import {
  createLoanPolicy,
  createManualLoan,
  deleteLoanPolicy,
  deleteServiceOverride,
  fetchEmployeeService,
  fetchLoanAdminSites,
  fetchLoanPolicies,
  fetchLoanRequest,
  fetchLoanRequests,
  fetchServiceOverrides,
  payLoan,
  rejectLoan,
  searchLoanSiteEmployees,
  setLoanQueue,
  setServiceOverride,
  settleLoan,
  toggleInstallment,
  updateLoanPolicy,
  updateLoanSite,
} from "../api/loans";

const STATUS_FILTERS = [
  { value: "", label: "همه" },
  { value: "open", label: "در حال بررسی یا صف" },
  { value: "in_review", label: "در مسیر تأیید" },
  { value: "waiting_finance", label: "در صف پرداخت" },
  { value: "active", label: "در حال بازپرداخت" },
  { value: "settled", label: "تسویه‌شده" },
  { value: "rejected", label: "ردشده" },
  { value: "cancelled", label: "لغوشده" },
];

// «۱۴۰۵/۰۸» → «1405/08»
function digitsOnlySlash(value) {
  return String(value || "")
    .split("/")
    .map((part) => digitsOnly(part))
    .join("/");
}

function nextMonthJalali() {
  // ماه بعد به‌عنوان پیش‌فرض شروع اقساط (YYYY/MM)
  const fmt = new Intl.DateTimeFormat("en-US-u-ca-persian", { year: "numeric", month: "numeric" });
  const parts = Object.fromEntries(fmt.formatToParts(new Date()).map((p) => [p.type, p.value]));
  let y = Number(String(parts.year).replace(/\D/g, ""));
  let m = Number(parts.month) + 1;
  if (m > 12) {
    m = 1;
    y += 1;
  }
  return `${y}/${String(m).padStart(2, "0")}`;
}

// ---------- دیالوگ پرداخت ----------

function PayDialog({ item, onClose, onDone }) {
  const fullScreen = useMediaQuery("(max-width:600px)");
  const [amount, setAmount] = useState("");
  const [mode, setMode] = useState("count");
  const [count, setCount] = useState("10");
  const [per, setPer] = useState("");
  const [firstMonth, setFirstMonth] = useState(nextMonthJalali());
  const [extra, setExtra] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (item) {
      setAmount(item.amount_requested);
      setMode("count");
      setCount("10");
      setPer("");
      setFirstMonth(nextMonthJalali());
      setExtra(false);
      setNote("");
      setError("");
    }
  }, [item]);
  if (!item) return null;
  const n = mode === "count" ? Number(count) || 0 : per ? Math.ceil(Number(amount || 0) / Number(per)) : 0;
  const valid = Number(amount) > 0 && n >= 1 && n <= 120 && n <= Number(amount) && /^\d{4}\/\d{1,2}$/.test(digitsOnlySlash(firstMonth));
  const perShown = mode === "count" && n ? Math.floor(Number(amount || 0) / n) : Number(per) || 0;
  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await payLoan(item.id, {
        amount_approved: amount,
        installment_count: mode === "count" ? Number(count) : null,
        installment_amount: mode === "amount" ? Number(per) : null,
        first_month: digitsOnlySlash(firstMonth),
        extra_confirmed: extra,
        note: note || null,
      });
      onDone("پرداخت و اقساط ثبت شد");
    } catch (e) {
      setError(errText(e, "ثبت پرداخت ناموفق بود"));
    } finally {
      setSaving(false);
    }
  };
  return (
    <Dialog open onClose={saving ? undefined : onClose} fullWidth maxWidth="sm" fullScreen={fullScreen}>
      <DialogTitle>پرداخت وام — {item.employee}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <Typography variant="body2">
            {item.type_title} — درخواستی: {formatRial(item.amount_requested)}
          </Typography>
          <AmountField label="مبلغ پرداختی (ریال)" value={amount} onChange={setAmount} fullWidth />
          <RadioGroup row value={mode} onChange={(e) => setMode(e.target.value)}>
            <FormControlLabel value="count" control={<Radio />} label="تعداد قسط" />
            <FormControlLabel value="amount" control={<Radio />} label="مبلغ هر قسط" />
          </RadioGroup>
          {mode === "count" ? (
            <TextField
              label="تعداد قسط"
              value={count}
              onChange={(e) => setCount(digitsOnly(e.target.value).slice(0, 3))}
              inputProps={{ inputMode: "numeric" }}
            />
          ) : (
            <AmountField label="مبلغ هر قسط (ریال)" value={per} onChange={setPer} />
          )}
          <TextField
            label="ماه اولین قسط"
            value={firstMonth}
            onChange={(e) => setFirstMonth(e.target.value)}
            placeholder="1405/08"
            inputProps={{ dir: "ltr" }}
          />
          {n > 0 && (
            <Alert severity="info">
              {n.toLocaleString("fa-IR")} قسط حدود {formatRial(perShown)} (باقیمانده‌ی تقسیم روی قسط آخر)
            </Alert>
          )}
          {item.extra_requirement && (
            <FormControlLabel
              control={<Checkbox checked={extra} onChange={(e) => setExtra(e.target.checked)} />}
              label={`«${item.extra_requirement}» دریافت شد`}
            />
          )}
          <TextField label="توضیح (اختیاری)" value={note} onChange={(e) => setNote(e.target.value)} multiline minRows={2} />
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          انصراف
        </Button>
        <Button variant="contained" onClick={save} disabled={saving || !valid || (item.extra_requirement && !extra)}>
          ثبت پرداخت
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------- دیالوگ عمومی متن ----------

function PromptDialog({ open, title, label, initial = "", required, numeric, confirmLabel = "ثبت", onClose, onConfirm }) {
  const [value, setValue] = useState(initial);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (open) {
      setValue(initial);
      setError("");
    }
  }, [open, initial]);
  const confirm = async () => {
    setSaving(true);
    setError("");
    try {
      await onConfirm(value);
    } catch (e) {
      setError(errText(e, "عملیات ناموفق بود"));
    } finally {
      setSaving(false);
    }
  };
  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} fullWidth maxWidth="xs">
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <TextField
          label={label}
          value={value}
          onChange={(e) => setValue(numeric ? digitsOnly(e.target.value).slice(0, 7) : e.target.value)}
          fullWidth
          autoFocus
          multiline={!numeric}
          minRows={numeric ? undefined : 2}
          sx={{ mt: 1 }}
        />
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          انصراف
        </Button>
        <Button variant="contained" onClick={confirm} disabled={saving || (required && !String(value).trim())}>
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------- جزئیات یک درخواست ----------

function DetailDialog({ id, canFinance, onClose, onChanged, onPay }) {
  const fullScreen = useMediaQuery("(max-width:600px)");
  const [item, setItem] = useState(null);
  const [busy, setBusy] = useState(null);
  const [prompt, setPrompt] = useState(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    if (!id) return;
    setError("");
    fetchLoanRequest(id)
      .then(setItem)
      .catch((e) => setError(errText(e, "دریافت جزئیات ناموفق بود")));
  }, [id]);
  useEffect(() => {
    setItem(null);
    load();
  }, [load]);
  if (!id) return null;
  const toggle = async (inst) => {
    setBusy(inst.id);
    try {
      setItem(await toggleInstallment(inst.id));
      onChanged();
    } catch (e) {
      setError(errText(e, "تغییر قسط ناموفق بود"));
    } finally {
      setBusy(null);
    }
  };
  const runPrompt = async (value) => {
    const fn = { reject: rejectLoan, settle: settleLoan, queue: (rid, v) => setLoanQueue(rid, Number(v)) }[prompt.kind];
    setItem(await fn(item.id, value || null));
    setPrompt(null);
    onChanged();
  };
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md" fullScreen={fullScreen}>
      <DialogTitle>جزئیات درخواست وام</DialogTitle>
      <DialogContent dividers>
        {!item && !error && <CircularProgress />}
        {error && <Alert severity="error">{error}</Alert>}
        {item && (
          <Stack spacing={1.5}>
            <Stack direction="row" justifyContent="space-between" flexWrap="wrap" useFlexGap spacing={1}>
              <Typography fontWeight={800}>{item.employee}</Typography>
              <LoanStatusChip item={item} />
            </Stack>
            <Typography variant="body2">
              {item.type_title} — درخواستی: {formatRial(item.amount_requested)}
              {item.amount_approved ? ` — پرداختی: ${formatRial(item.amount_approved)}` : ""}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              سابقه هنگام ثبت: {formatService(item.service_months)}
              {item.queue_seq ? ` — شماره‌ی نوبت: ${item.queue_seq.toLocaleString("fa-IR")}` : ""}
              {item.is_manual ? " — ثبت دستی" : ""}
            </Typography>
            {item.reason && <Typography variant="body2">توضیح پرسنل: {item.reason}</Typography>}
            <LoanSteps item={item} vertical={fullScreen} />
            <GuarantorChips item={item} />
            {item.extra_requirement && (
              <Typography variant="body2">
                مدرک اضافه: {item.extra_requirement} — {item.extra_confirmed ? "دریافت شد" : "دریافت نشده"}
              </Typography>
            )}
            <InstallmentsTable item={item} onToggle={canFinance ? toggle : undefined} busyId={busy} />
            {canFinance && item.installments?.length > 0 && (
              <Typography variant="caption" color="text.secondary">
                برای ثبت پرداخت یک قسط روی وضعیت آن بزنید.
              </Typography>
            )}
            {item.finance_note && <Typography variant="body2">توضیح مالی: {item.finance_note}</Typography>}
            <LoanHistory item={item} />
          </Stack>
        )}
      </DialogContent>
      <DialogActions sx={{ flexWrap: "wrap", gap: 1 }}>
        {item && canFinance && item.status === "waiting_finance" && (
          <>
            <Button variant="contained" onClick={() => onPay(item)}>
              پرداخت و اقساط
            </Button>
            {!item.out_of_queue && (
              <Button onClick={() => setPrompt({ kind: "queue", title: "تغییر شماره‌ی نوبت", label: "شماره‌ی نوبت", numeric: true, required: true, initial: String(item.queue_seq || "") })}>
                تغییر نوبت
              </Button>
            )}
          </>
        )}
        {item && canFinance && ["in_review", "waiting_finance"].includes(item.status) && (
          <Button color="error" onClick={() => setPrompt({ kind: "reject", title: "رد درخواست", label: "دلیل رد", required: true })}>
            رد
          </Button>
        )}
        {item && canFinance && item.status === "active" && (
          <Button onClick={() => setPrompt({ kind: "settle", title: "تسویه‌ی یکجا", label: "توضیح (اختیاری)" })}>تسویه‌ی یکجا</Button>
        )}
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
      <PromptDialog
        open={Boolean(prompt)}
        title={prompt?.title}
        label={prompt?.label}
        required={prompt?.required}
        numeric={prompt?.numeric}
        initial={prompt?.initial || ""}
        onClose={() => setPrompt(null)}
        onConfirm={runPrompt}
      />
    </Dialog>
  );
}

// ---------- جدول درخواست‌ها ----------

function RequestsTable({ rows, onOpen, showPosition }) {
  if (!rows.length) return <Alert severity="info">موردی نیست.</Alert>;
  return (
    <TableContainer component={Card} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            {showPosition && <TableCell>نوبت</TableCell>}
            <TableCell>پرسنل</TableCell>
            <TableCell>نوع</TableCell>
            <TableCell>مبلغ</TableCell>
            <TableCell>وضعیت</TableCell>
            <TableCell>ثبت</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((r) => (
            <TableRow key={r.id} hover sx={{ cursor: "pointer" }} onClick={() => onOpen(r)}>
              {showPosition && <TableCell>{r.queue_position ? r.queue_position.toLocaleString("fa-IR") : "—"}</TableCell>}
              <TableCell>{r.employee}</TableCell>
              <TableCell>{r.type_title}</TableCell>
              <TableCell>{formatRial(r.amount_approved ?? r.amount_requested)}</TableCell>
              <TableCell>
                <LoanStatusChip item={r} />
              </TableCell>
              <TableCell>{formatDateTime(r.created_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

// ---------- ثبت دستی ----------

function ManualDialog({ open, siteId, onClose, onDone }) {
  const [employee, setEmployee] = useState(null);
  const [policy, setPolicy] = useState(null);
  const [typeId, setTypeId] = useState("");
  const [typeTitle, setTypeTitle] = useState("");
  const [amount, setAmount] = useState("");
  const [seq, setSeq] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (!open) return;
    setEmployee(null);
    setPolicy(null);
    setTypeId("");
    setTypeTitle("");
    setAmount("");
    setSeq("");
    setNote("");
    setError("");
    fetchLoanPolicies(siteId)
      .then((rows) => setPolicy(rows.find((p) => p.is_current) || null))
      .catch(() => setPolicy(null));
  }, [open, siteId]);
  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await createManualLoan(siteId, {
        employee_id: employee.id,
        loan_type_id: typeId || null,
        type_title: typeId ? null : typeTitle || null,
        amount,
        queue_seq: seq ? Number(seq) : null,
        note: note || null,
      });
      onDone("در صف ثبت شد");
    } catch (e) {
      setError(errText(e, "ثبت ناموفق بود"));
    } finally {
      setSaving(false);
    }
  };
  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} fullWidth maxWidth="sm">
      <DialogTitle>ثبت دستی در صف (نوبت‌های قبلی)</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <Alert severity="info">
            برای کسانی که پیش از راه‌اندازی پرتال در نوبت بوده‌اند. بدون مسیر تأیید مستقیم در صف پرداخت قرار می‌گیرد. اگر وام قبلاً
            پرداخت شده، بعد از ثبت، «پرداخت و اقساط» را بزنید تا اقساط باقیمانده ثبت شود.
          </Alert>
          <EmployeeSearch label="پرسنل" fetcher={(q) => searchLoanSiteEmployees(siteId, q)} value={employee} onChange={setEmployee} />
          {policy?.types?.length ? (
            <TextField select label="نوع وام" value={typeId} onChange={(e) => setTypeId(e.target.value)}>
              {policy.types.map((t) => (
                <MenuItem key={t.id} value={t.id}>
                  {t.title}
                </MenuItem>
              ))}
            </TextField>
          ) : (
            <TextField
              label="عنوان وام"
              value={typeTitle}
              onChange={(e) => setTypeTitle(e.target.value)}
              helperText="مقررات جاری برای این سایت تعریف نشده؛ عنوان را دستی بنویسید"
            />
          )}
          <AmountField label="مبلغ (ریال)" value={amount} onChange={setAmount} />
          <TextField
            label="شماره‌ی نوبت (اختیاری)"
            value={seq}
            onChange={(e) => setSeq(digitsOnly(e.target.value).slice(0, 7))}
            helperText="خالی = آخر صف"
          />
          <TextField label="توضیح" value={note} onChange={(e) => setNote(e.target.value)} multiline minRows={2} />
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          انصراف
        </Button>
        <Button variant="contained" onClick={save} disabled={saving || !employee || !(typeId || typeTitle.trim()) || !amount}>
          ثبت
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------- تب‌ها ----------

function QueueTab({ siteId, onOpen, reloadKey, onManual }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setRows(null);
    setError("");
    Promise.all([fetchLoanRequests(siteId, "waiting_finance"), fetchLoanRequests(siteId, "active")])
      .then(([waiting, active]) => setRows({ waiting, active }))
      .catch((e) => setError(errText(e, "دریافت صف ناموفق بود")));
  }, [siteId, reloadKey]);
  if (error) return <Alert severity="error">{error}</Alert>;
  if (!rows) return <CircularProgress />;
  const queued = rows.waiting.filter((r) => !r.out_of_queue).sort((a, b) => (a.queue_position || 0) - (b.queue_position || 0));
  const outside = rows.waiting.filter((r) => r.out_of_queue);
  return (
    <Stack spacing={2}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography fontWeight={800}>صف پرداخت</Typography>
        <Button onClick={onManual}>ثبت دستی نوبت‌های قبلی</Button>
      </Stack>
      <RequestsTable rows={queued} onOpen={onOpen} showPosition />
      <Typography fontWeight={800}>خارج از نوبت (اضطراری)</Typography>
      <RequestsTable rows={outside} onOpen={onOpen} />
      <Typography fontWeight={800}>در حال بازپرداخت</Typography>
      <RequestsTable rows={rows.active} onOpen={onOpen} />
    </Stack>
  );
}

function RequestsTab({ siteId, onOpen, reloadKey }) {
  const [status, setStatus] = useState("");
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setRows(null);
    setError("");
    fetchLoanRequests(siteId, status)
      .then(setRows)
      .catch((e) => setError(errText(e, "دریافت درخواست‌ها ناموفق بود")));
  }, [siteId, status, reloadKey]);
  return (
    <Stack spacing={2}>
      <TextField select size="small" label="وضعیت" value={status} onChange={(e) => setStatus(e.target.value)} sx={{ maxWidth: 260 }}>
        {STATUS_FILTERS.map((f) => (
          <MenuItem key={f.value} value={f.value}>
            {f.label}
          </MenuItem>
        ))}
      </TextField>
      {error && <Alert severity="error">{error}</Alert>}
      {!rows && !error && <CircularProgress />}
      {rows && <RequestsTable rows={rows} onOpen={onOpen} />}
    </Stack>
  );
}

function PolicyTab({ site, sites, toast }) {
  const [rows, setRows] = useState(null);
  const [editor, setEditor] = useState(null); // {policy} | {source}
  const [newOpen, setNewOpen] = useState(false);
  const [sourceKey, setSourceKey] = useState("empty");
  const [sources, setSources] = useState([]);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    fetchLoanPolicies(site.site_id)
      .then(setRows)
      .catch((e) => setError(errText(e, "دریافت مقررات ناموفق بود")));
  }, [site.site_id]);
  useEffect(() => {
    setRows(null);
    load();
  }, [load]);

  const openNew = async () => {
    const own = (rows || []).map((p) => ({ ...p, site_name: site.site_name }));
    setSources(own);
    setSourceKey(own[0] ? `p${own[0].id}` : "empty");
    setNewOpen(true);
    const others = sites.filter((s) => s.site_id !== site.site_id);
    const lists = await Promise.all(
      others.map((s) =>
        fetchLoanPolicies(s.site_id)
          .then((list) => list.map((p) => ({ ...p, site_name: s.site_name })))
          .catch(() => []),
      ),
    );
    setSources([...own, ...lists.flat()]);
  };

  const startFromSource = () => {
    setNewOpen(false);
    const p = sources.find((x) => `p${x.id}` === sourceKey);
    if (sourceKey === "factory") setEditor({ source: { ...FACTORY_TEMPLATE, _copy: true } });
    else if (p) setEditor({ source: { ...p, _copy: true, _copyId: p.id } });
    else setEditor({ source: null });
  };

  const save = async (payload) => {
    if (editor.policy) await updateLoanPolicy(editor.policy.id, payload);
    else await createLoanPolicy(site.site_id, { ...payload, copy_from_policy_id: editor.source?._copyId || null });
    setEditor(null);
    toast("مقررات ذخیره شد");
    load();
  };

  const remove = async (p) => {
    if (!window.confirm(`مقررات «${p.title}» حذف شود؟ درخواست‌های ثبت‌شده باقی می‌مانند.`)) return;
    try {
      await deleteLoanPolicy(p.id);
      load();
    } catch (err) {
      setError(errText(err, "حذف ناموفق بود"));
    }
  };

  return (
    <Stack spacing={2}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" useFlexGap spacing={1}>
        <Typography variant="body2" color="text.secondary" sx={{ flex: "1 1 260px" }}>
          هر نسخه از «تاریخ اجرا» برای درخواست‌های جدید اعمال می‌شود؛ درخواست‌های قبلی با قانون زمان ثبتشان می‌مانند.
        </Typography>
        <Button variant="contained" onClick={openNew} disabled={!rows}>
          نسخه‌ی جدید
        </Button>
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      {!rows && !error && <CircularProgress />}
      {rows && !rows.length && <Alert severity="warning">برای این سایت هنوز مقرراتی تعریف نشده؛ پرسنل نمی‌توانند درخواست وام بدهند.</Alert>}
      {rows?.map((p) => (
        <Card key={p.id} variant="outlined" sx={{ borderRadius: 3 }}>
          <CardContent>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Typography fontWeight={800}>{p.title}</Typography>
              <Chip size="small" label={`از ${p.effective_from}`} />
              {p.is_current && <Chip size="small" color="success" label="جاری" />}
              {p.is_future && <Chip size="small" color="info" label="آینده" />}
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              مسیر تأیید: {p.approval_steps.map((s) => STEP_LABELS[s]).join(" ← ")}
            </Typography>
            <Box sx={{ overflowX: "auto", mt: 1 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>نوع</TableCell>
                    <TableCell>سقف</TableCell>
                    <TableCell>حداقل سابقه</TableCell>
                    <TableCell>ضامن</TableCell>
                    <TableCell>توضیح</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {p.types.map((t) => (
                    <TableRow key={t.id} sx={{ opacity: t.is_active ? 1 : 0.5 }}>
                      <TableCell>{t.title}</TableCell>
                      <TableCell>{formatRial(t.max_amount)}</TableCell>
                      <TableCell>{formatService(t.min_service_months)}</TableCell>
                      <TableCell>{t.guarantor_count.toLocaleString("fa-IR")}</TableCell>
                      <TableCell>
                        {[t.extra_requirement, t.out_of_queue ? "خارج از نوبت" : null, t.is_active ? null : "غیرفعال"]
                          .filter(Boolean)
                          .join(" — ")}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
            <Stack direction="row" spacing={1} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
              <Button size="small" onClick={() => setEditor({ policy: p })}>
                ویرایش
              </Button>
              <Button size="small" color="error" onClick={() => remove(p)}>
                حذف
              </Button>
            </Stack>
          </CardContent>
        </Card>
      ))}
      <Dialog open={newOpen} onClose={() => setNewOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>شروع نسخه‌ی جدید از</DialogTitle>
        <DialogContent>
          <TextField select fullWidth value={sourceKey} onChange={(e) => setSourceKey(e.target.value)} sx={{ mt: 1 }}>
            <MenuItem value="empty">خالی</MenuItem>
            <MenuItem value="factory">نمونه: دستورالعمل کارخانه (الف/ب/ج)</MenuItem>
            {sources.map((p) => (
              <MenuItem key={p.id} value={`p${p.id}`}>
                {p.site_name} — {p.title} (از {p.effective_from})
              </MenuItem>
            ))}
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNewOpen(false)}>انصراف</Button>
          <Button variant="contained" onClick={startFromSource}>
            ادامه
          </Button>
        </DialogActions>
      </Dialog>
      <LoanPolicyEditor
        open={Boolean(editor)}
        policy={editor?.policy || null}
        source={editor?.source || null}
        onClose={() => setEditor(null)}
        onSave={save}
      />
    </Stack>
  );
}

function SettingsTab({ site, onSaved }) {
  const [enabled, setEnabled] = useState(site.is_enabled);
  const [manager, setManager] = useState(
    site.site_manager_employee_id ? { id: site.site_manager_employee_id, label: site.site_manager } : null,
  );
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    setEnabled(site.is_enabled);
    setManager(site.site_manager_employee_id ? { id: site.site_manager_employee_id, label: site.site_manager } : null);
  }, [site]);
  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await updateLoanSite(site.site_id, { is_enabled: enabled, site_manager_employee_id: manager?.id ?? null });
      onSaved();
    } catch (e) {
      setError(errText(e, "ذخیره ناموفق بود"));
    } finally {
      setSaving(false);
    }
  };
  return (
    <Card variant="outlined" sx={{ borderRadius: 3, maxWidth: 560 }}>
      <CardContent>
        <Stack spacing={2}>
          <FormControlLabel
            control={<Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />}
            label="درخواست وام برای پرسنل این سایت فعال باشد"
          />
          <EmployeeSearch
            label="مدیر سایت (تأییدکننده‌ی مرحله‌ی «مدیر سایت»)"
            fetcher={(q) => searchLoanSiteEmployees(site.site_id, q)}
            value={manager}
            onChange={setManager}
          />
          <Typography variant="caption" color="text.secondary">
            مدیر واحد هر پرسنل همان تأییدکننده‌ی مرخصی اوست و جدا تعریف نمی‌شود. «واحد مالی» = دارندگان مجوز loans.finance این سایت.
          </Typography>
          {error && <Alert severity="error">{error}</Alert>}
          <Button variant="contained" onClick={save} disabled={saving} sx={{ alignSelf: "flex-start" }}>
            ذخیره
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}

function ServiceTab({ siteId, toast }) {
  const [rows, setRows] = useState(null);
  const [employee, setEmployee] = useState(null);
  const [info, setInfo] = useState(null);
  const [start, setStart] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const load = useCallback(() => {
    fetchServiceOverrides(siteId)
      .then(setRows)
      .catch((e) => setError(errText(e, "دریافت فهرست ناموفق بود")));
  }, [siteId]);
  useEffect(() => {
    setRows(null);
    load();
  }, [load]);
  useEffect(() => {
    setInfo(null);
    if (employee) fetchEmployeeService(employee.id).then(setInfo).catch(() => setInfo(null));
  }, [employee]);
  const save = async () => {
    setError("");
    try {
      await setServiceOverride(employee.id, start, note);
      setEmployee(null);
      setStart("");
      setNote("");
      toast("سابقه اصلاح شد");
      load();
    } catch (e) {
      setError(errText(e, "ذخیره ناموفق بود"));
    }
  };
  return (
    <Stack spacing={2}>
      <Alert severity="info">
        سابقه‌ی وام از تاریخ استخدام دوره‌ی فعلی حساب می‌شود (کسی که ترک کار کرده و برگشته، از تاریخ استخدام جدید). فقط برای
        موارد استثنا (مثل انتقال بین سایت‌ها بدون ترک کار) تاریخ شروع سابقه را این‌جا اصلاح کنید.
      </Alert>
      <Card variant="outlined" sx={{ borderRadius: 3 }}>
        <CardContent>
          <Stack spacing={2}>
            <EmployeeSearch label="پرسنل" fetcher={(q) => searchLoanSiteEmployees(siteId, q)} value={employee} onChange={setEmployee} />
            {info && (
              <Typography variant="body2">
                سابقه‌ی فعلی: {formatService(info.months)} {info.start_date ? `(از ${info.start_date})` : ""}
                {info.overridden ? " — اصلاح‌شده" : ""}
              </Typography>
            )}
            <TextField
              label="تاریخ شروع سابقه"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              placeholder="1398/01/15"
              inputProps={{ dir: "ltr" }}
            />
            <TextField label="دلیل" value={note} onChange={(e) => setNote(e.target.value)} />
            {error && <Alert severity="error">{error}</Alert>}
            <Button variant="contained" onClick={save} disabled={!employee || !start || !note.trim()} sx={{ alignSelf: "flex-start" }}>
              ثبت
            </Button>
          </Stack>
        </CardContent>
      </Card>
      {rows && rows.length > 0 && (
        <TableContainer component={Card} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>پرسنل</TableCell>
                <TableCell>تاریخ استخدام</TableCell>
                <TableCell>شروع سابقه‌ی اصلاحی</TableCell>
                <TableCell>دلیل</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.employee_id}>
                  <TableCell>{r.employee}</TableCell>
                  <TableCell>{r.hire_date || "—"}</TableCell>
                  <TableCell>{r.start_date}</TableCell>
                  <TableCell>{r.note}</TableCell>
                  <TableCell>
                    <Button
                      size="small"
                      color="error"
                      onClick={() => {
                        if (!window.confirm("اصلاح سابقه‌ی این پرسنل حذف شود؟")) return;
                        deleteServiceOverride(r.employee_id)
                          .then(load)
                          .catch((err) => setError(errText(err, "حذف ناموفق بود")));
                      }}
                    >
                      حذف
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Stack>
  );
}

// ---------- صفحه ----------

export default function LoansAdminPage() {
  const [sites, setSites] = useState(null);
  const [siteId, setSiteId] = useState(null);
  const [tab, setTab] = useState(null);
  const [error, setError] = useState("");
  const [toastText, setToastText] = useState("");
  const [detailId, setDetailId] = useState(null);
  const [payItem, setPayItem] = useState(null);
  const [manualOpen, setManualOpen] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const loadSites = useCallback(() => {
    fetchLoanAdminSites()
      .then((rows) => {
        setSites(rows);
        setSiteId((cur) => cur ?? rows[0]?.site_id ?? null);
      })
      .catch((e) => setError(errText(e, "دریافت سایت‌ها ناموفق بود")));
  }, []);
  useEffect(() => {
    loadSites();
  }, [loadSites]);

  const site = sites?.find((s) => s.site_id === siteId);
  const tabs = useMemo(() => {
    if (!site) return [];
    return [
      site.can_finance && { key: "queue", label: "صف و پرداخت" },
      site.can_view && { key: "requests", label: "همه‌ی درخواست‌ها" },
      site.can_policy && { key: "policy", label: "مقررات" },
      site.can_policy && { key: "settings", label: "تنظیمات سایت" },
      site.can_finance && { key: "service", label: "اصلاح سابقه" },
    ].filter(Boolean);
  }, [site]);
  const activeTab = tabs.some((t) => t.key === tab) ? tab : tabs[0]?.key;
  const refresh = () => setReloadKey((k) => k + 1);
  const toast = (msg) => setToastText(msg);

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }} flexWrap="wrap" useFlexGap spacing={1}>
        <Typography variant="h5" fontWeight={700}>
          وام پرسنل
        </Typography>
        {sites && sites.length > 1 && (
          <TextField select size="small" label="سایت" value={siteId ?? ""} onChange={(e) => setSiteId(Number(e.target.value))} sx={{ minWidth: 200 }}>
            {sites.map((s) => (
              <MenuItem key={s.site_id} value={s.site_id}>
                {s.site_name}
              </MenuItem>
            ))}
          </TextField>
        )}
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      {!sites && !error && <CircularProgress />}
      {sites && !sites.length && <Alert severity="info">سایتی برای مدیریت وام در دسترس شما نیست.</Alert>}
      {site && (
        <>
          {!site.is_enabled && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              درخواست وام برای این سایت فعال نیست{site.can_policy ? " (تب «تنظیمات سایت»)" : ""}.
            </Alert>
          )}
          <PillTabs tabs={tabs} value={activeTab} onChange={setTab} />
          {activeTab === "queue" && (
            <QueueTab siteId={site.site_id} reloadKey={reloadKey} onOpen={(r) => setDetailId(r.id)} onManual={() => setManualOpen(true)} />
          )}
          {activeTab === "requests" && <RequestsTab siteId={site.site_id} reloadKey={reloadKey} onOpen={(r) => setDetailId(r.id)} />}
          {activeTab === "policy" && <PolicyTab site={site} sites={sites} toast={toast} />}
          {activeTab === "settings" && (
            <SettingsTab
              site={site}
              onSaved={() => {
                toast("تنظیمات ذخیره شد");
                loadSites();
              }}
            />
          )}
          {activeTab === "service" && <ServiceTab siteId={site.site_id} toast={toast} />}
        </>
      )}
      {detailId && (
        <DetailDialog
          key={detailId}
          id={detailId}
          canFinance={Boolean(site?.can_finance)}
          onClose={() => setDetailId(null)}
          onChanged={refresh}
          onPay={(item) => setPayItem(item)}
        />
      )}
      <PayDialog
        item={payItem}
        onClose={() => setPayItem(null)}
        onDone={(msg) => {
          setPayItem(null);
          setDetailId(null);
          toast(msg);
          refresh();
        }}
      />
      <ManualDialog
        open={manualOpen}
        siteId={siteId}
        onClose={() => setManualOpen(false)}
        onDone={(msg) => {
          setManualOpen(false);
          toast(msg);
          refresh();
        }}
      />
      <Snackbar open={Boolean(toastText)} autoHideDuration={4000} onClose={() => setToastText("")} message={toastText} />
    </Box>
  );
}
