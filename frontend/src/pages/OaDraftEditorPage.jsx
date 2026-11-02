// ویرایش پیش‌نویس نامه — اتوماسیون اداری فاز ۲: موضوع، فوریت، محرمانگی، قالب، اندازه‌ی کاغذ و متن (TipTap) با
// ذخیره‌ی خودکار، پیش‌نمایش صفحه‌ای A4/A5 (شمار صفحه و پیشنهاد A4 وقتی A5 جا نمی‌شود) و چاپ.
// قفل خوش‌بینانه: اگر همین پیش‌نویس در تب/دستگاه دیگری ذخیره شده باشد سرور 409 می‌دهد و ذخیره‌ی خودکار متوقف می‌شود.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  GlobalStyles,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import PrintOutlinedIcon from "@mui/icons-material/PrintOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import SendOutlinedIcon from "@mui/icons-material/SendOutlined";
import { discardDraft, fetchComposeOptions, fetchDraft, saveDraft, sendDraft } from "../api/automationLetters";
import DraftExtras from "../components/oa/DraftExtras";
import LetterEditor from "../components/oa/LetterEditor";
import LetterPreview from "../components/oa/LetterPreview";
import { toPersianDigits } from "../utils/searchText";

const AUTOSAVE_MS = 3000;

function formFrom(d) {
  return {
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
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [extras, setExtras] = useState({ recipients: [], attachments: [] });
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
        setExtras({ recipients: d.recipients || [], attachments: d.attachments || [] });
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
      const updated = await saveDraft(d.id, {
        ...f,
        template_id: f.template_id ? Number(f.template_id) : null,
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

  const siteTemplates = useMemo(
    () => (options?.templates || []).filter((t) => draft && t.site_id === draft.site_id),
    [options, draft],
  );

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
      {/* چاپ: فقط صفحه‌های نامه، اندازه‌ی واقعی، بدون حاشیه‌ی مرورگر */}
      <GlobalStyles
        styles={{
          ".oa-print-area": { display: "none" },
          "@media print": {
            "@page": { size: `${previewPaper} portrait`, margin: 0 },
            "body *": { visibility: "hidden" },
            ".oa-print-area, .oa-print-area *": { visibility: "visible" },
            ".oa-print-area": { display: "block", position: "absolute", top: 0, right: 0 },
          },
        }}
      />

      <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap" sx={{ mb: 2 }}>
        <Button startIcon={<ArrowForwardIcon />} onClick={() => navigate("/automation/drafts")} sx={{ height: 40 }}>
          پیش‌نویس‌ها
        </Button>
        <Typography variant="h6" fontWeight={700} sx={{ flex: 1 }}>
          {form.subject || "پیش‌نویس بدون موضوع"}
        </Typography>
        <Typography variant="caption" color={saveState?.ok === false ? "error" : "text.secondary"}>
          {saving ? "در حال ذخیره..." : dirty ? "تغییر ذخیره‌نشده" : saveState?.message || ""}
        </Typography>
        <Button variant="contained" startIcon={<SaveOutlinedIcon />} onClick={doSave} disabled={saving || conflict} sx={{ height: 40 }}>
          ذخیره
        </Button>
        <Button variant="outlined" startIcon={<PrintOutlinedIcon />} onClick={() => window.print()} disabled={dirty} sx={{ height: 40 }}>
          چاپ
        </Button>
        <Button color="error" startIcon={<DeleteOutlineIcon />} onClick={() => setConfirmDiscard(true)} sx={{ height: 40 }}>
          حذف
        </Button>
        <Button
          variant="contained"
          color="success"
          startIcon={<SendOutlinedIcon />}
          onClick={() => { setSendError(""); setConfirmSend(true); }}
          disabled={conflict || !extras.recipients.some((r) => r.role === "to")}
          sx={{ height: 40 }}
        >
          ارسال
        </Button>
      </Stack>

      {conflict && (
        <Alert severity="error" sx={{ mb: 2 }} action={<Button color="inherit" onClick={() => window.location.reload()}>تازه کردن</Button>}>
          این پیش‌نویس در تب یا دستگاه دیگری تغییر کرده است. برای جلوگیری از پاک شدن آن تغییرها، ذخیره متوقف شد. صفحه را تازه کنید.
        </Alert>
      )}
      {saveState?.ok === false && !conflict && <Alert severity="error" sx={{ mb: 2 }}>{saveState.message}</Alert>}
      {draft.template_outdated && (
        <Alert severity="info" sx={{ mb: 2 }}>
          قالب «{draft.template_name}» بعد از ساخت این پیش‌نویس تغییر کرده است؛ با ذخیره‌ی بعدی نسخه‌ی تازه‌ی قالب اعمال می‌شود.
        </Alert>
      )}

      <Stack direction={{ xs: "column", lg: "row" }} spacing={3} alignItems="flex-start">
        <Stack spacing={2} sx={{ flex: 1, minWidth: 0, width: "100%" }}>
          <TextField
            label="موضوع"
            value={form.subject}
            onChange={(e) => update({ subject: e.target.value })}
            inputProps={{ maxLength: 300 }}
            fullWidth
          />
          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
            <TextField select size="small" label="فوریت" value={form.urgency} onChange={(e) => update({ urgency: e.target.value })} sx={{ minWidth: 130 }}>
              {Object.entries(options.urgencies).map(([k, v]) => (
                <MenuItem key={k} value={k}>{v}</MenuItem>
              ))}
            </TextField>
            <TextField select size="small" label="محرمانگی" value={form.confidentiality} onChange={(e) => update({ confidentiality: e.target.value })} sx={{ minWidth: 130 }}>
              {Object.entries(options.confidentiality).map(([k, v]) => (
                <MenuItem key={k} value={k}>{v}</MenuItem>
              ))}
            </TextField>
            <TextField select size="small" label="قالب" value={form.template_id} onChange={(e) => update({ template_id: e.target.value }, { saveNow: true })} sx={{ minWidth: 180 }} disabled={conflict}>
              <MenuItem value="">بدون قالب</MenuItem>
              {siteTemplates.map((t) => (
                <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>
              ))}
            </TextField>
            <TextField select size="small" label="کاغذ" value={form.paper_size} onChange={(e) => update({ paper_size: e.target.value }, { saveNow: true })} sx={{ minWidth: 100 }} disabled={conflict}>
              <MenuItem value="A4">A4</MenuItem>
              <MenuItem value="A5">A5</MenuItem>
            </TextField>
          </Stack>
          <DraftExtras
            draftId={draft.id}
            recipients={extras.recipients}
            attachments={extras.attachments}
            onChange={setExtras}
            disabled={conflict || sending}
          />
          <LetterEditor value={form.body_html} onChange={(html) => update({ body_html: html })} disabled={conflict} />
        </Stack>

        <Card variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: "action.hover", flex: "none", width: { xs: "100%", lg: "auto" }, overflowX: "auto" }}>
          <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
            پیش‌نمایش {previewPaper} — {toPersianDigits(pages)} صفحه
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
            scale={previewPaper === "A5" ? 0.75 : 0.55}
            onPages={setPages}
            siteName={draft.site_name}
          />
        </Card>
      </Stack>

      <Box className="oa-print-area">
        <LetterPreview paper={previewPaper} layout={draft.layout} subject={form.subject} bodyHtml={form.body_html} printOnly forcePages={pages} siteName={draft.site_name} />
      </Box>

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
