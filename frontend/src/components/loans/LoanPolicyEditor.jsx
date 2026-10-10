/**
 * ویرایشگر «مقررات وام» یک سایت (دیالوگ): عنوان، تاریخ اجرا، متن دستورالعمل، قانون تسویه، مسیر تأیید قابل چیدن،
 * قواعد اختیاری ضامن و جدول انواع وام. «واحد مالی» همیشه آخرین مرحله است.
 */
import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Grid,
  IconButton,
  MenuItem,
  Stack,
  Switch,
  TextField,
  Typography,
  useMediaQuery,
} from "@mui/material";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";
import ArrowDownwardIcon from "@mui/icons-material/ArrowDownward";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import AddIcon from "@mui/icons-material/Add";
import { gregorianToJalali } from "../../utils/jalaliDate";
import JalaliCalendarField from "../JalaliCalendarField";
import { AmountField, digitsOnly, errText } from "./LoanShared";

export const STEP_LABELS = {
  guarantors: "ضامن‌ها",
  unit_manager: "مدیر واحد (تأییدکننده‌ی مرخصی)",
  site_manager: "مدیر سایت",
  finance: "واحد مالی",
};
const OPTIONAL_STEPS = ["guarantors", "unit_manager", "site_manager"];

function todayJalali() {
  const { jy, jm, jd } = gregorianToJalali(new Date());
  return `${jy}/${String(jm).padStart(2, "0")}/${String(jd).padStart(2, "0")}`;
}

const EMPTY_TYPE = {
  title: "",
  max_amount: "",
  min_service_months: 0,
  guarantor_count: 0,
  extra_requirement: "",
  out_of_queue: false,
  is_active: true,
  // قواعد ضامنِ همین نوع (خالی = بدون محدودیت)
  guarantor_max_active: "",
  guarantor_min_service_months: "",
  guarantor_no_active_loan: false,
};

// نمونه‌ی آماده: دستورالعمل کارخانه ۱۴۰۵/۰۷/۱۵
export const FACTORY_TEMPLATE = {
  title: "دستورالعمل پرداخت وام",
  rules_text:
    "وام‌ها بدون بهره است.\nتا تسویه‌ی کامل وام قبلی، وام جدید پرداخت نمی‌شود.\nدر صورت ترک کار، باقیمانده‌ی وام از سنوات کسر می‌شود و ضامن‌ها مسئولیت تضامنی دارند.",
  block_if_unsettled: true,
  approval_steps: ["guarantors", "unit_manager", "site_manager", "finance"],
  types: [
    { ...EMPTY_TYPE, title: "نوع الف", max_amount: 400000000, min_service_months: 24, guarantor_count: 2, extra_requirement: "سفته به مبلغ ۴۰۰ میلیون ریال" },
    { ...EMPTY_TYPE, title: "نوع ب", max_amount: 200000000, min_service_months: 12, guarantor_count: 2 },
    { ...EMPTY_TYPE, title: "نوع ج (اضطراری)", max_amount: 100000000, min_service_months: 3, guarantor_count: 2, out_of_queue: true },
  ],
};

function initialForm(source) {
  const base = source || {};
  return {
    title: base.title || "",
    effective_from: base.effective_from && !base._copy ? base.effective_from : todayJalali(),
    rules_text: base.rules_text || "",
    block_if_unsettled: base.block_if_unsettled ?? true,
    approval_steps: base.approval_steps?.length ? base.approval_steps : ["guarantors", "unit_manager", "site_manager", "finance"],
    types: (base.types?.length ? base.types : [EMPTY_TYPE]).map((t) => ({
      ...EMPTY_TYPE,
      ...t,
      id: base._copy ? undefined : t.id,
      extra_requirement: t.extra_requirement || "",
      guarantor_max_active: t.guarantor_max_active ?? "",
      guarantor_min_service_months: t.guarantor_min_service_months ?? "",
      guarantor_no_active_loan: Boolean(t.guarantor_no_active_loan),
    })),
  };
}

/**
 * open، policy (برای ویرایش) یا source (برای نسخه‌ی جدید: کپی از یک مقررات یا نمونه؛ _copy=true)،
 * onSave(payload) که Promise برمی‌گرداند.
 */
export default function LoanPolicyEditor({ open, policy, source, onClose, onSave }) {
  const [form, setForm] = useState(() => initialForm(policy || source));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const fullScreen = useMediaQuery("(max-width:900px)");

  useEffect(() => {
    if (open) {
      setForm(initialForm(policy || source));
      setError("");
    }
  }, [open, policy, source]);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  const setType = (i, key, value) =>
    setForm((f) => ({ ...f, types: f.types.map((t, j) => (j === i ? { ...t, [key]: value } : t)) }));

  const steps = form.approval_steps.filter((s) => s !== "finance");
  const moveStep = (i, dir) => {
    const next = [...steps];
    [next[i], next[i + dir]] = [next[i + dir], next[i]];
    set("approval_steps", [...next, "finance"]);
  };
  const removeStep = (key) => set("approval_steps", [...steps.filter((s) => s !== key), "finance"]);
  const addStep = (key) => set("approval_steps", [...steps, key, "finance"]);

  const save = async () => {
    const needs = form.types.find((t) => t.is_active && Number(t.guarantor_count) > 0);
    if (needs && !form.approval_steps.includes("guarantors")) {
      setError(`نوع «${needs.title || "بی‌نام"}» ضامن می‌خواهد؛ مرحله‌ی «ضامن‌ها» را به مسیر تأیید اضافه کنید یا تعداد ضامن را صفر کنید.`);
      return;
    }
    setSaving(true);
    setError("");
    try {
      const toInt = (v) => (v === "" || v === null || v === undefined ? null : Number(digitsOnly(v)) || null);
      await onSave({
        ...form,
        types: form.types.map((t) => ({
          ...t,
          max_amount: Number(t.max_amount) || 0,
          min_service_months: Number(t.min_service_months) || 0,
          guarantor_count: Number(t.guarantor_count) || 0,
          extra_requirement: t.extra_requirement || null,
          guarantor_max_active: toInt(t.guarantor_max_active),
          guarantor_min_service_months: toInt(t.guarantor_min_service_months),
          guarantor_no_active_loan: Boolean(t.guarantor_no_active_loan),
        })),
      });
    } catch (e) {
      setError(errText(e, "ذخیره ناموفق بود"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} fullWidth maxWidth="md" fullScreen={fullScreen}>
      <DialogTitle>{policy ? "ویرایش مقررات وام" : "مقررات وام — نسخه‌ی جدید"}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={8}>
              <TextField label="عنوان" value={form.title} onChange={(e) => set("title", e.target.value)} fullWidth required />
            </Grid>
            <Grid item xs={12} sm={4}>
              <JalaliCalendarField
                label="تاریخ اجرا"
                value={form.effective_from}
                onChange={(v) => set("effective_from", v || todayJalali())}
                required
                clearable={false}
                size="medium"
                helperText="از این روز برای درخواست‌های جدید اجرا می‌شود"
              />
            </Grid>
          </Grid>
          <TextField
            label="متن دستورالعمل برای پرسنل"
            value={form.rules_text}
            onChange={(e) => set("rules_text", e.target.value)}
            multiline
            minRows={3}
            fullWidth
          />
          <FormControlLabel
            control={<Switch checked={form.block_if_unsettled} onChange={(e) => set("block_if_unsettled", e.target.checked)} />}
            label="تا تسویه‌ی کامل وام قبلی، درخواست وام جدید ممنوع"
          />

          <Box>
            <Typography fontWeight={800} sx={{ mb: 1 }}>
              مسیر تأیید
            </Typography>
            <Stack spacing={1}>
              {steps.map((key, i) => (
                <Stack key={key} direction="row" alignItems="center" spacing={1}>
                  <Chip label={`${(i + 1).toLocaleString("fa-IR")}. ${STEP_LABELS[key]}`} sx={{ flex: 1, justifyContent: "flex-start" }} />
                  <IconButton size="small" disabled={i === 0} onClick={() => moveStep(i, -1)} aria-label="بالا">
                    <ArrowUpwardIcon fontSize="small" />
                  </IconButton>
                  <IconButton size="small" disabled={i === steps.length - 1} onClick={() => moveStep(i, 1)} aria-label="پایین">
                    <ArrowDownwardIcon fontSize="small" />
                  </IconButton>
                  <IconButton size="small" color="error" onClick={() => removeStep(key)} aria-label="حذف">
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </Stack>
              ))}
              <Chip
                color="primary"
                variant="outlined"
                label={`${(steps.length + 1).toLocaleString("fa-IR")}. ${STEP_LABELS.finance} (همیشه آخر: مبلغ و اقساط)`}
                sx={{ justifyContent: "flex-start" }}
              />
              {OPTIONAL_STEPS.filter((k) => !steps.includes(k)).map((k) => (
                <Button key={k} size="small" startIcon={<AddIcon />} onClick={() => addStep(k)} sx={{ alignSelf: "flex-start" }}>
                  افزودن مرحله‌ی {STEP_LABELS[k]}
                </Button>
              ))}
            </Stack>
            <Typography variant="caption" color="text.secondary">
              اگر مدیر واحد و مدیر سایت یک نفر باشند، یک بار تأیید می‌کند. مرحله‌ی ضامن برای نوع وامی که ضامن نمی‌خواهد خودکار رد می‌شود.
            </Typography>
          </Box>

          <Box>
            <Typography fontWeight={800} sx={{ mb: 1 }}>
              انواع وام
            </Typography>
            <Stack spacing={1.5}>
              {form.types.map((t, i) => (
                <Card key={t.id ?? `n${i}`} variant="outlined">
                  <CardContent>
                    <Grid container spacing={1.5} alignItems="center">
                      <Grid item xs={12} sm={4}>
                        <TextField label="عنوان" value={t.title} onChange={(e) => setType(i, "title", e.target.value)} fullWidth size="small" />
                      </Grid>
                      <Grid item xs={12} sm={4}>
                        <AmountField
                          label="سقف مبلغ (ریال)"
                          value={t.max_amount}
                          onChange={(v) => setType(i, "max_amount", v)}
                          fullWidth
                          size="small"
                        />
                      </Grid>
                      <Grid item xs={6} sm={2}>
                        <TextField
                          label="حداقل سابقه (ماه)"
                          value={t.min_service_months}
                          onChange={(e) => setType(i, "min_service_months", digitsOnly(e.target.value))}
                          fullWidth
                          size="small"
                        />
                      </Grid>
                      <Grid item xs={6} sm={2}>
                        <TextField
                          select
                          label="تعداد ضامن"
                          value={Number(t.guarantor_count) || 0}
                          onChange={(e) => setType(i, "guarantor_count", e.target.value)}
                          fullWidth
                          size="small"
                        >
                          {[0, 1, 2, 3, 4, 5].map((n) => (
                            <MenuItem key={n} value={n}>
                              {n.toLocaleString("fa-IR")}
                            </MenuItem>
                          ))}
                        </TextField>
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <TextField
                          label="مدرک اضافه (اختیاری؛ مالی هنگام پرداخت تأیید می‌کند)"
                          value={t.extra_requirement}
                          onChange={(e) => setType(i, "extra_requirement", e.target.value)}
                          fullWidth
                          size="small"
                          placeholder="مثلاً: سفته به مبلغ ۴۰۰ میلیون ریال"
                        />
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <Stack direction="row" alignItems="center" flexWrap="wrap" useFlexGap>
                          <FormControlLabel
                            control={<Switch checked={t.out_of_queue} onChange={(e) => setType(i, "out_of_queue", e.target.checked)} />}
                            label="خارج از نوبت"
                          />
                          <FormControlLabel
                            control={<Switch checked={t.is_active} onChange={(e) => setType(i, "is_active", e.target.checked)} />}
                            label="فعال"
                          />
                          <IconButton
                            color="error"
                            disabled={form.types.length === 1}
                            onClick={() => set("types", form.types.filter((_, j) => j !== i))}
                            aria-label="حذف نوع"
                          >
                            <DeleteOutlineIcon />
                          </IconButton>
                        </Stack>
                      </Grid>
                      {Number(t.guarantor_count) > 0 && (
                        <>
                          <Grid item xs={12}>
                            <Typography variant="body2" fontWeight={700}>
                              قواعد ضامنِ این نوع (اختیاری — خالی یعنی بدون محدودیت)
                            </Typography>
                          </Grid>
                          <Grid item xs={6} sm={4}>
                            <TextField
                              label="حداکثر ضمانت هم‌زمان هر نفر"
                              value={t.guarantor_max_active}
                              onChange={(e) => setType(i, "guarantor_max_active", digitsOnly(e.target.value).slice(0, 4))}
                              fullWidth
                              size="small"
                            />
                          </Grid>
                          <Grid item xs={6} sm={4}>
                            <TextField
                              label="حداقل سابقه‌ی ضامن (ماه)"
                              value={t.guarantor_min_service_months}
                              onChange={(e) => setType(i, "guarantor_min_service_months", digitsOnly(e.target.value).slice(0, 4))}
                              fullWidth
                              size="small"
                            />
                          </Grid>
                          <Grid item xs={12} sm={4}>
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={t.guarantor_no_active_loan}
                                  onChange={(e) => setType(i, "guarantor_no_active_loan", e.target.checked)}
                                />
                              }
                              label="ضامن خودش وام تسویه‌نشده نداشته باشد"
                            />
                          </Grid>
                        </>
                      )}
                    </Grid>
                  </CardContent>
                </Card>
              ))}
              <Button startIcon={<AddIcon />} onClick={() => set("types", [...form.types, { ...EMPTY_TYPE }])} sx={{ alignSelf: "flex-start" }}>
                افزودن نوع وام
              </Button>
            </Stack>
          </Box>
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          انصراف
        </Button>
        <Button variant="contained" onClick={save} disabled={saving}>
          ذخیره
        </Button>
      </DialogActions>
    </Dialog>
  );
}
