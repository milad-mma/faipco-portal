/**
 * پنل مدیریت «مساعده پرسنل» (/advances/admin؛ docs/advances.md). مجوزهای سایت‌محور:
 * - advances.finance: تب «درخواست‌ها» با تأیید/رد گروهی (در انتظار مالی) و ثبت پرداخت گروهی (تأییدشده‌ها)
 * - advances.view: فقط مشاهده‌ی درخواست‌ها
 * - advances.policy: تب «تنظیمات» (فعال‌سازی، مدیر سایت مساعده، بازه‌ی روزهای ثبت، دفعات در ماه، پله‌های سابقه،
 *   متن قوانین) و «متن اعلان‌ها»
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  MenuItem,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import AddIcon from "@mui/icons-material/Add";
import PillTabs from "../components/PillTabs";
import ResultDialog from "../components/ResultDialog";
import NoteDialog from "../components/NoteDialog";
import NotificationTemplatesEditor from "../components/NotificationTemplatesEditor";
import JalaliCalendarField from "../components/JalaliCalendarField";
import {
  AmountField,
  EmployeeSearch,
  LoanHistory,
  LoanStatusChip,
  LoanSteps,
  digitsOnly,
  errText,
  formatRial,
  formatService,
} from "../components/loans/LoanShared";
import {
  fetchAdvanceAdminSites,
  fetchAdvanceNotificationTemplates,
  fetchAdvanceRequests,
  financeDecideAdvances,
  payAdvances,
  saveAdvanceNotificationTemplates,
  searchAdvanceSiteEmployees,
  updateAdvanceSite,
} from "../api/advances";

const fa = (n) => Number(n || 0).toLocaleString("fa-IR");

const STATUS_OPTIONS = [
  { value: "open", label: "باز (در جریان)" },
  { value: "waiting_finance", label: "در انتظار تأیید مالی" },
  { value: "approved", label: "تأییدشده، در انتظار پرداخت" },
  { value: "paid", label: "پرداخت‌شده" },
  { value: "rejected", label: "ردشده" },
  { value: "cancelled", label: "لغوشده" },
  { value: "", label: "همه" },
];

function bulkResultText(res, okLabel) {
  const parts = [];
  if (res.done?.length) parts.push(`${fa(res.done.length)} مورد ${okLabel}`);
  (res.failed || []).forEach((f) =>
    parts.push(`شماره ${fa(f.id)}: ${f.error}`),
  );
  return parts.join("\n") || "موردی انجام نشد";
}

// ---------- دیالوگ ثبت پرداخت گروهی ----------
function PayDialog({ open, count, onClose, onConfirm }) {
  const [date, setDate] = useState(null);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setDate(null);
      setNote("");
      setError("");
    }
  }, [open]);
  const confirm = async () => {
    setSaving(true);
    setError("");
    try {
      await onConfirm(date, note);
    } catch (e) {
      setError(errText(e, "ثبت پرداخت ناموفق بود"));
    } finally {
      setSaving(false);
    }
  };
  return (
    <Dialog
      open={open}
      onClose={saving ? undefined : onClose}
      fullWidth
      maxWidth="xs"
    >
      <DialogTitle>ثبت پرداخت {fa(count)} مساعده</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <JalaliCalendarField
            label="تاریخ پرداخت (خالی = امروز)"
            value={date}
            onChange={setDate}
            clearable
          />
          <TextField
            label="توضیح (اختیاری)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            fullWidth
            inputProps={{ maxLength: 500 }}
          />
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          انصراف
        </Button>
        <Button variant="contained" onClick={confirm} disabled={saving}>
          ثبت پرداخت
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------- جزئیات یک درخواست ----------
function DetailDialog({ item, onClose }) {
  return (
    <Dialog open={Boolean(item)} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>درخواست مساعده #{item ? fa(item.id) : ""}</DialogTitle>
      {item && (
        <DialogContent>
          <Stack spacing={1}>
            <Typography fontWeight={800}>{item.employee}</Typography>
            <Typography variant="body2">
              {formatRial(item.amount)} — ماه {item.request_month}
              {item.department ? ` — ${item.department}` : ""}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              سابقه هنگام درخواست: {formatService(item.service_months)}
              {item.reason ? ` — توضیح: ${item.reason}` : ""}
            </Typography>
            {item.paid_date && (
              <Typography variant="body2">
                تاریخ پرداخت: {item.paid_date}
                {item.paid_note ? ` — ${item.paid_note}` : ""}
              </Typography>
            )}
            <Box>
              <LoanStatusChip item={item} />
            </Box>
            <LoanSteps item={item} />
            <LoanHistory item={item} />
          </Stack>
        </DialogContent>
      )}
      <DialogActions>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}

// ---------- تب درخواست‌ها ----------
function RequestsTab({ site, reloadKey, onToast }) {
  const [status, setStatus] = useState("open");
  const [month, setMonth] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState([]);
  const [action, setAction] = useState(null); // {ids, approve}
  const [payIds, setPayIds] = useState(null);
  const [detail, setDetail] = useState(null);
  const [tick, setTick] = useState(0);
  // با تغییر فیلتر/صفحه انتخاب‌ها پاک می‌شوند تا شناسه‌های صفحه‌ی قبلی باقی نمانند
  useEffect(() => {
    setSelected([]);
  }, [status, month, q, page, pageSize]);

  useEffect(() => {
    let alive = true;
    setError("");
    const t = setTimeout(() => {
      fetchAdvanceRequests(site.site_id, {
        status,
        month: month.trim() || undefined,
        q: q.trim() || undefined,
        page: page + 1,
        pageSize,
      })
        .then((d) => alive && setData(d))
        .catch(
          (e) => alive && setError(errText(e, "دریافت درخواست‌ها ناموفق بود")),
        );
    }, 300);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [site.site_id, status, month, q, page, pageSize, reloadKey, tick]);

  const items = data?.items || [];
  const waiting = items
    .filter((r) => r.status === "waiting_finance")
    .map((r) => r.id);
  const approved = items
    .filter((r) => r.status === "approved")
    .map((r) => r.id);
  const selWaiting = selected.filter((id) => waiting.includes(id));
  const selApproved = selected.filter((id) => approved.includes(id));
  const selectable = [...waiting, ...approved];
  const toggle = (id) =>
    setSelected((s) =>
      s.includes(id) ? s.filter((x) => x !== id) : [...s, id],
    );
  const done = (res, okLabel) => {
    onToast(
      bulkResultText(res, okLabel),
      res.failed?.length ? "error" : "success",
    );
    setSelected([]);
    setAction(null);
    setPayIds(null);
    setTick((k) => k + 1);
  };

  return (
    <Stack spacing={2}>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1.5}
        alignItems={{ xs: "stretch", sm: "flex-end" }}
        flexWrap="wrap"
        useFlexGap
      >
        <TextField
          select
          size="small"
          label="وضعیت"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(0);
          }}
          sx={{ minWidth: 200 }}
        >
          {STATUS_OPTIONS.map((o) => (
            <MenuItem key={o.value} value={o.value}>
              {o.label}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          size="small"
          label="ماه (مثلاً 1405/07)"
          value={month}
          onChange={(e) => {
            setMonth(e.target.value);
            setPage(0);
          }}
          inputProps={{ dir: "ltr", maxLength: 7 }}
          sx={{ minWidth: 160 }}
        />
        <TextField
          size="small"
          label="جست‌وجوی نام یا کد پرسنلی"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(0);
          }}
          sx={{ minWidth: 260, flexGrow: 1 }}
        />
      </Stack>
      {site.can_finance && (
        <Stack direction="row" alignItems="center" flexWrap="wrap" gap={1}>
          <FormControlLabel
            control={
              <Checkbox
                checked={
                  selectable.length > 0 && selected.length === selectable.length
                }
                indeterminate={
                  selected.length > 0 && selected.length < selectable.length
                }
                disabled={!selectable.length}
                onChange={(e) =>
                  setSelected(e.target.checked ? selectable : [])
                }
              />
            }
            label="انتخاب همه‌ی قابل‌اقدام‌ها"
          />
          <Box sx={{ flex: 1 }} />
          <Button
            variant="contained"
            disabled={!selWaiting.length}
            onClick={() => setAction({ ids: selWaiting, approve: true })}
          >
            تأیید مالی{selWaiting.length ? ` (${fa(selWaiting.length)})` : ""}
          </Button>
          <Button
            color="error"
            variant="outlined"
            disabled={!selWaiting.length}
            onClick={() => setAction({ ids: selWaiting, approve: false })}
          >
            رد
          </Button>
          <Button
            variant="contained"
            color="success"
            disabled={!selApproved.length}
            onClick={() => setPayIds(selApproved)}
          >
            ثبت پرداخت{selApproved.length ? ` (${fa(selApproved.length)})` : ""}
          </Button>
        </Stack>
      )}
      {error && <Alert severity="error">{error}</Alert>}
      {!data && !error && <CircularProgress />}
      {data && (
        <>
          <Box sx={{ overflowX: "auto" }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  {site.can_finance && <TableCell padding="checkbox" />}
                  <TableCell>پرسنل</TableCell>
                  <TableCell>واحد</TableCell>
                  <TableCell>گروه</TableCell>
                  <TableCell>مبلغ</TableCell>
                  <TableCell>ماه</TableCell>
                  <TableCell>وضعیت</TableCell>
                  <TableCell>پرداخت</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={9} align="center">
                      درخواستی پیدا نشد.
                    </TableCell>
                  </TableRow>
                )}
                {items.map((r) => (
                  <TableRow key={r.id} hover selected={selected.includes(r.id)}>
                    {site.can_finance && (
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={selected.includes(r.id)}
                          disabled={!selectable.includes(r.id)}
                          onChange={() => toggle(r.id)}
                        />
                      </TableCell>
                    )}
                    <TableCell sx={{ whiteSpace: "nowrap" }}>
                      {r.employee}
                    </TableCell>
                    <TableCell>{r.department || "—"}</TableCell>
                    <TableCell>{r.group_label}</TableCell>
                    <TableCell sx={{ whiteSpace: "nowrap" }}>
                      {formatRial(r.amount)}
                    </TableCell>
                    <TableCell sx={{ whiteSpace: "nowrap" }}>
                      {r.request_month}
                    </TableCell>
                    <TableCell>
                      <LoanStatusChip item={r} />
                    </TableCell>
                    <TableCell sx={{ whiteSpace: "nowrap" }}>
                      {r.paid_date || "—"}
                    </TableCell>
                    <TableCell>
                      <Button size="small" onClick={() => setDetail(r)}>
                        جزئیات
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
          <TablePagination
            component="div"
            count={data.total}
            page={page}
            onPageChange={(_, p) => setPage(p)}
            rowsPerPage={pageSize}
            onRowsPerPageChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(0);
            }}
            rowsPerPageOptions={[20, 50, 100]}
            labelRowsPerPage="در هر صفحه"
          />
        </>
      )}
      <NoteDialog
        open={Boolean(action)}
        title={
          action?.approve
            ? `تأیید مالی ${fa(action?.ids?.length || 0)} درخواست`
            : `رد ${fa(action?.ids?.length || 0)} درخواست`
        }
        confirmLabel={action?.approve ? "تأیید" : "رد"}
        required={Boolean(action) && !action.approve}
        warning={
          action?.ids?.length > 1
            ? "یک توضیح برای همه‌ی درخواست‌های انتخاب‌شده ثبت می‌شود."
            : undefined
        }
        onClose={() => setAction(null)}
        onConfirm={async (note) => {
          const res = await financeDecideAdvances(
            site.site_id,
            action.ids,
            action.approve,
            note || null,
          );
          done(res, action.approve ? "تأیید شد" : "رد شد");
        }}
      />
      <PayDialog
        open={Boolean(payIds)}
        count={payIds?.length || 0}
        onClose={() => setPayIds(null)}
        onConfirm={async (date, note) => {
          const res = await payAdvances(site.site_id, payIds, date, note);
          done(res, "پرداخت ثبت شد");
        }}
      />
      <DetailDialog item={detail} onClose={() => setDetail(null)} />
    </Stack>
  );
}

// ---------- تب تنظیمات ----------
const GROUPS = [
  { key: "staff", label: "پرسنل" },
  { key: "supervisor", label: "سرپرستان" },
  { key: "manager", label: "مدیران" },
];

function SettingsTab({ site, onSaved }) {
  const [form, setForm] = useState(null);
  const [memberPick, setMemberPick] = useState(null); // پرسنل انتخاب‌شده برای افزودن به مدیران/سرپرستان
  const [memberGroup, setMemberGroup] = useState("manager");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    setForm({
      is_enabled: site.is_enabled,
      manager: site.site_manager_employee_id
        ? { id: site.site_manager_employee_id, label: site.site_manager }
        : null,
      window_from_day: site.window_from_day,
      window_to_day: site.window_to_day,
      max_per_month: site.max_per_month,
      rules_text: site.rules_text || "",
      tiers: (site.tiers || []).map((t) => ({
        group: t.group || "staff",
        min_months: t.min_months,
        amount: t.amount,
      })),
      members: (site.members || []).map((m) => ({ ...m })),
    });
  }, [site]);
  if (!form) return null;
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setTier = (i, k, v) =>
    set(
      "tiers",
      form.tiers.map((t, j) => (j === i ? { ...t, [k]: v } : t)),
    );
  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await updateAdvanceSite(site.site_id, {
        is_enabled: form.is_enabled,
        site_manager_employee_id: form.manager?.id ?? null,
        window_from_day: Number(form.window_from_day),
        window_to_day: Number(form.window_to_day),
        max_per_month: Number(form.max_per_month),
        rules_text: form.rules_text.trim() || null,
        // ردیف‌های کاملاً خالی نادیده گرفته می‌شوند؛ ردیف ناقص خطای فارسی می‌دهد
        tiers: form.tiers
          .filter((t) => String(t.min_months).trim() !== "" || t.amount !== "")
          .map((t) => {
            if (String(t.min_months).trim() === "" || !t.amount) {
              throw new Error(
                "هر پله باید «از سابقه (ماه)» و «مبلغ» داشته باشد",
              );
            }
            return {
              group: t.group || "staff",
              min_months: Number(t.min_months),
              amount: Number(t.amount),
            };
          }),
        members: form.members.map((m) => ({
          employee_id: m.employee_id,
          group: m.group,
        })),
      });
      onSaved();
    } catch (e) {
      setError(
        e?.response
          ? errText(e, "ذخیره ناموفق بود")
          : e.message || "ذخیره ناموفق بود",
      );
    } finally {
      setSaving(false);
    }
  };
  const dayField = (label, key) => (
    <TextField
      label={label}
      size="small"
      value={form[key]}
      onChange={(e) => set(key, digitsOnly(e.target.value).slice(0, 2))}
      inputProps={{ inputMode: "numeric", dir: "ltr" }}
      sx={{ width: 140 }}
    />
  );
  return (
    <Stack spacing={2.5} sx={{ maxWidth: 720 }}>
      <FormControlLabel
        control={
          <Switch
            checked={form.is_enabled}
            onChange={(e) => set("is_enabled", e.target.checked)}
          />
        }
        label="درخواست مساعده برای پرسنل این سایت فعال باشد"
      />
      <EmployeeSearch
        label="مدیر سایت (تأییدکننده‌ی مرحله‌ی «مدیر سایت» مساعده)"
        fetcher={(q) => searchAdvanceSiteEmployees(site.site_id, q)}
        value={form.manager}
        onChange={(v) => set("manager", v)}
      />
      <Typography variant="caption" color="text.secondary">
        مدیر واحد هر پرسنل همان تأییدکننده‌ی مرخصی اوست. «واحد مالی» = دارندگان
        مجوز advances.finance این سایت.
      </Typography>

      <Typography fontWeight={700}>بازه‌ی ثبت درخواست</Typography>
      <Stack
        direction="row"
        spacing={1.5}
        alignItems="flex-end"
        flexWrap="wrap"
        useFlexGap
      >
        {dayField("از روز", "window_from_day")}
        {dayField("تا روز", "window_to_day")}
        <TextField
          label="حداکثر دفعات در ماه"
          size="small"
          value={form.max_per_month}
          onChange={(e) =>
            set("max_per_month", digitsOnly(e.target.value).slice(0, 2))
          }
          inputProps={{ inputMode: "numeric", dir: "ltr" }}
          sx={{ width: 170 }}
        />
      </Stack>
      <Typography variant="caption" color="text.secondary">
        روزهای ماه شمسی، شامل هر دو سر. اگر «از» بزرگ‌تر از «تا» باشد بازه از
        آخر ماه به اول ماه بعد می‌چرخد (مثلاً ۲۵ تا ۵). ۱ تا ۳۱ یعنی همه‌ی
        روزها. رد/لغوشده‌ها در «دفعات» شمرده نمی‌شوند و هر پرسنل هم‌زمان فقط یک
        درخواست باز دارد.
      </Typography>

      <Typography fontWeight={700}>
        مبلغ بر اساس سابقه (پله‌ای، مبلغ ثابت) — جدا برای هر گروه
      </Typography>
      {GROUPS.map((g) => {
        const rows = form.tiers
          .map((t, i) => ({ ...t, i }))
          .filter((t) => (t.group || "staff") === g.key);
        return (
          <Box
            key={g.key}
            sx={{ pl: 1, borderInlineStart: 3, borderColor: "divider" }}
          >
            <Typography fontWeight={600} sx={{ mb: 1 }}>
              {g.label}
              {g.key !== "staff" && rows.length === 0 && (
                <Typography
                  component="span"
                  variant="caption"
                  color="text.secondary"
                >
                  {" "}
                  (بدون پله = همان پله‌های پرسنل)
                </Typography>
              )}
            </Typography>
            <Stack spacing={1}>
              {rows.map((t) => (
                <Stack
                  key={t.i}
                  direction="row"
                  spacing={1.5}
                  alignItems="flex-start"
                >
                  <TextField
                    label="از سابقه (ماه)"
                    size="small"
                    value={t.min_months}
                    onChange={(e) =>
                      setTier(
                        t.i,
                        "min_months",
                        digitsOnly(e.target.value).slice(0, 3),
                      )
                    }
                    inputProps={{ inputMode: "numeric", dir: "ltr" }}
                    sx={{ width: 150 }}
                  />
                  <AmountField
                    label="مبلغ مساعده (ریال)"
                    size="small"
                    value={t.amount}
                    onChange={(v) => setTier(t.i, "amount", v)}
                    sx={{ flex: 1 }}
                  />
                  <IconButton
                    color="error"
                    onClick={() =>
                      set(
                        "tiers",
                        form.tiers.filter((_, j) => j !== t.i),
                      )
                    }
                    sx={{ mt: 0.25 }}
                  >
                    <DeleteOutlineIcon />
                  </IconButton>
                </Stack>
              ))}
              <Button
                size="small"
                startIcon={<AddIcon />}
                onClick={() =>
                  set("tiers", [
                    ...form.tiers,
                    { group: g.key, min_months: "", amount: "" },
                  ])
                }
                sx={{ alignSelf: "flex-start" }}
              >
                افزودن پله‌ی {g.label}
              </Button>
            </Stack>
          </Box>
        );
      })}
      <Typography variant="caption" color="text.secondary">
        هر نفر مبلغ بالاترین پله‌ی گروه خودش را می‌گیرد که سابقه‌اش به آن رسیده
        و نمی‌تواند مبلغ دیگری بزند. کسی که به هیچ پله‌ای نرسد نمی‌تواند درخواست
        بدهد (برای همه، پله‌ی «۰ ماه» بگذارید). سابقه با همان قاعده‌ی وام محاسبه
        می‌شود.
      </Typography>

      <Typography fontWeight={700}>مدیران و سرپرستان</Typography>
      <Typography variant="caption" color="text.secondary">
        «سرپرست» خودکار تشخیص داده می‌شود: هر کسی که تأییدکننده‌ی مرخصی دست‌کم
        یک واحد است (زنجیره‌ی کاراوب یا تعیین دستی در تنظیمات مرخصی). «مدیر» فقط
        این‌جا تعیین می‌شود. تعیین دستی بر تشخیص خودکار مقدم است؛ مثلاً
        می‌توانید یک سرپرست را «مدیر» کنید یا کسی را که در زنجیره نیست «سرپرست».
      </Typography>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1.5}
        alignItems={{ sm: "flex-start" }}
      >
        <Box sx={{ flex: 1 }}>
          <EmployeeSearch
            label="افزودن پرسنل"
            fetcher={(q) => searchAdvanceSiteEmployees(site.site_id, q)}
            value={memberPick}
            onChange={setMemberPick}
            excludeIds={form.members.map((m) => m.employee_id)}
          />
        </Box>
        <TextField
          select
          size="small"
          label="گروه"
          value={memberGroup}
          onChange={(e) => setMemberGroup(e.target.value)}
          sx={{ minWidth: 140 }}
        >
          <MenuItem value="manager">مدیر</MenuItem>
          <MenuItem value="supervisor">سرپرست</MenuItem>
        </TextField>
        <Button
          variant="outlined"
          disabled={!memberPick}
          onClick={() => {
            set("members", [
              ...form.members,
              {
                employee_id: memberPick.id,
                label: memberPick.label,
                group: memberGroup,
              },
            ]);
            setMemberPick(null);
          }}
        >
          افزودن
        </Button>
      </Stack>
      <Stack direction="row" flexWrap="wrap" useFlexGap gap={1}>
        {form.members.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            هنوز کسی تعیین نشده است.
          </Typography>
        )}
        {form.members.map((m) => (
          <Chip
            key={m.employee_id}
            label={`${m.label} — ${m.group === "manager" ? "مدیر" : "سرپرست"}`}
            color={m.group === "manager" ? "primary" : "default"}
            variant="outlined"
            onDelete={() =>
              set(
                "members",
                form.members.filter((x) => x.employee_id !== m.employee_id),
              )
            }
          />
        ))}
      </Stack>

      <TextField
        label="متن قوانین مساعده (بالای فرم پرسنل)"
        value={form.rules_text}
        onChange={(e) => set("rules_text", e.target.value)}
        multiline
        minRows={3}
        inputProps={{ maxLength: 4000 }}
      />
      {error && <Alert severity="error">{error}</Alert>}
      <Box>
        <Button variant="contained" onClick={save} disabled={saving}>
          ذخیره
        </Button>
      </Box>
    </Stack>
  );
}

// ---------- تب متن اعلان‌ها (load/save ثابت تا رندر دوباره‌ی والد ویرایش را نپراند) ----------
function NotifyTab({ siteId }) {
  const load = useCallback(
    () => fetchAdvanceNotificationTemplates(siteId),
    [siteId],
  );
  const save = useCallback(
    (texts) => saveAdvanceNotificationTemplates(siteId, texts),
    [siteId],
  );
  return <NotificationTemplatesEditor load={load} save={save} />;
}

// ---------- صفحه ----------
export default function AdvancesAdminPage() {
  const [sites, setSites] = useState(null);
  const [siteId, setSiteId] = useState(null);
  const [tab, setTab] = useState(null);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [reloadKey, setReloadKey] = useState(0);

  const loadSites = useCallback(() => {
    fetchAdvanceAdminSites()
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
      site.can_view && { key: "requests", label: "درخواست‌ها" },
      site.can_policy && { key: "settings", label: "تنظیمات" },
      site.can_policy && { key: "notify", label: "متن اعلان‌ها" },
    ].filter(Boolean);
  }, [site]);
  const activeTab = tabs.some((t) => t.key === tab) ? tab : tabs[0]?.key;
  const toast = (text, severity = "success") => setResult({ severity, text });

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        مساعده پرسنل
      </Typography>
      {sites && sites.length > 1 && (
        <TextField
          select
          size="small"
          label="سایت"
          value={siteId ?? ""}
          onChange={(e) => setSiteId(Number(e.target.value))}
          sx={{ minWidth: 220, mb: 2 }}
        >
          {sites.map((s) => (
            <MenuItem key={s.site_id} value={s.site_id}>
              {s.site_name}
            </MenuItem>
          ))}
        </TextField>
      )}
      {error && <Alert severity="error">{error}</Alert>}
      {!sites && !error && <CircularProgress />}
      {sites && !sites.length && (
        <Alert severity="info">
          سایتی برای مدیریت مساعده در دسترس شما نیست.
        </Alert>
      )}
      {site && (
        <>
          {!site.is_enabled && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              درخواست مساعده برای این سایت فعال نیست
              {site.can_policy ? " (تب «تنظیمات»)" : ""}.
            </Alert>
          )}
          {site.is_enabled &&
            !site.tiers?.some((t) => t.group === "staff") &&
            site.can_policy && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                هنوز پله‌ی سابقه‌ای برای گروه «پرسنل» تعریف نشده؛ پرسنل عادی
                نمی‌توانند درخواست بدهند.
              </Alert>
            )}
          <PillTabs tabs={tabs} value={activeTab} onChange={setTab} />
          {activeTab === "requests" && (
            <RequestsTab
              key={site.site_id}
              site={site}
              reloadKey={reloadKey}
              onToast={toast}
            />
          )}
          {activeTab === "settings" && (
            <SettingsTab
              site={site}
              onSaved={() => {
                toast("تنظیمات ذخیره شد");
                loadSites();
                setReloadKey((k) => k + 1);
              }}
            />
          )}
          {activeTab === "notify" && (
            <NotifyTab key={site.site_id} siteId={site.site_id} />
          )}
        </>
      )}
      <ResultDialog result={result} onClose={() => setResult(null)} />
    </Box>
  );
}
