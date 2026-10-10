/**
 * «درخواست وام» پرسنل (مسیر /loans؛ کارت «درخواست وام» کارتابل درخواست). docs/loans.md
 * تب «وام‌های من»: متن دستورالعمل سایت، سابقه، درخواست جدید، پیگیری مراحل و اقساط.
 * تب «کارتابل»: ضمانت‌هایی که از من خواسته شده و درخواست‌های منتظر تأیید من (مدیر واحد/مدیر سایت).
 */
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
  useMediaQuery,
} from "@mui/material";
import BackLink from "../components/BackLink";
import PillTabs from "../components/PillTabs";
import ResultDialog from "../components/ResultDialog";
import {
  AmountField,
  EmployeeSearch,
  GuarantorChips,
  InstallmentsTable,
  LoanStatusChip,
  LoanSteps,
  formatDateTime,
  formatRial,
  errText,
  formatService,
  LoanHistory,
} from "../components/loans/LoanShared";
import {
  cancelLoan,
  decideGuarantee,
  decideLoan,
  fetchLoanInbox,
  fetchMyLoans,
  replaceGuarantor,
  searchGuarantors,
  submitLoan,
} from "../api/loans";

function NewLoanDialog({ open, onClose, data, onDone }) {
  const types = data?.policy?.types || [];
  const [typeId, setTypeId] = useState(null);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [guarantors, setGuarantors] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const type = types.find((t) => t.id === typeId);
  const fullScreen = useMediaQuery("(max-width:600px)");

  useEffect(() => {
    if (open) {
      const first = types.find((t) => !t.ineligible_reason);
      setTypeId(first?.id ?? null);
      setAmount("");
      setReason("");
      setGuarantors(Array(first?.guarantor_count || 0).fill(null));
      setError("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    setGuarantors((prev) => Array.from({ length: type?.guarantor_count || 0 }, (_, i) => prev[i] || null));
  }, [type?.id, type?.guarantor_count]);

  const ready =
    type &&
    !type.ineligible_reason &&
    amount > 0 &&
    amount <= type.max_amount &&
    guarantors.length === (type.guarantor_count || 0) &&
    guarantors.every((g) => g);

  const submit = async () => {
    setSaving(true);
    setError("");
    try {
      await submitLoan({
        loan_type_id: type.id,
        amount,
        reason: reason || null,
        guarantor_ids: guarantors.map((g) => g.id),
      });
      onDone("درخواست وام ثبت شد");
    } catch (e) {
      setError(errText(e, "ثبت درخواست ناموفق بود"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} fullWidth maxWidth="sm" fullScreen={fullScreen}>
      <DialogTitle>درخواست وام جدید</DialogTitle>
      <DialogContent dividers>
        <Typography fontWeight={700} sx={{ mb: 1 }}>
          نوع وام
        </Typography>
        <RadioGroup value={typeId ?? ""} onChange={(e) => setTypeId(Number(e.target.value))}>
          {types.map((t) => (
            <Card key={t.id} variant="outlined" sx={{ mb: 1, opacity: t.ineligible_reason ? 0.6 : 1 }}>
              <CardContent sx={{ py: 1, "&:last-child": { pb: 1 } }}>
                <FormControlLabel
                  value={t.id}
                  disabled={Boolean(t.ineligible_reason)}
                  control={<Radio />}
                  label={
                    <Box>
                      <Typography fontWeight={700}>{t.title}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        تا {formatRial(t.max_amount)}
                        {t.min_service_months ? ` — حداقل ${formatService(t.min_service_months)} سابقه` : ""}
                        {t.guarantor_count ? ` — ${t.guarantor_count.toLocaleString("fa-IR")} ضامن` : ""}
                        {t.out_of_queue ? " — خارج از نوبت" : ""}
                      </Typography>
                      {t.extra_requirement && (
                        <Typography variant="body2" color="text.secondary">
                          مدرک لازم: {t.extra_requirement}
                        </Typography>
                      )}
                      {t.ineligible_reason && (
                        <Typography variant="body2" color="error">
                          {t.ineligible_reason}
                        </Typography>
                      )}
                    </Box>
                  }
                />
              </CardContent>
            </Card>
          ))}
        </RadioGroup>
        {type && !type.ineligible_reason && (
          <Stack spacing={2} sx={{ mt: 2 }}>
            <AmountField
              label="مبلغ درخواستی (ریال)"
              value={amount}
              onChange={setAmount}
              fullWidth
              error={amount > type.max_amount}
              helperText={amount > type.max_amount ? `حداکثر ${formatRial(type.max_amount)}` : undefined}
            />
            {guarantors.map((g, i) => (
              <EmployeeSearch
                key={i}
                label={`ضامن ${(i + 1).toLocaleString("fa-IR")} (همکار)`}
                fetcher={(q) => searchGuarantors(q, type.id)}
                value={g}
                excludeIds={guarantors.filter((x, j) => x && j !== i).map((x) => x.id)}
                onChange={(next) => setGuarantors((prev) => prev.map((p, j) => (j === i ? next : p)))}
              />
            ))}
            {guarantors.length > 0 && (
              <Typography variant="caption" color="text.secondary">
                فقط همکارانی در فهرست هستند که طبق مقررات وام سایت می‌توانند ضامن شوند. برای هر ضامن اعلان می‌رود و
                باید در پرتال ضمانت را قبول کند.
              </Typography>
            )}
            <TextField
              label="توضیح (اختیاری)"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              multiline
              minRows={2}
              inputProps={{ maxLength: 2000 }}
            />
          </Stack>
        )}
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
        <Button variant="contained" onClick={submit} disabled={!ready || saving}>
          {saving ? <CircularProgress size={20} /> : "ثبت درخواست"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function NoteDialog({ open, title, confirmLabel, required, warning, onClose, onConfirm }) {
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setNote("");
      setError("");
    }
  }, [open]);
  const confirm = async () => {
    setSaving(true);
    setError("");
    try {
      await onConfirm(note);
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
        {warning && (
          <Alert severity="info" sx={{ mb: 2 }}>
            {warning}
          </Alert>
        )}
        <TextField
          label={required ? "دلیل" : "توضیح (اختیاری)"}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          fullWidth
          multiline
          minRows={2}
          autoFocus
          inputProps={{ maxLength: 2000 }}
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
        <Button variant="contained" onClick={confirm} disabled={saving || (required && !note.trim())}>
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function ReplaceGuarantorDialog({ target, onClose, onDone }) {
  const [value, setValue] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    setValue(null);
    setError("");
  }, [target]);
  if (!target) return null;
  const exclude = target.item.guarantors.map((g) => g.employee_id);
  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await replaceGuarantor(target.item.id, target.guarantor.id, value.id);
      onDone("ضامن جدید ثبت شد");
    } catch (e) {
      setError(errText(e, "تغییر ضامن ناموفق بود"));
    } finally {
      setSaving(false);
    }
  };
  return (
    <Dialog open onClose={saving ? undefined : onClose} fullWidth maxWidth="xs">
      <DialogTitle>انتخاب ضامن جایگزین</DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ mb: 2 }}>
          به‌جای {target.guarantor.name}
        </Typography>
        <EmployeeSearch label="ضامن جدید" fetcher={(q) => searchGuarantors(q, target.item.loan_type_id)} value={value} onChange={setValue} excludeIds={exclude} />
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
        <Button variant="contained" onClick={save} disabled={!value || saving}>
          ثبت
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function MyLoanCard({ item, onCancel, onReplace }) {
  const vertical = useMediaQuery("(max-width:600px)");
  const atGuarantors = item.current_step === "guarantors";
  return (
    <Card variant="outlined" sx={{ borderRadius: 3 }}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1} flexWrap="wrap" useFlexGap>
          <Box>
            <Typography fontWeight={800}>
              {item.type_title} — {formatRial(item.amount_approved ?? item.amount_requested)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              ثبت: {formatDateTime(item.created_at)}
            </Typography>
          </Box>
          <LoanStatusChip item={item} />
        </Stack>
        {item.status !== "cancelled" && <LoanSteps item={item} vertical={vertical} />}
        <GuarantorChips
          item={item}
          renderAction={(g) =>
            atGuarantors && g.status !== "accepted" ? (
              <Button size="small" onClick={() => onReplace(item, g)}>
                تغییر
              </Button>
            ) : null
          }
        />
        {item.extra_requirement && ["waiting_finance", "in_review"].includes(item.status) && (
          <Alert severity="info" sx={{ mt: 1 }}>
            هنگام پرداخت، «{item.extra_requirement}» را به واحد مالی تحویل دهید.
          </Alert>
        )}
        {item.installments?.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <InstallmentsTable item={item} />
          </Box>
        )}
        {item.finance_note && (
          <Typography variant="body2" sx={{ mt: 1 }}>
            توضیح واحد مالی: {item.finance_note}
          </Typography>
        )}
        <LoanHistory item={item} />
        {["in_review", "waiting_finance"].includes(item.status) && (
          <Button color="error" size="small" sx={{ mt: 1 }} onClick={() => onCancel(item)}>
            لغو درخواست
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function InboxCard({ item, kind, onAct }) {
  return (
    <Card variant="outlined" sx={{ borderRadius: 3 }}>
      <CardContent>
        <Typography fontWeight={800}>{item.employee}</Typography>
        <Typography variant="body2">
          {item.type_title} — {formatRial(item.amount_requested)}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          سابقه: {formatService(item.service_months)}
          {item.reason ? ` — توضیح: ${item.reason}` : ""}
        </Typography>
        {kind === "approval" && (
          <Box sx={{ mt: 1 }}>
            <GuarantorChips item={item} />
          </Box>
        )}
        <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
          <Button variant="contained" onClick={() => onAct(item, kind, true)}>
            {kind === "guarantee" ? "قبول ضمانت" : "تأیید"}
          </Button>
          <Button color="error" variant="outlined" onClick={() => onAct(item, kind, false)}>
            {kind === "guarantee" ? "نمی‌پذیرم" : "رد"}
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}

export default function LoanRequestPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get("tab") === "inbox" ? "inbox" : "mine";
  const [data, setData] = useState(null);
  const [inbox, setInbox] = useState({ guarantee: [], approvals: [] });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [newOpen, setNewOpen] = useState(false);
  const [result, setResult] = useState(null); // دیالوگ نتیجه {severity, text}
  const [action, setAction] = useState(null); // {item, kind, approve} | {cancel: item}
  const [replaceTarget, setReplaceTarget] = useState(null);

  const load = useCallback(async () => {
    setLoadError("");
    try {
      const [mine, box] = await Promise.all([fetchMyLoans(), fetchLoanInbox()]);
      setData(mine);
      setInbox(box);
    } catch (e) {
      setLoadError(errText(e, "دریافت اطلاعات ناموفق بود"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const inboxCount = inbox.guarantee.length + inbox.approvals.length;
  const done = (msg) => {
    setResult({ severity: "success", text: msg });
    setNewOpen(false);
    setAction(null);
    setReplaceTarget(null);
    load();
  };

  const confirmAction = async (note) => {
    if (action.cancel) {
      await cancelLoan(action.cancel.id);
      return done("درخواست لغو شد");
    }
    const { item, kind, approve } = action;
    if (kind === "guarantee") await decideGuarantee(item.id, approve, note || null);
    else await decideLoan(item.id, approve, note || null);
    done(approve ? "ثبت شد" : "رد شد");
  };

  const policy = data?.policy;

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <BackLink to="/requests" label="بازگشت به کارتابل درخواست" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        درخواست وام
      </Typography>
      <PillTabs
        tabs={[
          { key: "mine", label: "وام‌های من" },
          { key: "inbox", label: inboxCount ? `کارتابل (${inboxCount.toLocaleString("fa-IR")})` : "کارتابل" },
        ]}
        value={tab}
        onChange={(key) => setSearchParams(key === "inbox" ? { tab: "inbox" } : {})}
      />
      {loading && <CircularProgress />}
      {loadError && <Alert severity="error">{loadError}</Alert>}

      {!loading && data && tab === "mine" && (
        <Stack spacing={2}>
          {!data.enabled && <Alert severity="info">درخواست وام برای سایت شما در حال حاضر فعال نیست.</Alert>}
          {data.enabled && !policy && <Alert severity="info">مقررات وام برای سایت شما هنوز تعریف نشده است.</Alert>}
          {policy && (
            <Card variant="outlined" sx={{ borderRadius: 3 }}>
              <CardContent>
                <Typography fontWeight={800}>{policy.title}</Typography>
                <Typography variant="caption" color="text.secondary">
                  از تاریخ {policy.effective_from}
                </Typography>
                {policy.rules_text && (
                  <Typography variant="body2" sx={{ mt: 1, whiteSpace: "pre-wrap" }}>
                    {policy.rules_text}
                  </Typography>
                )}
                <Divider sx={{ my: 1.5 }} />
                <Typography variant="body2">
                  سابقه‌ی شما برای وام: <b>{data.service.label === "نامشخص" ? "نامشخص" : formatService(data.service.months)}</b>
                  {data.service.start_date ? ` (از ${data.service.start_date})` : ""}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  سابقه از تاریخ استخدام دوره‌ی فعلی حساب می‌شود.
                </Typography>
                <Box sx={{ mt: 2 }}>
                  {data.block_reason ? (
                    <Alert severity="warning">{data.block_reason}</Alert>
                  ) : (
                    <Button variant="contained" onClick={() => setNewOpen(true)} disabled={!policy.types.length}>
                      درخواست وام جدید
                    </Button>
                  )}
                </Box>
              </CardContent>
            </Card>
          )}
          {data.requests.map((item) => (
            <MyLoanCard
              key={item.id}
              item={item}
              onCancel={(it) => setAction({ cancel: it })}
              onReplace={(it, g) => setReplaceTarget({ item: it, guarantor: g })}
            />
          ))}
        </Stack>
      )}

      {!loading && tab === "inbox" && (
        <Stack spacing={2}>
          {!inboxCount && !loadError && <Alert severity="success">موردی در انتظار شما نیست.</Alert>}
          {inbox.guarantee.length > 0 && <Typography fontWeight={800}>درخواست‌های ضمانت</Typography>}
          {inbox.guarantee.map((item) => (
            <InboxCard key={`g${item.id}`} item={item} kind="guarantee" onAct={(it, kind, approve) => setAction({ item: it, kind, approve })} />
          ))}
          {inbox.approvals.length > 0 && <Typography fontWeight={800}>در انتظار تأیید شما</Typography>}
          {inbox.approvals.map((item) => (
            <InboxCard key={`a${item.id}`} item={item} kind="approval" onAct={(it, kind, approve) => setAction({ item: it, kind, approve })} />
          ))}
        </Stack>
      )}

      <NewLoanDialog open={newOpen} onClose={() => setNewOpen(false)} data={data} onDone={done} />
      <NoteDialog
        open={Boolean(action)}
        title={
          action?.cancel
            ? "لغو درخواست وام"
            : action?.kind === "guarantee"
              ? action?.approve
                ? "قبول ضمانت"
                : "نپذیرفتن ضمانت"
              : action?.approve
                ? "تأیید درخواست وام"
                : "رد درخواست وام"
        }
        confirmLabel={action?.cancel ? "لغو درخواست" : action?.approve ? "تأیید" : "رد"}
        required={Boolean(action && !action.cancel && !action.approve && action.kind === "approval")}
        warning={
          action?.cancel
            ? "با لغو، درخواست و نوبت آن از بین می‌رود."
            : action?.kind === "guarantee" && action?.approve
              ? "با قبول، طبق دستورالعمل وام سایت ضامن بازپرداخت این وام می‌شوید."
              : null
        }
        onClose={() => setAction(null)}
        onConfirm={confirmAction}
      />
      <ReplaceGuarantorDialog target={replaceTarget} onClose={() => setReplaceTarget(null)} onDone={done} />
      <ResultDialog result={result} onClose={() => setResult(null)} />
    </Box>
  );
}
