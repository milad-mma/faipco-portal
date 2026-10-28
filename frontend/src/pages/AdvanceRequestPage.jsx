/**
 * صفحه‌ی پرسنل «درخواست مساعده» (/advances؛ docs/advances.md).
 * تب «درخواست‌های من»: وضعیت فعلی (بازه‌ی مجاز، سابقه، مبلغ ثابت پله‌ی سابقه)، ثبت درخواست (فقط توضیح اختیاری)،
 * فهرست درخواست‌ها با مراحل و تاریخچه و امکان لغو تا پیش از تأیید مالی.
 * تب «کارتابل»: درخواست‌های در انتظار من (مدیر واحد / مدیر سایت) با انتخاب چندتایی و تأیید/رد گروهی.
 * کد پرسنلی همکاران در این صفحه نشان داده نمی‌شود (سرور با public=True می‌فرستد).
 */
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import BackLink from "../components/BackLink";
import PillTabs from "../components/PillTabs";
import ResultDialog from "../components/ResultDialog";
import NoteDialog from "../components/NoteDialog";
import {
  AmountField,
  LoanHistory,
  LoanStatusChip,
  LoanSteps,
  errText,
  formatRial,
  formatService,
  rialWords,
} from "../components/loans/LoanShared";
import {
  cancelAdvance,
  decideAdvances,
  fetchAdvanceInbox,
  fetchMyAdvances,
  submitAdvance,
} from "../api/advances";

const fa = (n) => Number(n || 0).toLocaleString("fa-IR");

// متن خلاصه‌ی نتیجه‌ی یک عملیات گروهی: «۳ مورد ثبت شد» + خطاهای موردی
function bulkResultText(res, okLabel) {
  const parts = [];
  if (res.done?.length) parts.push(`${fa(res.done.length)} مورد ${okLabel}`);
  (res.failed || []).forEach((f) =>
    parts.push(`شماره ${fa(f.id)}: ${f.error}`),
  );
  return parts.join("\n") || "موردی انجام نشد";
}

function SubmitDialog({ open, data, onClose, onConfirm }) {
  const [reason, setReason] = useState("");
  const [custom, setCustom] = useState(""); // مبلغ دلخواه (حالت «محدوده»)
  const amount = data?.amount;
  const isRange = data?.amount_mode === "range";
  const min = data?.amount_min;
  const max = data?.amount_max;
  const step = data?.amount_step;
  // خطای مبلغ دلخواه (هم‌سو با advance_rules.validate_requested_amount)
  let amountError = "";
  if (isRange && custom !== "") {
    if (custom < min || custom > max) amountError = `بین ${formatRial(min)} و ${formatRial(max)}`;
    else if (step && custom % step) amountError = `مضرب ${formatRial(step)} باشد`;
  }
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setReason("");
      setCustom("");
      setError("");
    }
  }, [open]);
  const confirm = async () => {
    setSaving(true);
    setError("");
    try {
      await onConfirm(reason, isRange ? custom : null);
    } catch (e) {
      setError(errText(e, "ثبت درخواست ناموفق بود"));
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
      <DialogTitle>ثبت درخواست مساعده</DialogTitle>
      <DialogContent>
        {isRange ? (
          <>
            <Alert severity="info" sx={{ mb: 2 }}>
              مبلغ دلخواه خود را بین <b>{formatRial(min)}</b> و <b>{formatRial(max)}</b> وارد کنید
              {step ? ` (مضرب ${formatRial(step)})` : ""}.
            </Alert>
            <AmountField
              label="مبلغ درخواستی (ریال)"
              value={custom}
              onChange={setCustom}
              fullWidth
              error={Boolean(amountError)}
              helperText={amountError || (custom ? rialWords(custom) : " ")}
              sx={{ mb: 1 }}
              autoFocus
            />
          </>
        ) : (
          <Alert severity="info" sx={{ mb: 2 }}>
            مبلغ مساعده‌ی شما طبق سابقه: <b>{formatRial(amount)}</b> (
            {rialWords(amount)})
          </Alert>
        )}
        <TextField
          label="توضیح (اختیاری)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          fullWidth
          multiline
          minRows={2}
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
        <Button
          variant="contained"
          onClick={confirm}
          disabled={saving || (isRange && (custom === "" || Boolean(amountError)))}
        >
          ثبت درخواست
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function MyAdvanceCard({ item, onCancel }) {
  const cancellable =
    item.status === "in_review" || item.status === "waiting_finance";
  return (
    <Card variant="outlined" sx={{ borderRadius: 3 }}>
      <CardContent>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          flexWrap="wrap"
          gap={1}
        >
          <Typography fontWeight={800}>
            {formatRial(item.amount)} — ماه {item.request_month}
          </Typography>
          <LoanStatusChip item={item} />
        </Stack>
        {item.reason && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            توضیح: {item.reason}
          </Typography>
        )}
        {item.paid_date && (
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            تاریخ پرداخت: {item.paid_date}
            {item.paid_note ? ` — ${item.paid_note}` : ""}
          </Typography>
        )}
        <LoanSteps item={item} />
        <LoanHistory item={item} />
        {cancellable && (
          <Button
            color="error"
            size="small"
            sx={{ mt: 1 }}
            onClick={() => onCancel(item)}
          >
            لغو درخواست
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export default function AdvanceRequestPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get("tab") === "inbox" ? "inbox" : "mine";
  const [data, setData] = useState(null);
  const [inbox, setInbox] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [newOpen, setNewOpen] = useState(false);
  const [result, setResult] = useState(null);
  const [action, setAction] = useState(null); // {ids, approve} | {cancel: item}
  const [selected, setSelected] = useState([]); // شناسه‌های انتخاب‌شده در کارتابل

  const load = useCallback(async () => {
    setLoadError("");
    try {
      const [mine, box] = await Promise.all([
        fetchMyAdvances(),
        fetchAdvanceInbox(),
      ]);
      setData(mine);
      setInbox(box);
      setSelected((prev) => prev.filter((id) => box.some((r) => r.id === id)));
    } catch (e) {
      setLoadError(errText(e, "دریافت اطلاعات ناموفق بود"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const finish = (text, severity = "success") => {
    setResult({ severity, text });
    setNewOpen(false);
    setAction(null);
    load();
  };

  const confirmAction = async (note) => {
    if (action.cancel) {
      await cancelAdvance(action.cancel.id);
      return finish("درخواست لغو شد");
    }
    const res = await decideAdvances(action.ids, action.approve, note || null);
    finish(
      bulkResultText(res, action.approve ? "تأیید شد" : "رد شد"),
      res.failed?.length ? "error" : "success",
    );
  };

  const toggle = (id) =>
    setSelected((s) =>
      s.includes(id) ? s.filter((x) => x !== id) : [...s, id],
    );
  const allSelected = inbox.length > 0 && selected.length === inbox.length;

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <BackLink to="/requests" label="بازگشت به کارتابل درخواست" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        درخواست مساعده
      </Typography>
      <PillTabs
        tabs={[
          { key: "mine", label: "درخواست‌های من" },
          {
            key: "inbox",
            label: inbox.length ? `کارتابل (${fa(inbox.length)})` : "کارتابل",
          },
        ]}
        value={tab}
        onChange={(key) =>
          setSearchParams(key === "inbox" ? { tab: "inbox" } : {})
        }
      />
      {loading && <CircularProgress />}
      {loadError && <Alert severity="error">{loadError}</Alert>}

      {!loading && data && tab === "mine" && (
        <Stack spacing={2}>
          {!data.enabled && (
            <Alert severity="info">
              درخواست مساعده برای سایت شما در حال حاضر فعال نیست.
            </Alert>
          )}
          {data.enabled && (
            <Card variant="outlined" sx={{ borderRadius: 3 }}>
              <CardContent>
                {data.rules_text && (
                  <Typography
                    variant="body2"
                    sx={{ whiteSpace: "pre-line", mb: 1.5 }}
                  >
                    {data.rules_text}
                  </Typography>
                )}
                <Typography variant="body2" color="text.secondary">
                  زمان ثبت: {data.window_label}
                  {data.max_per_month > 1
                    ? ` — حداکثر ${fa(data.max_per_month)} بار در ماه`
                    : " — یک بار در ماه"}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  سابقه‌ی شما: {formatService(data.service?.months)} — گروه:{" "}
                  {data.group_label}
                </Typography>
                <Typography variant="body1" fontWeight={700} sx={{ mt: 1 }}>
                  {data.amount == null
                    ? "با سابقه‌ی فعلی شما مبلغی برای مساعده تعریف نشده است."
                    : data.amount_mode === "range" && data.amount_min != null
                      ? `مبلغ قابل درخواست: از ${formatRial(data.amount_min)} تا ${formatRial(data.amount_max)}`
                      : `مبلغ مساعده‌ی شما: ${formatRial(data.amount)} (${rialWords(data.amount)})`}
                </Typography>
                {data.block_reasons?.length > 0 && (
                  <Alert severity="info" sx={{ mt: 1.5 }}>
                    {data.block_reasons.join(" ")}
                  </Alert>
                )}
                <Button
                  variant="contained"
                  sx={{ mt: 2 }}
                  disabled={!data.can_submit}
                  onClick={() => setNewOpen(true)}
                >
                  ثبت درخواست مساعده
                </Button>
              </CardContent>
            </Card>
          )}
          {data.requests?.length > 0 && <Divider />}
          {data.requests?.map((item) => (
            <MyAdvanceCard
              key={item.id}
              item={item}
              onCancel={(it) => setAction({ cancel: it })}
            />
          ))}
        </Stack>
      )}

      {!loading && tab === "inbox" && (
        <Stack spacing={2}>
          {inbox.length === 0 && (
            <Alert severity="info">درخواستی در انتظار تصمیم شما نیست.</Alert>
          )}
          {inbox.length > 0 && (
            <Stack direction="row" alignItems="center" flexWrap="wrap" gap={1}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={allSelected}
                    indeterminate={selected.length > 0 && !allSelected}
                    onChange={(e) =>
                      setSelected(
                        e.target.checked ? inbox.map((r) => r.id) : [],
                      )
                    }
                  />
                }
                label="انتخاب همه"
              />
              <Box sx={{ flex: 1 }} />
              <Button
                variant="contained"
                disabled={!selected.length}
                onClick={() => setAction({ ids: selected, approve: true })}
              >
                تأیید انتخاب‌شده‌ها
                {selected.length ? ` (${fa(selected.length)})` : ""}
              </Button>
              <Button
                color="error"
                variant="outlined"
                disabled={!selected.length}
                onClick={() => setAction({ ids: selected, approve: false })}
              >
                رد انتخاب‌شده‌ها
              </Button>
            </Stack>
          )}
          {inbox.map((item) => (
            <Card
              key={item.id}
              variant="outlined"
              sx={{
                borderRadius: 3,
                borderColor: selected.includes(item.id)
                  ? "primary.main"
                  : undefined,
              }}
            >
              <CardContent
                sx={{ display: "flex", gap: 1, alignItems: "flex-start" }}
              >
                <Checkbox
                  checked={selected.includes(item.id)}
                  onChange={() => toggle(item.id)}
                  sx={{ mt: -1 }}
                />
                <Box sx={{ flex: 1 }}>
                  <Typography fontWeight={800}>{item.employee}</Typography>
                  <Typography variant="body2">
                    {formatRial(item.amount)} — ماه {item.request_month}
                    {item.department ? ` — ${item.department}` : ""}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    سابقه: {formatService(item.service_months)}
                    {item.reason ? ` — توضیح: ${item.reason}` : ""}
                  </Typography>
                  <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
                    <Button
                      size="small"
                      variant="contained"
                      onClick={() =>
                        setAction({ ids: [item.id], approve: true })
                      }
                    >
                      تأیید
                    </Button>
                    <Button
                      size="small"
                      color="error"
                      variant="outlined"
                      onClick={() =>
                        setAction({ ids: [item.id], approve: false })
                      }
                    >
                      رد
                    </Button>
                  </Stack>
                </Box>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}

      <SubmitDialog
        open={newOpen}
        data={data}
        onClose={() => setNewOpen(false)}
        onConfirm={async (reason, amount) => {
          const item = await submitAdvance(reason, amount);
          finish(`درخواست مساعده ثبت شد — ${item.status_label}`);
        }}
      />
      <NoteDialog
        open={Boolean(action)}
        title={
          action?.cancel
            ? "لغو درخواست"
            : action?.approve
              ? `تأیید ${fa(action?.ids?.length || 0)} درخواست`
              : `رد ${fa(action?.ids?.length || 0)} درخواست`
        }
        confirmLabel={
          action?.cancel ? "لغو درخواست" : action?.approve ? "تأیید" : "رد"
        }
        required={Boolean(action) && !action.cancel && !action.approve}
        warning={
          action?.ids?.length > 1
            ? "یک توضیح برای همه‌ی درخواست‌های انتخاب‌شده ثبت می‌شود."
            : undefined
        }
        onClose={() => setAction(null)}
        onConfirm={confirmAction}
      />
      <ResultDialog result={result} onClose={() => setResult(null)} />
    </Box>
  );
}
