// نوشتن نامه (ظاهر شبیه ایمیل): گیرنده/رونوشت، موضوع، گزینه‌ها (فوریت، محرمانگی، قالب، کاغذ، نیاز به اقدام)، متن (TipTap)،
// پیوست‌ها زیر متن و نوار پایین با «ارسال»؛ ذخیره‌ی خودکار، پیش‌نمایش صفحه‌ای A4/A5 و چاپ.
// قفل خوش‌بینانه: اگر همین پیش‌نویس در تب/دستگاه دیگری ذخیره شده باشد سرور 409 می‌دهد و ذخیره‌ی خودکار متوقف می‌شود.
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  InputBase,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import PrintOutlinedIcon from "@mui/icons-material/PrintOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import SendOutlinedIcon from "@mui/icons-material/SendOutlined";
import { discardDraft, fetchComposeOptions, fetchDraft, fetchMySignatureBlob, saveDraft, sendDraft, submitForApproval } from "../api/automationLetters";
import ApprovalPathEditor from "../components/oa/ApprovalPathEditor";
import useBlobUrl from "../components/oa/useBlobUrl";
import { AttachButton, AttachmentChips, RecipientRow, useDraftExtras } from "../components/oa/DraftExtras";
import LetterEditor from "../components/oa/LetterEditor";
import LetterPreview from "../components/oa/LetterPreview";
import LetterPrint from "../components/oa/LetterPrint";
import { toPersianDigits } from "../utils/searchText";
import { oaToJalali, oaJalaliEndOfDay } from "../utils/oaDates";
import JalaliCalendarField from "../components/JalaliCalendarField";

const AUTOSAVE_MS = 3000;
const toJalaliInput = oaToJalali;
const jalaliToIso = oaJalaliEndOfDay;

const selectSx = { minWidth: 110, "& .MuiInput-root": { fontSize: 14 } };

function formFrom(d) {
  return {
    requires_action: Boolean(d.requires_action),
    action_due: toJalaliInput(d.action_due_at),
    subject: d.subject || "",
    body_html: d.body_html || "",
    paper_size: d.paper_size,
    template_id: d.template_id || "",
    urgency: d.urgency,
    confidentiality: d.confidentiality,
    principal_employee_id: d.principal_employee_id || "", // «از طرف» (منشی)؛ خالی = خودم
    sign_on_send: Boolean(d.sign_on_send),
  };
}

export default function OaDraftEditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [draft, setDraft] = useState(null); // آخرین پاسخ سرور (چیدمان، row_version، …)
  const [form, setForm] = useState(null);
  const [options, setOptions] = useState(null);
  const [error, setError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveState, setSaveState] = useState(null); // { ok, message }
  const [conflict, setConflict] = useState(false);
  const [conflictBackupOpen, setConflictBackupOpen] = useState(false);
  const [pages, setPages] = useState(1);
  const [segments, setSegments] = useState(null); // شکست صفحه‌های پیش‌نمایش، برای چاپ یکسان
  const handlePages = useCallback((n, segs) => {
    setPages(n);
    setSegments(segs);
  }, []);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [extras, setExtras] = useState({ recipients: [], attachments: [], attachment_limits: null });
  const [confirmSend, setConfirmSend] = useState(false);
  const [sending, setSending] = useState(false);
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [approvalError, setApprovalError] = useState(false);
  const approvalBusyRef = useRef(false);
  const [sendError, setSendError] = useState("");
  const [numberingError, setNumberingError] = useState("");
  const [hasSignature, setHasSignature] = useState(false);
  const [approvalPlan, setApprovalPlan] = useState({ steps: [], auto_final: null, history: [] });
  const mySignatureUrl = useBlobUrl(hasSignature ? "my-signature" : null, () => fetchMySignatureBlob()); // پیشوند دبیرخانه‌ی سایت تعیین نشده → ارسال ممکن نیست
  const formRef = useRef(null);
  const savingRef = useRef(false); // دو ذخیره‌ی هم‌زمان با یک row_version به 409 کاذب می‌رسید
  const draftRef = useRef(null);
  formRef.current = form;
  draftRef.current = draft;

  useEffect(() => {
    Promise.all([fetchDraft(id), fetchComposeOptions()])
      .then(([d, o]) => {
        if (d.status !== "draft") {
          navigate(`/automation/letters/${d.id}`, { replace: true }); // قبلاً ارسال شده
          return;
        }
        setDraft(d);
        setForm(formFrom(d));
        setExtras({
          recipients: d.recipients || [],
          attachments: d.attachments || [],
          attachment_limits: d.attachment_limits,
          relations: d.relations || [],
        });
        setNumberingError(d.numbering_error || "");
        setHasSignature(Boolean(d.has_signature));
        setApprovalPlan(d.approval_plan || { steps: [], auto_final: null, history: [] });
        setOptions(o);
      })
      .catch((err) => setError(err.response?.data?.detail || "پیش‌نویس پیدا نشد."));
  }, [id]);

  const doSave = useCallback(async () => {
    const f = formRef.current;
    const d = draftRef.current;
    if (!f || !d || conflict) return false;
    if (savingRef.current) {
      return false;
    }
    savingRef.current = true;
    setSaving(true);
    try {
      const { action_due: due, ...rest } = f;
      const updated = await saveDraft(d.id, {
        ...rest,
        template_id: f.template_id ? Number(f.template_id) : null,
        principal_employee_id: f.principal_employee_id ? Number(f.principal_employee_id) : null,
        action_due_at: f.requires_action && due ? jalaliToIso(due) : null,
        row_version: d.row_version,
      });
      draftRef.current = updated;
      setDraft(updated); // متن محلی جایگزین نمی‌شود تا مکان‌نما نپرد؛ پاک‌سازی سرور در نمایش بعدی اعمال است
      setDirty(formRef.current !== f);
      setSaveState({ ok: true, message: `ذخیره شد — ${new Date().toLocaleTimeString("fa-IR")}` });
      return true;
    } catch (err) {
      if (err.response?.status === 409) setConflict(true);
      setSaveState({ ok: false, message: err.response?.data?.detail || "ذخیره ناموفق بود؛ دوباره امتحان کنید." });
      return false;
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }, [conflict]);

  // ذخیره‌ی خودکار چند ثانیه بعد از آخرین تغییر
  useEffect(() => {
    if (!dirty || conflict || saving) return undefined;
    const t = setTimeout(doSave, AUTOSAVE_MS);
    return () => clearTimeout(t);
  }, [form, dirty, conflict, saving, doSave]);

  // هشدار بستن صفحه با تغییر ذخیره‌نشده + Ctrl+S
  useEffect(() => {
    const onBeforeUnload = (e) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        if (!conflict) doSave();
      }
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      window.removeEventListener("keydown", onKey);
    };
  }, [dirty, conflict, doSave]);

  useEffect(() => {
    if (!dirty) return undefined;
    const protectLinks = (event) => {
      const anchor = event.target?.closest?.("a[href]");
      if (!anchor || event.defaultPrevented || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const target = new URL(anchor.href, window.location.href);
      if (target.origin !== window.location.origin || target.pathname === window.location.pathname) return;
      if (!window.confirm("تغییرات ذخیره‌نشده دارید. بدون ذخیره خارج شوید؟")) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    document.addEventListener("click", protectLinks, true);
    return () => document.removeEventListener("click", protectLinks, true);
  }, [dirty]);

  function update(patch, { saveNow = false } = {}) {
    // Update the ref immediately: a save scheduled in the same tick must see the
    // newly selected template, paper size or principal (not the previous render).
    const next = { ...formRef.current, ...patch };
    formRef.current = next;
    setForm(next);
    setDirty(true);
    // قالب و اندازه‌ی کاغذ چیدمان پیش‌نمایش را عوض می‌کنند؛ فوراً ذخیره می‌شود تا چیدمان تازه از سرور برسد
    if (saveNow) setTimeout(doSave, 0);
  }

  const api = useDraftExtras(draft?.id, extras, setExtras);
  const templates = options?.templates || [];
  const lockedUI = conflict || sending;
  const submissionBlocked = lockedUI || saving || api.busy || approvalBusy || approvalError || Boolean(api.error);
  const needsApproval = approvalPlan.steps.length > 0 || Boolean(approvalPlan.auto_final);

  async function handleSend() {
    if (sending) return;
    setSending(true);
    setSendError("");
    try {
      if (approvalBusyRef.current || approvalError) throw new Error("ذخیره مسیر تأیید هنوز کامل نشده است.");
      // No final send until every recipient / attachment mutation has finished successfully.
      await api.awaitIdle();
      while (savingRef.current) await new Promise((r) => setTimeout(r, 60));
      const saved = await doSave();
      if (!saved || conflict) throw new Error("آخرین تغییرات ذخیره نشدند. نامه ارسال نشد؛ دوباره ذخیره کنید.");
      await api.awaitIdle();
      if (approvalBusyRef.current || approvalError) throw new Error("مسیر تأیید ذخیره نشده است.");
      const res = needsApproval
        ? await submitForApproval(draftRef.current.id, draftRef.current.row_version)
        : await sendDraft(draftRef.current.id, draftRef.current.row_version);
      setDirty(false);
      navigate(`/automation/letters/${res.letter_id}`, { replace: true });
    } catch (err) {
      setSendError(err.response?.data?.detail || err.message || "ارسال ناموفق بود.");
      setSending(false);
    }
  }

  async function handleDiscard() {
    try {
      await discardDraft(draft.id);
      setDirty(false);
      navigate("/automation/drafts");
    } catch (err) {
      setSaveState({ ok: false, message: err.response?.data?.detail || "حذف ناموفق بود." });
      setConfirmDiscard(false);
    }
  }

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!draft || !form || !options) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  const previewPaper = draft.paper_size;
  // مسیر تأیید (یا نامه‌ی «از طرف» مدیر که امضای او خودکار است) → «ارسال برای تأیید»
  // پیش‌نمایش امضا: فقط امضای خود نویسنده و فقط وقتی «امضا شود» زده شده و نامه به نام خودش است
  const willSign = form.sign_on_send && draft.has_signature && !form.principal_employee_id;
  const previewSignature = willSign ? { name: draft.signer_name, title: draft.signer_title, imageUrl: mySignatureUrl } : null; // چیدمان از سرور برای همین اندازه آمده است

  return (
    <Box>

      <Stack direction="row" alignItems="center" gap={1} sx={{ mb: 2, minWidth: 0 }}>
        <IconButton aria-label="بازگشت به پیش‌نویس‌ها" onClick={() => {
          if (dirty && !window.confirm("تغییرات ذخیره‌نشده دارید. بدون ذخیره خارج شوید؟")) return;
          navigate("/automation/drafts");
        }}><ArrowForwardIcon /></IconButton>
        <Typography variant="h6" fontWeight={700} title={form.subject || "نامه‌ی جدید"} sx={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {form.subject || "نامه‌ی جدید"}
        </Typography>
      </Stack>

      {conflict && (
        <Alert severity="error" sx={{ mb: 2 }} action={
          <Button color="inherit" onClick={() => setConflictBackupOpen(true)}>برداشتن نسخه‌ی متن من</Button>
        }>
          این پیش‌نویس در تب یا دستگاه دیگری تغییر کرده است. ذخیره متوقف شده است. قبل از دریافت نسخه‌ی جدید، متن فعلی خود را در پنجره‌ی کناری کپی کنید.
        </Alert>
      )}
      {saveState?.ok === false && !conflict && <Alert severity="error" sx={{ mb: 2 }}>{saveState.message}</Alert>}
      {numberingError && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {numberingError}؛ تا تعیین آن، نامه ذخیره می‌شود ولی ارسال نمی‌شود. (مسئول تنظیمات اتوماسیون ← دبیرخانه و شماره)
        </Alert>
      )}
      {extras.relations?.length > 0 && (
        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 2 }}>
          {extras.relations.map((r, i) => (
            <Chip
              key={i}
              variant="outlined"
              color="primary"
              label={`${r.label}: ${r.subject || "نامه‌ی مرجع"}`}
              onClick={r.letter_id ? () => window.open(`/automation/letters/${r.letter_id}`, "_blank") : undefined}
            />
          ))}
        </Stack>
      )}
      {draft.template_outdated && (
        <Alert severity="info" sx={{ mb: 2 }}>
          قالب «{draft.template_name}» بعد از ساخت این پیش‌نویس تغییر کرده است؛ با ذخیره‌ی بعدی نسخه‌ی تازه‌ی قالب اعمال می‌شود.
        </Alert>
      )}

      <Stack direction={{ xs: "column", lg: "row" }} spacing={3} alignItems="flex-start">
        {/* کارت نوشتن نامه، شبیه پنجره‌ی نوشتن ایمیل */}
        <Card variant="outlined" sx={{ flex: { lg: "1 1 0" }, minWidth: 0, width: "100%", borderRadius: 3, bgcolor: "background.paper" }}>
          {options.principals?.length > 0 && (
            <Stack direction="row" alignItems="center" gap={1.5} sx={{ px: 2, py: 1, borderBottom: 1, borderColor: "divider" }}>
              <Typography variant="body2" color="text.secondary" sx={{ minWidth: 56 }}>از طرف</Typography>
              <TextField
                select
                variant="standard"
                size="small"
                value={form.principal_employee_id}
                onChange={(e) => {
                  const pid = e.target.value;
                  update({ principal_employee_id: pid }, { saveNow: true });
                  // امضای خود مدیر خودکار آخر مسیر تأیید است
                  const p = options.principals.find((x) => x.employee_id === pid);
                  setApprovalPlan((plan) => ({
                    ...plan,
                    steps: plan.steps.filter((st) => st.employee_id !== pid),
                    auto_final: p ? { employee_id: p.employee_id, name: p.name, title: p.title, kind: "sign", required: true } : null,
                  }));
                }}
                disabled={lockedUI}
                sx={{ minWidth: 220, "& .MuiInput-root": { fontSize: 14 } }}
                SelectProps={{ displayEmpty: true }}
              >
                <MenuItem value="">خودم</MenuItem>
                {options.principals.map((p) => (
                  <MenuItem key={p.employee_id} value={p.employee_id}>
                    {p.name}{p.title ? ` — ${p.title}` : ""}
                  </MenuItem>
                ))}
              </TextField>
              {form.principal_employee_id && (
                <Typography variant="caption" color="text.secondary">نامه به نام ایشان ارسال می‌شود</Typography>
              )}
            </Stack>
          )}
          <RecipientRow
            label="گیرنده"
            role="to"
            extras={extras}
            api={api}
            disabled={lockedUI}
          />
          <RecipientRow label="رونوشت" role="cc" extras={extras} api={api} disabled={lockedUI} />
          <Box sx={{ px: 2, borderBottom: 1, borderColor: "divider" }}>
            <InputBase
              fullWidth
              placeholder="موضوع"
              value={form.subject}
              onChange={(e) => update({ subject: e.target.value })}
              inputProps={{ maxLength: 300 }}
              disabled={lockedUI}
              sx={{ py: 1.25, fontSize: 15 }}
            />
          </Box>
          <Stack direction="row" flexWrap="wrap" alignItems="flex-end" columnGap={2.5} rowGap={2} sx={{ px: 2, pt: 1.5, pb: 2, borderBottom: 1, borderColor: "divider" }}>
            <TextField select variant="standard" size="small" label="فوریت" value={form.urgency} onChange={(e) => update({ urgency: e.target.value })} disabled={lockedUI} sx={selectSx}>
              {Object.entries(options.urgencies).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
            <TextField select variant="standard" size="small" label="محرمانگی" value={form.confidentiality} onChange={(e) => update({ confidentiality: e.target.value })} disabled={lockedUI} sx={selectSx}>
              {Object.entries(options.confidentiality).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
            <TextField select variant="standard" size="small" label="قالب" value={form.template_id} onChange={(e) => update({ template_id: e.target.value }, { saveNow: true })} sx={{ ...selectSx, minWidth: 150 }} disabled={lockedUI}>
              <MenuItem value="">بدون قالب</MenuItem>
              {templates.map((t) => <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>)}
            </TextField>
            <TextField select variant="standard" size="small" label="کاغذ" value={form.paper_size} onChange={(e) => update({ paper_size: e.target.value }, { saveNow: true })} sx={{ ...selectSx, minWidth: 70 }} disabled={lockedUI}>
              <MenuItem value="A4">A4</MenuItem>
              <MenuItem value="A5">A5</MenuItem>
            </TextField>
            <FormControlLabel
              control={<Checkbox size="small" color="error" checked={form.requires_action} disabled={lockedUI} onChange={(e) => update({ requires_action: e.target.checked })} />}
              label={<Typography variant="body2" color="error.main" fontWeight={600}>نیاز به اقدام از سمت گیرنده</Typography>}
              sx={{ m: 0 }}
            />
            <Tooltip
              title={
                !draft.has_signature
                  ? "امضای فعال ندارید (اتوماسیون اداری ← امضای من)"
                  : form.principal_employee_id
                    ? "نامه‌ای که از طرف دیگری ارسال می‌شود با امضای شما امضا نمی‌شود"
                    : ""
              }
            >
              <FormControlLabel
                control={
                  <Checkbox
                    size="small"
                    checked={Boolean(willSign)}
                    disabled={!draft.has_signature || Boolean(form.principal_employee_id) || lockedUI}
                    onChange={(e) => update({ sign_on_send: e.target.checked })}
                  />
                }
                label={<Typography variant="body2">امضا شود</Typography>}
                sx={{ m: 0 }}
              />
            </Tooltip>
            {form.requires_action && (
              <Box sx={{ width: 190, pointerEvents: lockedUI ? "none" : "auto", opacity: lockedUI ? 0.6 : 1 }}>
                <JalaliCalendarField
                  label="مهلت اقدام (اختیاری)"
                  value={form.action_due}
                  onChange={(v) => update({ action_due: v })}
                />
              </Box>
            )}
          </Stack>
          <LetterEditor value={form.body_html} onChange={(html) => update({ body_html: html })} disabled={lockedUI} bare />
          <AttachmentChips extras={extras} api={api} disabled={lockedUI} />
          <ApprovalPathEditor
            letterId={draft.id} plan={approvalPlan} onChange={setApprovalPlan} disabled={lockedUI}
            onBusyChange={(busy) => { approvalBusyRef.current = busy; setApprovalBusy(busy); }}
            onErrorChange={setApprovalError}
          />
          {api.error && <Alert severity="error" sx={{ mx: 2, mb: 1, whiteSpace: "pre-wrap" }} onClose={() => api.setError("")}>{api.error}</Alert>}
          {/* نوار پایین مثل ایمیل: ارسال، پیوست، چاپ، وضعیت ذخیره، حذف */}
          <Box sx={{
            display: "grid", alignItems: "center", gap: { xs: 0.5, sm: 1 },
            gridTemplateColumns: { xs: "minmax(0, 1fr) 40px 40px 40px", sm: "max-content 40px 40px minmax(0, 1fr) 40px" },
            px: { xs: 1, sm: 2 }, py: 1.25, borderTop: 1, borderColor: "divider", minWidth: 0,
          }}>
            <Button
              variant="contained"
              startIcon={<SendOutlinedIcon />}
              onClick={() => { setSendError(""); setConfirmSend(true); }}
              disabled={submissionBlocked || Boolean(numberingError) || !extras.recipients.some((r) => r.role === "to")}
              sx={{ height: 40, borderRadius: 5, px: { xs: 1.5, sm: 3 }, flexShrink: 0, whiteSpace: "nowrap" }}
            >
              {needsApproval ? "ارسال برای تأیید" : "ارسال"}
            </Button>
            <AttachButton extras={extras} api={api} disabled={lockedUI} />
            <Tooltip title="چاپ">
              <span>
                <IconButton onClick={() => window.print()} disabled={dirty}><PrintOutlinedIcon /></IconButton>
              </span>
            </Tooltip>
            <Typography variant="caption" color={saveState?.ok === false ? "error" : "text.secondary"}
              sx={{ minWidth: 0, gridRow: { xs: 2, sm: "auto" }, gridColumn: { xs: "1 / -1", sm: "auto" } }} noWrap>
              {saving ? "در حال ذخیره..." : dirty ? "تغییر ذخیره‌نشده" : saveState?.message || "پیش‌نویس خودکار ذخیره می‌شود"}
            </Typography>
            <Tooltip title="حذف پیش‌نویس">
              <IconButton onClick={() => setConfirmDiscard(true)} disabled={submissionBlocked} aria-label="حذف پیش‌نویس"><DeleteOutlineIcon /></IconButton>
            </Tooltip>
          </Box>
        </Card>

        <Card variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: "action.hover", flex: { lg: "1 1 0" }, minWidth: 0, width: "100%", position: { lg: "sticky" }, top: { lg: 16 } }}>
          <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
            پیش‌نمایش — کاغذ <bdi dir="ltr">{previewPaper}</bdi>، {toPersianDigits(pages)} صفحه
          </Typography>
          {previewPaper === "A5" && pages > 1 && (
            <Alert
              severity="warning"
              sx={{ mb: 1.5 }}
              action={<Button color="inherit" size="small" onClick={() => update({ paper_size: "A4" }, { saveNow: true })}>A4 شود</Button>}
            >
              متن در A5 بیش از یک صفحه شد؛ برای این نامه A4 مناسب‌تر است.
            </Alert>
          )}
          <LetterPreview
            paper={previewPaper}
            layout={draft.layout}
            subject={form.subject}
            bodyHtml={form.body_html}
            fit
            onPages={handlePages}
            siteName={draft.site_name}
            signature={previewSignature}
          />
        </Card>
      </Stack>

      <LetterPrint paper={previewPaper} layout={draft.layout} subject={form.subject} bodyHtml={form.body_html} segments={segments} siteName={draft.site_name} signature={previewSignature} />

      <Dialog open={confirmSend} onClose={() => !sending && setConfirmSend(false)} fullWidth maxWidth="xs">
        <DialogTitle>{needsApproval ? "ارسال برای تأیید" : "ارسال نامه"}</DialogTitle>
        <DialogContent>
          <Typography sx={{ mb: 1 }}>
            «{form.subject || "بدون موضوع"}» برای {toPersianDigits(extras.recipients.filter((r) => r.role === "to").length)} گیرنده
            {extras.recipients.some((r) => r.role === "cc")
              ? ` و ${toPersianDigits(extras.recipients.filter((r) => r.role === "cc").length)} رونوشت`
              : ""}{" "}
            ارسال شود؟
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {draft.principal_name ? `نامه به نام «${draft.principal_name}» ارسال می‌شود و در گردش نوشته می‌شود که شما (منشی) فرستاده‌اید. ` : ""}
            {form.requires_action ? "از گیرنده‌ی اصلی اقدام خواسته می‌شود. " : "فقط برای اطلاع گیرنده (بدون نیاز به اقدام). "}
            {needsApproval
              ? `نامه به ترتیب برای ${toPersianDigits(approvalPlan.steps.length + (approvalPlan.auto_final ? 1 : 0))} نفر مسیر تأیید فرستاده می‌شود و بعد از آخرین تأیید، خودکار شماره می‌گیرد و برای گیرندگان ارسال می‌شود. تا وقتی در انتظار تأیید است متن قفل است؛ با «پس گرفتن» یا «برگشت برای اصلاح» دوباره قابل ویرایش می‌شود.`
              : "هنگام ارسال شماره و تاریخ رسمی از دبیرخانه گرفته می‌شود. بعد از ارسال، متن و گیرندگان قابل تغییر نیستند."}
            {form.confidentiality === "confidential" ? " این نامه محرمانه است و فقط گیرندگان و افرادی که به آن‌ها ارجاع شود آن را می‌بینند." : ""}
          </Typography>
          {sendError && <Alert severity="error" sx={{ mt: 2 }}>{sendError}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmSend(false)} disabled={sending}>انصراف</Button>
          <Button variant="contained" color="success" onClick={handleSend} disabled={submissionBlocked}>
            {sending ? "در حال ارسال..." : needsApproval ? "ارسال برای تأیید" : "ارسال"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={conflictBackupOpen} onClose={() => setConflictBackupOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>نگهداری متن فعلی شما</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            این متن هنوز روی سرور ذخیره نشده است. آن را کپی و در جای امن نگهداری کنید، سپس نسخه‌ی جدید پیش‌نویس را دریافت کنید.
          </Typography>
          <TextField label="موضوع" fullWidth value={form.subject} InputProps={{ readOnly: true }} sx={{ mb: 2 }} />
          <TextField label="متن نامه (HTML)" fullWidth multiline minRows={8} maxRows={15}
            value={form.body_html} InputProps={{ readOnly: true }} helperText="برای حفظ قالب‌بندی، متن کامل HTML را کپی کنید." />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConflictBackupOpen(false)}>بستن</Button>
          <Button variant="contained" onClick={() => {
            const text = `موضوع: ${form.subject}\n\n${form.body_html}`;
            navigator.clipboard?.writeText(text).catch(() => setSaveState({ ok: false, message: "کپی خودکار انجام نشد؛ متن را دستی انتخاب و کپی کنید." }));
          }}>کپی متن</Button>
          <Button color="warning" onClick={() => {
            if (window.confirm("از کپی متن فعلی خود مطمئن هستید؟ با دریافت نسخه جدید، تغییرات ذخیره‌نشده جایگزین می‌شوند.")) window.location.reload();
          }}>دریافت نسخه جدید</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={confirmDiscard} onClose={() => setConfirmDiscard(false)}>
        <DialogTitle>حذف پیش‌نویس</DialogTitle>
        <DialogContent>
          <Typography>این پیش‌نویس حذف شود؟</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDiscard(false)}>انصراف</Button>
          <Button color="error" variant="contained" onClick={handleDiscard}>
            حذف
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
