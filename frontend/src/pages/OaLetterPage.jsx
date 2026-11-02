// مشاهده‌ی نامه — اتوماسیون اداری فاز ۳الف: متن (پیش‌نمایش صفحه‌ای)، گیرندگان، پیوست‌ها، مسئولیت من (ثبت نتیجه / اعلام
// رؤیت)، ارجاع، درخت گردش، هامش و محرمانه کردن. همه‌ی دسترسی‌ها در سرور (can) بررسی می‌شوند؛ این صفحه فقط نمایش می‌دهد.
import { useCallback, useEffect, useState } from "react";
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
  Divider,
  FormControlLabel,
  GlobalStyles,
  IconButton,
  MenuItem,
  Stack,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
  useMediaQuery,
} from "@mui/material";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import ForwardToInboxOutlinedIcon from "@mui/icons-material/ForwardToInboxOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import PrintOutlinedIcon from "@mui/icons-material/PrintOutlined";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import TaskAltIcon from "@mui/icons-material/TaskAlt";
import {
  addLetterNote,
  completeTask,
  downloadLetterAttachment,
  fetchLetter,
  makeLetterConfidential,
  referLetter,
} from "../api/automationLetters";
import LetterPreview from "../components/oa/LetterPreview";
import PersonPicker from "../components/oa/PersonPicker";
import { formatSize, saveBlob } from "../components/oa/DraftExtras";
import { useAuth } from "../context/AuthContext";
import { toPersianDigits } from "../utils/searchText";

const URGENCY = { normal: "عادی", urgent: "فوری", immediate: "آنی" };
const KIND = { action: "اقدام", info: "اطلاع" };
const fmt = (d) => (d ? new Date(d).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "");

// گردش نامه مثل گردش درخواست وام: مراحل (Stepper؛ افقی در دسکتاپ، عمودی در موبایل یا وقتی مراحل زیاد است) و زیرش تاریخچه
function LetterFlow({ letter }) {
  const vertical = useMediaQuery((t) => t.breakpoints.down("md")) || letter.tasks.length > 5;
  const tasks = [...letter.tasks].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  const steps = [
    { key: "sent", label: "ارسال", person: letter.sender?.name, state: "done", at: letter.sent_at },
    ...tasks.map((t) => ({
      key: t.id,
      label: `${t.origin === "referral" ? "ارجاع" : "گیرنده"} — ${KIND[t.kind]}`,
      person: t.assignee,
      state: t.status === "done" ? "done" : t.status === "open" ? "current" : "cancelled",
      at: t.done_at || t.created_at,
      overdue: t.status === "open" && t.due_at && new Date(t.due_at) < new Date(),
    })),
  ];
  const firstOpen = steps.findIndex((s) => s.state === "current");
  // تاریخچه: ارسال، هر ارجاع (با دستور) و هر نتیجه، به ترتیب زمان
  const events = [{ at: letter.sent_at, text: `ارسال توسط ${letter.sender?.name || "—"}` }];
  for (const t of tasks) {
    if (t.origin === "referral") {
      events.push({ at: t.created_at, text: `ارجاع ${t.created_by || ""} به ${t.assignee} (${KIND[t.kind]})${t.instruction ? `: ${t.instruction}` : ""}${t.due_at ? ` — مهلت ${fmt(t.due_at)}` : ""}` });
    }
    if (t.status === "done") {
      events.push({ at: t.done_at, text: `${t.assignee}: ${t.kind === "info" ? "رؤیت شد" : "اقدام شد"}${t.result_note ? ` — ${t.result_note}` : ""}` });
    }
  }
  events.sort((a, b) => new Date(a.at) - new Date(b.at));
  return (
    <>
      <Box sx={{ overflowX: "auto" }}>
        <Stepper
          activeStep={firstOpen === -1 ? steps.length : firstOpen}
          orientation={vertical ? "vertical" : "horizontal"}
          alternativeLabel={!vertical}
          sx={{ my: 1 }}
        >
          {steps.map((s) => (
            <Step key={s.key} completed={s.state === "done"}>
              <StepLabel
                error={s.overdue}
                optional={
                  <Typography variant="caption" color="text.secondary" component="div">
                    {s.person}
                    {s.state === "current" ? " — در انتظار" : s.state === "cancelled" ? " — لغو شد" : ""}
                  </Typography>
                }
              >
                {s.label}
              </StepLabel>
            </Step>
          ))}
        </Stepper>
      </Box>
      <Stack spacing={0.5} sx={{ mt: 1 }}>
        {events.map((e, i) => (
          <Typography key={i} variant="caption" color="text.secondary" sx={{ whiteSpace: "pre-wrap" }}>
            {fmt(e.at)} — {e.text}
          </Typography>
        ))}
      </Stack>
    </>
  );
}

export default function OaLetterPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { refetchUser } = useAuth();
  const [letter, setLetter] = useState(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState(null); // { ok, text }
  const [pages, setPages] = useState(1);
  const [doneFor, setDoneFor] = useState(null); // task
  const [doneNote, setDoneNote] = useState("");
  const [referOpen, setReferOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [refer, setRefer] = useState({ people: [], kind: "action", instruction: "", allow_refer: false, due: "" });
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmConfidential, setConfirmConfidential] = useState(false);

  const load = useCallback(() => {
    return fetchLetter(id)
      .then((d) => {
        setLetter(d);
        refetchUser?.(); // شمارنده‌ی منو (خوانده شد)
      })
      .catch((err) => setError(err.response?.data?.detail || "نامه یافت نشد."));
  }, [id, refetchUser]);

  useEffect(() => {
    load();
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function run(fn, okText) {
    setBusy(true);
    setMsg(null);
    try {
      await fn();
      await load();
      setMsg({ ok: true, text: okText });
      return true;
    } catch (err) {
      setMsg({ ok: false, text: err.response?.data?.detail || "انجام نشد." });
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function submitDone() {
    if (await run(() => completeTask(doneFor.id, doneNote), doneFor.kind === "info" ? "رؤیت ثبت شد." : "نتیجه ثبت شد.")) {
      setDoneFor(null);
      setDoneNote("");
    }
  }

  async function submitRefer() {
    const ok = await run(
      () =>
        referLetter(id, {
          assignees: refer.people.map((p) => p.employee_id),
          kind: refer.kind,
          instruction: refer.instruction,
          allow_refer: refer.allow_refer,
          due_at: refer.due ? new Date(refer.due).toISOString() : null,
        }),
      "ارجاع انجام شد.",
    );
    if (ok) {
      setReferOpen(false);
      setRefer({ people: [], kind: "action", instruction: "", allow_refer: false, due: "" });
    }
  }

  async function submitNote() {
    if (await run(() => addLetterNote(id, note), "یادداشت ثبت شد.")) setNote("");
  }

  async function download(a) {
    try {
      saveBlob(await downloadLetterAttachment({ letterId: letter.id, attachmentId: a.id }), a.file.name);
    } catch {
      setMsg({ ok: false, text: "دانلود ناموفق بود." });
    }
  }

  if (error) {
    return (
      <Box sx={{ maxWidth: 600, mx: "auto" }}>
        <Alert severity="error" action={<Button color="inherit" onClick={() => navigate("/automation/cartable")}>کارتابل</Button>}>{error}</Alert>
      </Box>
    );
  }
  if (!letter) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  const confidential = letter.confidentiality === "confidential";
  const to = letter.recipients.filter((r) => r.role === "to");
  const cc = letter.recipients.filter((r) => r.role === "cc");
  const people = (list) =>
    list.map((r) => (
      <Chip
        key={`${r.role}-${r.name}`}
        size="small"
        variant="outlined"
        sx={{ m: 0.25 }}
        label={`${r.name}${r.title ? ` (${r.title})` : ""}${r.read_at ? " ✓" : ""}`}
        title={r.read_at ? `رؤیت: ${fmt(r.read_at)}` : undefined}
      />
    ));

  return (
    <Box>
      <GlobalStyles
        styles={{
          ".oa-print-area": { display: "none" },
          "@media print": {
            "@page": { size: `${letter.paper_size} portrait`, margin: 0 },
            "body *": { visibility: "hidden" },
            ".oa-print-area, .oa-print-area *": { visibility: "visible" },
            ".oa-print-area": { display: "block", position: "absolute", top: 0, right: 0 },
          },
        }}
      />

      <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap" sx={{ mb: 2 }}>
        <IconButton onClick={() => navigate("/automation/cartable")}><ArrowForwardIcon /></IconButton>
        {confidential && <LockOutlinedIcon color="error" />}
        <Typography variant="h6" fontWeight={700} sx={{ flex: 1 }}>{letter.subject}</Typography>
        {letter.urgency !== "normal" && <Chip color="warning" label={URGENCY[letter.urgency]} />}
        {confidential && <Chip color="error" label="محرمانه" />}
        <Button variant="outlined" startIcon={<PrintOutlinedIcon />} onClick={() => window.print()} sx={{ height: 40 }}>چاپ</Button>
        {letter.permissions.refer && (
          <Button variant="contained" startIcon={<ForwardToInboxOutlinedIcon />} onClick={() => setReferOpen(true)} sx={{ height: 40 }}>ارجاع</Button>
        )}
      </Stack>

      {msg && <Alert severity={msg.ok ? "success" : "error"} sx={{ mb: 2 }}>{msg.text}</Alert>}

      {letter.my_open_tasks.map((t) => (
        <Alert
          key={t.id}
          severity="warning"
          sx={{ mb: 2 }}
          action={
            <Button color="inherit" startIcon={<TaskAltIcon />} onClick={() => { setDoneFor(t); setDoneNote(""); }} disabled={busy}>
              {t.kind === "info" ? "اعلام رؤیت" : "ثبت نتیجه"}
            </Button>
          }
        >
          {t.kind === "info" ? "این نامه برای اطلاع به شما ارجاع شده است." : "این نامه در انتظار اقدام شماست."}
          {t.instruction ? ` دستور: ${t.instruction}` : ""}
        </Alert>
      ))}

      <Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems="flex-start">
        <Stack spacing={2} sx={{ flex: "1 1 0", minWidth: 0, width: "100%" }}>
          <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Stack spacing={1}>
              <Typography variant="body2">
                <b>فرستنده:</b> {letter.sender?.name}{letter.sender?.title ? ` (${letter.sender.title})` : ""} — {fmt(letter.sent_at)}
              </Typography>
              <Box><Typography variant="body2" component="span" fontWeight={700}>گیرنده: </Typography>{people(to)}</Box>
              {cc.length > 0 && <Box><Typography variant="body2" component="span" fontWeight={700}>رونوشت: </Typography>{people(cc)}</Box>}
              {letter.recipients.some((r) => r.read_at) && (
                <Typography variant="caption" color="text.secondary">✓ = رؤیت شده (فقط برای فرستنده نمایش داده می‌شود)</Typography>
              )}
              {letter.attachments.length > 0 && (
                <>
                  <Divider />
                  <Typography variant="body2" fontWeight={700}>پیوست‌ها</Typography>
                  {letter.attachments.map((a) => (
                    <Stack key={a.id} direction="row" alignItems="center" spacing={1}>
                      <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }} noWrap>{a.file.name}</Typography>
                      <Typography variant="caption" color="text.secondary">{formatSize(a.file.size)}</Typography>
                      <IconButton size="small" onClick={() => download(a)} disabled={!a.file.can_download}><DownloadOutlinedIcon fontSize="small" /></IconButton>
                    </Stack>
                  ))}
                </>
              )}
              {letter.permissions.make_confidential && (
                <Box>
                  <Button size="small" color="error" startIcon={<LockOutlinedIcon />} onClick={() => setConfirmConfidential(true)}>
                    محرمانه کردن این نامه
                  </Button>
                </Box>
              )}
            </Stack>
          </Card>

          <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>گردش و ارجاع‌ها</Typography>
            <LetterFlow letter={letter} />
          </Card>

          <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>یادداشت‌های داخلی (هامش)</Typography>
            <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 1 }}>
              مثل یادداشتی که کنار نامه‌ی کاغذی نوشته می‌شود: فقط کسانی که این نامه را می‌بینند آن را می‌خوانند و در متن رسمی
              و چاپ نامه نمی‌آید.
            </Typography>
            <Stack spacing={1}>
              {letter.notes.map((n) => (
                <Box key={n.id} sx={{ p: 1, bgcolor: "action.hover", borderRadius: 1 }}>
                  <Typography variant="caption" color="text.secondary">{n.author} — {fmt(n.created_at)}</Typography>
                  <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>{n.text}</Typography>
                </Box>
              ))}
              {letter.permissions.note && (
                <Stack direction="row" spacing={1} alignItems="flex-start">
                  <TextField size="small" multiline maxRows={6} fullWidth placeholder="یادداشت جدید" sx={{ "& .MuiInputBase-root": { bgcolor: "background.paper" } }} value={note} onChange={(e) => setNote(e.target.value)} inputProps={{ maxLength: 4000 }} />
                  <Button variant="outlined" onClick={submitNote} disabled={busy || !note.trim()} sx={{ height: 40 }}>ثبت</Button>
                </Stack>
              )}
            </Stack>
          </Card>
        </Stack>

        <Card variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: "action.hover", flex: "1 1 0", minWidth: 0, width: "100%", position: { lg: "sticky" }, top: { lg: 16 } }}>
          <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
            متن نامه — {letter.paper_size}، {toPersianDigits(pages)} صفحه
          </Typography>
          <LetterPreview paper={letter.paper_size} layout={letter.layout} subject={letter.subject} bodyHtml={letter.body_html} fit onPages={setPages} siteName={letter.site_name} />
        </Card>
      </Stack>

      <Box className="oa-print-area">
        <LetterPreview paper={letter.paper_size} layout={letter.layout} subject={letter.subject} bodyHtml={letter.body_html} printOnly forcePages={pages} siteName={letter.site_name} />
      </Box>

      {/* ثبت نتیجه / اعلام رؤیت */}
      <Dialog open={Boolean(doneFor)} onClose={() => !busy && setDoneFor(null)} fullWidth maxWidth="sm">
        <DialogTitle>{doneFor?.kind === "info" ? "اعلام رؤیت" : "ثبت نتیجه‌ی اقدام"}</DialogTitle>
        <DialogContent>
          <TextField
            multiline
            minRows={3}
            fullWidth
            sx={{ mt: 1 }}
            label={doneFor?.kind === "info" ? "توضیح (اختیاری)" : "نتیجه‌ی اقدام"}
            value={doneNote}
            onChange={(e) => setDoneNote(e.target.value)}
            inputProps={{ maxLength: 4000 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDoneFor(null)} disabled={busy}>انصراف</Button>
          <Button variant="contained" onClick={submitDone} disabled={busy || (doneFor?.kind === "action" && !doneNote.trim())}>ثبت</Button>
        </DialogActions>
      </Dialog>

      {/* ارجاع */}
      <Dialog open={referOpen} onClose={() => !busy && setReferOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>ارجاع نامه</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Box>
              <Button size="small" variant="outlined" onClick={() => setPickerOpen(true)}>انتخاب افراد</Button>
              <Box sx={{ mt: 1 }}>
                {refer.people.map((p) => (
                  <Chip key={p.employee_id} label={p.name} sx={{ m: 0.25 }} onDelete={() => setRefer((r) => ({ ...r, people: r.people.filter((x) => x.employee_id !== p.employee_id) }))} />
                ))}
              </Box>
            </Box>
            <TextField select size="small" label="نوع ارجاع" value={refer.kind} onChange={(e) => setRefer((r) => ({ ...r, kind: e.target.value }))}>
              <MenuItem value="action">برای اقدام</MenuItem>
              <MenuItem value="info">برای اطلاع</MenuItem>
            </TextField>
            <TextField multiline minRows={2} label="دستور / توضیح" value={refer.instruction} onChange={(e) => setRefer((r) => ({ ...r, instruction: e.target.value }))} inputProps={{ maxLength: 2000 }} />
            <TextField
              size="small"
              type="datetime-local"
              label="مهلت (اختیاری)"
              value={refer.due}
              onChange={(e) => setRefer((r) => ({ ...r, due: e.target.value }))}
              InputLabelProps={{ shrink: true }}
              sx={{ maxWidth: 260 }}
            />
            <FormControlLabel
              control={<Checkbox checked={refer.allow_refer} onChange={(e) => setRefer((r) => ({ ...r, allow_refer: e.target.checked }))} />}
              label="اجازه‌ی ارجاع دوباره به دیگران"
            />
            {confidential && (
              <Alert severity="info">این نامه محرمانه است؛ افرادی که انتخاب می‌کنید از این لحظه به آن دسترسی پیدا می‌کنند و ارجاع با نام شما ثبت می‌شود.</Alert>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setReferOpen(false)} disabled={busy}>انصراف</Button>
          <Button variant="contained" onClick={submitRefer} disabled={busy || !refer.people.length}>ارجاع</Button>
        </DialogActions>
      </Dialog>

      <PersonPicker
        open={pickerOpen}
        title="ارجاع به"
        exclude={refer.people.map((p) => p.employee_id)}
        onClose={() => setPickerOpen(false)}
        onConfirm={(list) => {
          setPickerOpen(false);
          setRefer((r) => ({ ...r, people: [...r.people, ...list] }));
        }}
      />

      <Dialog open={confirmConfidential} onClose={() => setConfirmConfidential(false)}>
        <DialogTitle>محرمانه کردن نامه</DialogTitle>
        <DialogContent>
          <Typography>
            بعد از محرمانه کردن، برگرداندن به «عادی» ممکن نیست. فقط شرکت‌کنندگان همین نامه (فرستنده، گیرندگان، رونوشت‌ها و
            ارجاع‌گیرندگان) دسترسی دارند و اعلان‌های بعدی بدون موضوع فرستاده می‌شوند.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmConfidential(false)}>انصراف</Button>
          <Button
            color="error"
            variant="contained"
            disabled={busy}
            onClick={async () => {
              if (await run(() => makeLetterConfidential(id, null), "نامه محرمانه شد.")) setConfirmConfidential(false);
            }}
          >
            محرمانه شود
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
