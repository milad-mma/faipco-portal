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
import { discardDraft, fetchComposeOptions, fetchDraft, saveDraft, sendDraft } from "../api/automationLetters";
import { AttachButton, AttachmentChips, RecipientRow, useDraftExtras } from "../components/oa/DraftExtras";
import LetterEditor from "../components/oa/LetterEditor";
import LetterPreview from "../components/oa/LetterPreview";
import LetterPrint from "../components/oa/LetterPrint";
import { toPersianDigits } from "../utils/searchText";
import { gregorianToJalali, jalaliToGregorian } from "../utils/jalaliDate";
import JalaliCalendarField from "../components/JalaliCalendarField";

const AUTOSAVE_MS = 3000;

// تاریخ سرور ↔ رشته‌ی شمسی «YYYY/MM/DD» فیلد تقویم؛ مهلت = پایان همان روز (۲۳:۵۹ به وقت مرورگر)
const pad2 = (n) => String(n).padStart(2, "0");
function toJalaliInput(iso) {
  if (!iso) return null;
  const { jy, jm, jd } = gregorianToJalali(new Date(iso));
  return `${jy}/${pad2(jm)}/${pad2(jd)}`;
}
function jalaliToIso(value) {
  const m = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/.exec(value || "");
  return m ? jalaliToGregorian(Number(m[1]), Number(m[2]), Number(m[3]), 23, 59).toISOString() : null;
}

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
  const [sendError, setSendError] = useState("");
  const formRef = useRef(null);
  const savingRef = useRef(false); // دو ذخیره‌ی هم‌زمان با یک row_version به 409 کاذب می‌رسید
  const againRef = useRef(false);
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
        setOptions(o);
      })
      .catch((err) => setError(err.response?.data?.detail || "پیش‌نویس پیدا نشد."));
  }, [id]);

  const doSave = useCallback(async () => {
    const f = formRef.current;
    const d = draftRef.current;
    if (!f || !d) return;
    if (savingRef.current) {
      againRef.current = true; // بعد از تمام شدن ذخیره‌ی فعلی دوباره ذخیره می‌شود
      return;
    }
    savingRef.current = true;
    setSaving(true);
    try {
      const { action_due: due, ...rest } = f;
      const updated = await saveDraft(d.id, {
        ...rest,
        template_id: f.template_id ? Number(f.template_id) : null,
        action_due_at: f.requires_action && due ? jalaliToIso(due) : null,
        row_version: d.row_version,
      });
      draftRef.current = updated;
      setDraft(updated); // متن محلی جایگزین نمی‌شود تا مکان‌نما نپرد؛ پاک‌سازی سرور در نمایش بعدی اعمال است
      setDirty(formRef.current !== f);
      setSaveState({ ok: true, message: `ذخیره شد — ${new Date().toLocaleTimeString("fa-IR")}` });
    } catch (err) {
      if (err.response?.status === 409) setConflict(true);
      setSaveState({ ok: false, message: err.response?.data?.detail || "ذخیره ناموفق بود؛ دوباره امتحان کنید." });
    } finally {
      savingRef.current = false;
      setSaving(false);
      if (againRef.current) {
        againRef.current = false;
        setTimeout(() => doSaveRef.current?.(), 0);
      }
    }
  }, []);
  const doSaveRef = useRef(null);
  doSaveRef.current = doSave;

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

  function update(patch, { saveNow = false } = {}) {
    setForm((f) => ({ ...f, ...patch }));
    setDirty(true);
    // قالب و اندازه‌ی کاغذ چیدمان پیش‌نمایش را عوض می‌کنند؛ فوراً ذخیره می‌شود تا چیدمان تازه از سرور برسد
    if (saveNow) setTimeout(doSave, 0);
  }

  const api = useDraftExtras(draft?.id, extras, setExtras);
  const templates = options?.templates || [];
  const lockedUI = conflict || sending;

  async function handleSend() {
    setSending(true);
    setSendError("");
    try {
      // آخرین متن اول ذخیره شود (اگر ذخیره‌ی خودکاری در جریان است، منتظر می‌مانیم)
      while (savingRef.current) await new Promise((r) => setTimeout(r, 100));
      await doSave();
      const res = await sendDraft(draftRef.current.id, draftRef.current.row_version);
      setDirty(false);
      navigate(`/automation/letters/${res.letter_id}`, { replace: true });
    } catch (err) {
      setSendError(err.response?.data?.detail || "ارسال ناموفق بود.");
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

  const previewPaper = draft.paper_size; // چیدمان از سرور برای همین اندازه آمده است

  return (
    <Box>

      <Stack direction="row" alignItems="center" gap={1} sx={{ mb: 2 }}>
        <IconButton onClick={() => navigate("/automation/drafts")}><ArrowForwardIcon /></IconButton>
        <Typography variant="h6" fontWeight={700} sx={{ flex: 1, minWidth: 0 }} noWrap>
          {form.subject || "نامه‌ی جدید"}
        </Typography>
      </Stack>

      {conflict && (
        <Alert severity="error" sx={{ mb: 2 }} action={<Button color="inherit" onClick={() => window.location.reload()}>تازه کردن</Button>}>
          این پیش‌نویس در تب یا دستگاه دیگری تغییر کرده است. برای جلوگیری از پاک شدن آن تغییرها، ذخیره متوقف شد. صفحه را تازه کنید.
        </Alert>
      )}
      {saveState?.ok === false && !conflict && <Alert severity="error" sx={{ mb: 2 }}>{saveState.message}</Alert>}
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
              sx={{ py: 1.25, fontSize: 15 }}
            />
          </Box>
          <Stack direction="row" flexWrap="wrap" alignItems="flex-end" columnGap={2.5} rowGap={2} sx={{ px: 2, pt: 1.5, pb: 2, borderBottom: 1, borderColor: "divider" }}>
            <TextField select variant="standard" size="small" label="فوریت" value={form.urgency} onChange={(e) => update({ urgency: e.target.value })} sx={selectSx}>
              {Object.entries(options.urgencies).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
            <TextField select variant="standard" size="small" label="محرمانگی" value={form.confidentiality} onChange={(e) => update({ confidentiality: e.target.value })} sx={selectSx}>
              {Object.entries(options.confidentiality).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </TextField>
            <TextField select variant="standard" size="small" label="قالب" value={form.template_id} onChange={(e) => update({ template_id: e.target.value }, { saveNow: true })} sx={{ ...selectSx, minWidth: 150 }} disabled={conflict}>
              <MenuItem value="">بدون قالب</MenuItem>
              {templates.map((t) => <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>)}
            </TextField>
            <TextField select variant="standard" size="small" label="کاغذ" value={form.paper_size} onChange={(e) => update({ paper_size: e.target.value }, { saveNow: true })} sx={{ ...selectSx, minWidth: 70 }} disabled={conflict}>
              <MenuItem value="A4">A4</MenuItem>
              <MenuItem value="A5">A5</MenuItem>
            </TextField>
            <FormControlLabel
              control={<Checkbox size="small" color="error" checked={form.requires_action} onChange={(e) => update({ requires_action: e.target.checked })} />}
              label={<Typography variant="body2" color="error.main" fontWeight={600}>نیاز به اقدام از سمت گیرنده</Typography>}
              sx={{ m: 0 }}
            />
            {form.requires_action && (
              <Box sx={{ width: 190 }}>
                <JalaliCalendarField
                  label="مهلت اقدام (اختیاری)"
                  value={form.action_due}
                  onChange={(v) => update({ action_due: v })}
                />
              </Box>
            )}
          </Stack>
          <LetterEditor value={form.body_html} onChange={(html) => update({ body_html: html })} disabled={conflict} bare />
          <AttachmentChips extras={extras} api={api} disabled={lockedUI} />
          {api.error && <Alert severity="error" sx={{ mx: 2, mb: 1, whiteSpace: "pre-wrap" }} onClose={() => api.setError("")}>{api.error}</Alert>}
          {/* نوار پایین مثل ایمیل: ارسال، پیوست، چاپ، وضعیت ذخیره، حذف */}
          <Stack direction="row" alignItems="center" gap={1} sx={{ px: 2, py: 1.25, borderTop: 1, borderColor: "divider" }}>
            <Button
              variant="contained"
              startIcon={<SendOutlinedIcon />}
              onClick={() => { setSendError(""); setConfirmSend(true); }}
              disabled={conflict || !extras.recipients.some((r) => r.role === "to")}
              sx={{ height: 40, borderRadius: 5, px: 3 }}
            >
              ارسال
            </Button>
            <AttachButton extras={extras} api={api} disabled={lockedUI} />
            <Tooltip title="چاپ">
              <span>
                <IconButton onClick={() => window.print()} disabled={dirty}><PrintOutlinedIcon /></IconButton>
              </span>
            </Tooltip>
            <Typography variant="caption" color={saveState?.ok === false ? "error" : "text.secondary"} sx={{ flex: 1, minWidth: 0 }} noWrap>
              {saving ? "در حال ذخیره..." : dirty ? "تغییر ذخیره‌نشده" : saveState?.message || "پیش‌نویس خودکار ذخیره می‌شود"}
            </Typography>
            <Tooltip title="حذف پیش‌نویس">
              <IconButton onClick={() => setConfirmDiscard(true)}><DeleteOutlineIcon /></IconButton>
            </Tooltip>
          </Stack>
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
          />
        </Card>
      </Stack>

      <LetterPrint paper={previewPaper} layout={draft.layout} subject={form.subject} bodyHtml={form.body_html} segments={segments} siteName={draft.site_name} />

      <Dialog open={confirmSend} onClose={() => !sending && setConfirmSend(false)} fullWidth maxWidth="xs">
        <DialogTitle>ارسال نامه</DialogTitle>
        <DialogContent>
          <Typography sx={{ mb: 1 }}>
            «{form.subject || "بدون موضوع"}» برای {toPersianDigits(extras.recipients.filter((r) => r.role === "to").length)} گیرنده
            {extras.recipients.some((r) => r.role === "cc")
              ? ` و ${toPersianDigits(extras.recipients.filter((r) => r.role === "cc").length)} رونوشت`
              : ""}{" "}
            ارسال شود؟
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {form.requires_action ? "از گیرنده‌ی اصلی اقدام خواسته می‌شود. " : "فقط برای اطلاع گیرنده (بدون نیاز به اقدام). "}
            بعد از ارسال، متن و گیرندگان قابل تغییر نیستند.
            {form.confidentiality === "confidential" ? " این نامه محرمانه است و فقط گیرندگان و افرادی که به آن‌ها ارجاع شود آن را می‌بینند." : ""}
          </Typography>
          {sendError && <Alert severity="error" sx={{ mt: 2 }}>{sendError}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmSend(false)} disabled={sending}>انصراف</Button>
          <Button variant="contained" color="success" onClick={handleSend} disabled={sending}>
            {sending ? "در حال ارسال..." : "ارسال"}
          </Button>
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
