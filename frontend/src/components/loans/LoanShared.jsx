/**
 * اجزای مشترک صفحه‌های وام (پرسنل و مدیریت): قالب مبلغ، چیپ وضعیت، مراحل تأیید، جدول اقساط،
 * فیلد مبلغ با جداکننده‌ی هزارگان و جست‌وجوی پرسنل.
 */
import { useEffect, useState } from "react";
import {
  Autocomplete,
  Box,
  Chip,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";

// ارقام فارسی/عربی → انگلیسی و حذف هر چیز غیرعددی
export function digitsOnly(value) {
  return String(value ?? "")
    .replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d))
    .replace(/[٠-٩]/g, (d) => "٠١٢٣٤٥٦٧٨٩".indexOf(d))
    .replace(/\D/g, "");
}

// متن خطای API (detail فارسی بک‌اند؛ client.js لیست‌های ۴۲۲ را هم به متن تبدیل می‌کند)
export function errText(e, fallback) {
  const detail = e?.response?.data?.detail;
  return typeof detail === "string" && detail ? detail : fallback;
}

export function formatRial(value) {
  if (value === null || value === undefined || value === "") return "—";
  return `${Number(value).toLocaleString("fa-IR")} ریال`;
}

// ۴۰۰٬۰۰۰٬۰۰۰ → «۴۰۰ میلیون ریال» (برای راهنمای زیر فیلد)
export function rialWords(value) {
  const n = Number(value || 0);
  if (!n) return "";
  if (n >= 1e9) return `${(n / 1e9).toLocaleString("fa-IR", { maximumFractionDigits: 2 })} میلیارد ریال`;
  if (n >= 1e6) return `${(n / 1e6).toLocaleString("fa-IR", { maximumFractionDigits: 2 })} میلیون ریال`;
  return formatRial(n);
}

export function formatService(months) {
  if (months === null || months === undefined) return "نامشخص";
  const y = Math.floor(months / 12);
  const m = months % 12;
  const parts = [];
  if (y) parts.push(`${y.toLocaleString("fa-IR")} سال`);
  if (m || !y) parts.push(`${m.toLocaleString("fa-IR")} ماه`);
  return parts.join(" و ");
}

export function formatDateTime(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" });
  } catch {
    return String(value);
  }
}

const STATUS_COLOR = {
  in_review: "warning",
  waiting_finance: "info",
  active: "primary",
  settled: "success",
  rejected: "error",
  cancelled: "default",
};

export function LoanStatusChip({ item }) {
  return <Chip size="small" color={STATUS_COLOR[item.status] || "default"} label={item.status_label} />;
}

// مراحل تأیید یک درخواست (افقی در دسکتاپ، عمودی در موبایل با orientation)
export function LoanSteps({ item, vertical = false }) {
  const steps = item.steps || [];
  if (!steps.length) return null;
  const active = steps.findIndex((s) => s.state === "current");
  const failed = item.status === "rejected";
  return (
    <Stepper
      activeStep={active === -1 ? (steps.every((s) => s.state === "done") ? steps.length : 0) : active}
      orientation={vertical ? "vertical" : "horizontal"}
      alternativeLabel={!vertical}
      sx={{ my: 1 }}
    >
      {steps.map((s, i) => (
        <Step key={s.key} completed={s.state === "done"}>
          <StepLabel
            error={failed && i === steps.findIndex((x) => x.state !== "done")}
            optional={
              s.person ? (
                <Typography variant="caption" color="text.secondary">
                  {s.person}
                </Typography>
              ) : null
            }
          >
            {s.label}
          </StepLabel>
        </Step>
      ))}
    </Stepper>
  );
}

const GUARANTOR_LABEL = { pending: "در انتظار", accepted: "پذیرفت", rejected: "نپذیرفت" };
const GUARANTOR_COLOR = { pending: "warning", accepted: "success", rejected: "error" };

export function GuarantorChips({ item, renderAction }) {
  if (!item.guarantors?.length) return null;
  return (
    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
      {item.guarantors.map((g) => (
        <Stack key={g.id} direction="row" spacing={0.5} alignItems="center">
          <Chip
            size="small"
            variant="outlined"
            color={GUARANTOR_COLOR[g.status]}
            label={`ضامن: ${g.name} — ${GUARANTOR_LABEL[g.status]}`}
          />
          {renderAction?.(g)}
        </Stack>
      ))}
    </Stack>
  );
}

export function InstallmentsTable({ item, onToggle, busyId }) {
  if (!item.installments?.length) return null;
  return (
    <Box sx={{ overflowX: "auto" }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>قسط</TableCell>
            <TableCell>ماه</TableCell>
            <TableCell>مبلغ</TableCell>
            <TableCell>وضعیت</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {item.installments.map((i) => (
            <TableRow key={i.id}>
              <TableCell>{i.seq.toLocaleString("fa-IR")}</TableCell>
              <TableCell>{i.due_month}</TableCell>
              <TableCell>{formatRial(i.amount)}</TableCell>
              <TableCell>
                <Chip
                  size="small"
                  color={i.paid ? "success" : "default"}
                  label={i.paid ? (i.from_payslip ? "پرداخت شد (فیش حقوقی)" : "پرداخت شد") : "پرداخت نشده"}
                  onClick={onToggle ? () => onToggle(i) : undefined}
                  disabled={busyId === i.id}
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Typography variant="body2" sx={{ mt: 1 }}>
        پرداخت‌شده: {formatRial(item.installments_paid)} — باقیمانده: {formatRial(item.remaining)}
      </Typography>
    </Box>
  );
}

// فیلد مبلغ (ریال) با جداکننده؛ value عدد یا ""، onChange(عدد یا "")
export function AmountField({ value, onChange, helperText, ...props }) {
  const shown = value === "" || value === null || value === undefined ? "" : Number(value).toLocaleString("en-US");
  return (
    <TextField
      {...props}
      value={shown}
      inputProps={{ inputMode: "numeric", dir: "ltr", ...(props.inputProps || {}) }}
      onChange={(e) => {
        const raw = digitsOnly(e.target.value).slice(0, 15);
        onChange(raw === "" ? "" : Number(raw));
      }}
      helperText={helperText ?? (value ? rialWords(value) : " ")}
    />
  );
}

// جست‌وجوی پرسنل با fetcher(q) → [{id, label}]؛ value: {id, label} یا null
export function EmployeeSearch({ fetcher, value, onChange, label, excludeIds = [], size = "small", sx }) {
  const [options, setOptions] = useState([]);
  const [input, setInput] = useState("");
  useEffect(() => {
    let alive = true;
    const t = setTimeout(() => {
      fetcher(input)
        .then((rows) => alive && setOptions(rows.filter((r) => !excludeIds.includes(r.id))))
        .catch(() => alive && setOptions([]));
    }, 300);
    return () => {
      alive = false;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input, JSON.stringify(excludeIds)]);
  return (
    <Autocomplete
      size={size}
      sx={sx}
      options={value && !options.some((o) => o.id === value.id) ? [value, ...options] : options}
      value={value}
      filterOptions={(x) => x}
      isOptionEqualToValue={(a, b) => a.id === b.id}
      getOptionLabel={(o) => o?.label || ""}
      onChange={(_, next) => onChange(next)}
      onInputChange={(_, text, reason) => {
        // بعد از انتخاب، MUI متن را به برچسب کامل «نام (کد)» برمی‌گرداند (reset)؛ آن را جست‌وجو نکن
        if (reason !== "reset") setInput(text);
      }}
      noOptionsText="کسی پیدا نشد"
      renderInput={(params) => <TextField {...params} label={label} />}
    />
  );
}

const EVENT_LABELS = {
  submitted: "ثبت درخواست",
  guarantee_accepted: "قبول ضمانت",
  guarantee_rejected: "رد ضمانت",
  guarantor_replaced: "تغییر ضامن",
  approved: "تأیید",
  rejected: "رد",
  cancelled: "لغو",
  queue_changed: "تغییر نوبت",
  paid: "پرداخت",
  installment_paid: "پرداخت قسط",
  installment_unpaid: "لغو پرداخت قسط",
  settled: "تسویه",
  manual: "ثبت دستی واحد مالی",
};

export function LoanHistory({ item }) {
  if (!item.events?.length) return null;
  return (
    <Stack spacing={0.5} sx={{ mt: 1 }}>
      {item.events.map((e, i) => (
        <Typography key={i} variant="caption" color="text.secondary">
          {formatDateTime(e.created_at)} — {EVENT_LABELS[e.action] || e.action}
          {e.actor ? ` — ${e.actor}` : ""}
          {e.note ? `: ${e.note}` : ""}
        </Typography>
      ))}
    </Stack>
  );
}

