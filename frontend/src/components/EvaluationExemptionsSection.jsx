/**
 * «معاف از ارزیابی» در صفحه‌ی ساختار ارزیابی (Migration 110): پرسنل این فهرست در «تولید انتساب» ارزیابی نمی‌شوند.
 * نوع معافیت: «فقط ارزیابی نشود» (پیش‌فرض؛ همچنان ارزیابی می‌کند) یا «کامل» (ارزیاب هم نیست).
 * برای کسی که در دوره‌های باز انتساب انجام‌نشده دارد، دکمه‌ی حذف همان انتساب‌ها (ارزیابی‌های ثبت‌شده حذف نمی‌شوند).
 * ورودی: siteId و onError.
 */
import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, Card, Chip, MenuItem, Stack, TextField, Typography } from "@mui/material";
import EmployeePicker from "./EmployeePicker";
import ResultDialog from "./ResultDialog";
import {
  addEvaluationExemption,
  fetchEvaluationExemptions,
  removeEvaluationExemption,
  removeExemptPendingAssignments,
} from "../api/evaluationStructure";

const SCOPES = [
  { value: "target_only", label: "فقط ارزیابی نشود", hint: "ارزیابی نمی‌شود ولی پرسنلش را ارزیابی می‌کند" },
  { value: "full", label: "کامل", hint: "نه ارزیابی می‌شود و نه ارزیابی می‌کند" },
];
const scopeLabel = (v) => SCOPES.find((s) => s.value === v)?.label || v;

export default function EvaluationExemptionsSection({ siteId, onError }) {
  const [rows, setRows] = useState([]);
  const [picked, setPicked] = useState(null);
  const [reason, setReason] = useState("");
  const [scope, setScope] = useState("target_only");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const load = useCallback(() => {
    fetchEvaluationExemptions(siteId)
      .then(setRows)
      .catch((e) => onError(e?.response?.data?.detail || "دریافت فهرست معاف‌ها ناموفق بود"));
  }, [siteId, onError]);

  useEffect(() => {
    setRows([]);
    setPicked(null);
    setReason("");
    setScope("target_only");
    load();
  }, [load]);

  const run = async (fn, okText) => {
    setBusy(true);
    try {
      const out = await fn();
      if (okText) setResult({ severity: "success", text: typeof okText === "function" ? okText(out) : okText });
      load();
    } catch (e) {
      onError(e?.response?.data?.detail || "عملیات ناموفق بود");
    } finally {
      setBusy(false);
    }
  };

  const add = () =>
    run(async () => {
      const out = await addEvaluationExemption(siteId, picked.id, reason || null, scope);
      setPicked(null);
      setReason("");
      setScope("target_only");
      return out;
    }, (out) =>
      out.pending_count
        ? `به فهرست معاف اضافه شد.\nاین پرسنل ${out.pending_count.toLocaleString("fa-IR")} انتساب انجام‌نشده در دوره‌های باز دارد؛ با دکمه‌ی «حذف انتساب‌های انجام‌نشده» پاکشان کنید.`
        : "به فهرست معاف اضافه شد.");

  return (
    <Box>
      <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>
        معاف از ارزیابی
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1.5 }}>
        این پرسنل در «تولید انتساب» ارزیابی نمی‌شوند (با تولید دوباره هم برنمی‌گردند). «فقط ارزیابی نشود»: همچنان
        پرسنلش را ارزیابی می‌کند؛ «کامل»: ارزیابی هم نمی‌کند. پرسنل غیرفعال یا قطع همکاری‌شده هم خودکار ارزیابی نمی‌شوند.
      </Typography>
      <Stack spacing={1} sx={{ mb: 1.5 }}>
        {rows.length === 0 && <Alert severity="info">کسی در فهرست معاف نیست.</Alert>}
        {rows.map((r) => (
          <Card key={r.employee_id} variant="outlined" sx={{ p: 1.5 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
              <Typography fontWeight={700}>{r.employee}</Typography>
              <Chip size="small" color={r.scope === "full" ? "secondary" : "primary"} variant="outlined" label={scopeLabel(r.scope)} />
              {r.reason && <Chip size="small" label={r.reason} />}
              {r.pending_count > 0 && (
                <Chip size="small" color="warning" label={`${r.pending_count.toLocaleString("fa-IR")} انتساب انجام‌نشده`} />
              )}
              <Box sx={{ flex: 1 }} />
              <Button
                size="small"
                disabled={busy}
                onClick={() =>
                  run(
                    () => addEvaluationExemption(siteId, r.employee_id, r.reason, r.scope === "full" ? "target_only" : "full"),
                    `نوع معافیت به «${scopeLabel(r.scope === "full" ? "target_only" : "full")}» تغییر کرد.`,
                  )
                }
              >
                تغییر به «{scopeLabel(r.scope === "full" ? "target_only" : "full")}»
              </Button>
              {r.pending_count > 0 && (
                <Button
                  size="small"
                  color="warning"
                  disabled={busy}
                  onClick={() => {
                    const role = r.scope === "full" ? "به‌عنوان ارزیاب یا ارزیابی‌شونده" : "به‌عنوان ارزیابی‌شونده";
                    if (!window.confirm(`${r.pending_count} انتساب انجام‌نشده‌ی «${r.employee}» (${role}) در دوره‌های باز حذف شود؟ ارزیابی‌های ثبت‌شده حذف نمی‌شوند.`)) return;
                    run(() => removeExemptPendingAssignments(siteId, r.employee_id), (out) => `${(out.removed || 0).toLocaleString("fa-IR")} انتساب حذف شد.`);
                  }}
                >
                  حذف انتساب‌های انجام‌نشده
                </Button>
              )}
              <Button
                size="small"
                color="error"
                disabled={busy}
                onClick={() => {
                  if (!window.confirm(`«${r.employee}» از فهرست معاف خارج شود؟ از تولید انتساب بعدی دوباره ارزیابی می‌شود.`)) return;
                  run(() => removeEvaluationExemption(siteId, r.employee_id), "از فهرست معاف خارج شد.");
                }}
              >
                خروج از فهرست
              </Button>
            </Stack>
          </Card>
        ))}
      </Stack>
      <Card variant="outlined" sx={{ p: 1.5 }}>
        <Stack spacing={1.5}>
          {picked ? (
            <Stack direction="row" spacing={1} alignItems="center">
              <Chip label={`${picked.first_name} ${picked.last_name} (${picked.personnel_code})`} onDelete={() => setPicked(null)} />
            </Stack>
          ) : (
            <EmployeePicker siteId={siteId} label="افزودن پرسنل به فهرست معاف" onSelect={setPicked} excludeIds={rows.map((r) => r.employee_id)} />
          )}
          <TextField
            select
            size="small"
            label="نوع معافیت"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            helperText={SCOPES.find((x) => x.value === scope)?.hint}
          >
            {SCOPES.map((x) => (
              <MenuItem key={x.value} value={x.value}>
                {x.label}
              </MenuItem>
            ))}
          </TextField>
          <TextField size="small" label="دلیل (اختیاری)" value={reason} onChange={(e) => setReason(e.target.value)} inputProps={{ maxLength: 300 }} placeholder="مثلاً: مرخصی زایمان" />
          <Button variant="contained" onClick={add} disabled={!picked || busy} sx={{ alignSelf: "flex-start" }}>
            افزودن به فهرست معاف
          </Button>
        </Stack>
      </Card>
      <ResultDialog result={result} onClose={() => setResult(null)} />
    </Box>
  );
}
