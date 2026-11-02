// مشاهده‌ی نامه — اتوماسیون اداری فاز ۳الف: متن (پیش‌نمایش صفحه‌ای)، گیرندگان، پیوست‌ها، مسئولیت من (ثبت نتیجه / اعلام
// رؤیت)، ارجاع، درخت گردش، هامش و محرمانه کردن. همه‌ی دسترسی‌ها در سرور (can) بررسی می‌شوند؛ این صفحه فقط نمایش می‌دهد.
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
  Divider,
  FormControlLabel,
  IconButton,
  LinearProgress,
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
import ReplyIcon from "@mui/icons-material/Reply";
import LinkIcon from "@mui/icons-material/Link";
import AttachFileIcon from "@mui/icons-material/AttachFile";
import {
  addLetterNote,
  completeTaskWithFiles,
  downloadTaskAttachment,
  createRelatedDraft,
  downloadLetterAttachment,
  fetchLetter,
  makeLetterConfidential,
  referLetter,
} from "../api/automationLetters";
import LetterPreview from "../components/oa/LetterPreview";
import LetterPrint from "../components/oa/LetterPrint";
import PersonPicker from "../components/oa/PersonPicker";
import { formatSize, saveBlob } from "../components/oa/DraftExtras";
import { useAuth } from "../context/AuthContext";
import { toPersianDigits } from "../utils/searchText";
import { jalaliToGregorian } from "../utils/jalaliDate";
import JalaliCalendarField from "../components/JalaliCalendarField";

// «YYYY/MM/DD» شمسی → ISO پایان همان روز
function jalaliEndOfDay(value) {
  const m = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/.exec(value || "");
  return m ? jalaliToGregorian(Number(m[1]), Number(m[2]), Number(m[3]), 23, 59).toISOString() : null;
}

const URGENCY = { normal: "عادی", urgent: "فوری", immediate: "آنی" };
const KIND = { action: "اقدام", info: "اطلاع" };
const fmt = (d) => (d ? new Date(d).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "");

const STATE_TEXT = { done: "انجام شد", current: "در انتظار اقدام", read: "خوانده شد", unread: "خوانده نشده", cancelled: "لغو شد" };

// گردش نامه مثل گردش درخواست وام: مراحل از سرور (letter.flow: ارسال، گیرندگان/رونوشت با وضعیت خواندن یا اقدام، ارجاع‌ها)؛
// افقی در دسکتاپ، عمودی در موبایل یا وقتی مراحل زیاد است؛ زیرش تاریخچه با زمان
function LetterFlow({ letter, onDownloadTaskFile }) {
  const small = useMediaQuery((t) => t.breakpoints.down("md"));
  const steps = letter.flow || [];
  const vertical = small || steps.length > 6;
  const firstOpen = steps.findIndex((s) => s.state === "current" || s.state === "unread");
  const events = [];
  for (const s of steps) {
    if (s.key === "sent") events.push({ at: s.at, text: `ارسال توسط ${s.person || "—"}${s.sent_by ? ` (فرستاده‌شده به‌وسیله‌ی منشی: ${s.sent_by})` : ""}` });
    else if (s.key.startsWith("t")) {
      events.push({ at: s.created_at || s.at, text: `ارجاع ${s.from || ""} به ${s.person}${s.instruction ? `: ${s.instruction}` : ""}${s.due_at ? ` — مهلت ${fmt(s.due_at)}` : ""}` });
    }
    if (s.read_at && s.key !== "sent") events.push({ at: s.read_at, text: `${s.person} نامه را خواند` });
    if (s.state === "done" && s.key !== "sent") {
      events.push({
        at: s.at,
        text: `${s.person}: ${s.label.includes("اطلاع") ? "رؤیت ثبت شد" : "اقدام شد"}${s.note ? ` — ${s.note}` : ""}`,
        files: s.attachments || [],
      });
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
            <Step key={s.key} completed={s.state === "done" || s.state === "read"}>
              <StepLabel
                error={Boolean(s.overdue)}
                optional={
                  <Typography variant="caption" color={s.state === "unread" ? "text.disabled" : "text.secondary"} component="div">
                    {s.person}
                    {s.key !== "sent" ? ` — ${STATE_TEXT[s.state]}` : ""}
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
          <Box key={i}>
            <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "pre-wrap" }}>
              {fmt(e.at)} — {e.text}
            </Typography>
            {e.files?.length > 0 && (
              <Stack direction="row" flexWrap="wrap" gap={0.5} sx={{ mt: 0.25 }}>
                {e.files.map((a) => (
                  <Chip
                    key={a.id}
                    size="small"
                    variant="outlined"
                    icon={<AttachFileIcon />}
                    label={`${a.file.name} (${formatSize(a.file.size)})`}
                    onClick={a.file.can_download ? () => onDownloadTaskFile(a) : undefined}
                    sx={{ maxWidth: "100%" }}
                  />
                ))}
              </Stack>
            )}
          </Box>
        ))}
      </Stack>
    </>
  );
}

export default function OaLetterPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, refetchUser } = useAuth();
  const [letter, setLetter] = useState(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState(null); // { ok, text }
  const [pages, setPages] = useState(1);
  const [segments, setSegments] = useState(null); // شکست صفحه‌های پیش‌نمایش، برای چاپ یکسان
  const handlePages = useCallback((n, segs) => {
    setPages(n);
    setSegments(segs);
  }, []);
  const [doneFor, setDoneFor] = useState(null); // task
  const [doneNote, setDoneNote] = useState("");
  const [doneFiles, setDoneFiles] = useState([]);
  const [doneProgress, setDoneProgress] = useState(0);
  const doneFileRef = useRef(null);
  const [referOpen, setReferOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [refer, setRefer] = useState({ people: [], kind: "action", instruction: "", allow_refer: false, due: "" });
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmConfidential, setConfirmConfidential] = useState(false);

  // پیش‌نویس پاسخ و رفتن به ویرایشگر آن
  async function newRelated(type) {
    setBusy(true);
    setMsg(null);
    try {
      const res = await createRelatedDraft(id, type);
      navigate(`/automation/drafts/${res.draft_id}`);
    } catch (err) {
      setMsg({ ok: false, text: err.response?.data?.detail || "ساخت پیش‌نویس ناموفق بود." });
      setBusy(false);
    }
  }

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
    const ok = await run(
      () => completeTaskWithFiles(doneFor.id, doneNote, doneFor.kind === "action" ? doneFiles : [], setDoneProgress),
      doneFor.kind === "info" ? "رؤیت ثبت شد." : "نتیجه ثبت شد.",
    );
    setDoneProgress(0);
    if (ok) {
      setDoneFor(null);
      setDoneNote("");
      setDoneFiles([]);
    }
  }

  function addDoneFiles(e) {
    const picked = Array.from(e.target.files || []);
    e.target.value = "";
    const lim = letter?.action_attachment_limits;
    const next = [...doneFiles, ...picked];
    if (lim) {
      if (next.length > lim.max_files) {
        setMsg({ ok: false, text: `حداکثر ${toPersianDigits(lim.max_files)} پیوست برای نتیجه‌ی اقدام مجاز است.` });
        return;
      }
      const big = picked.find((f) => f.size > lim.max_file_mb * 1024 * 1024);
      if (big) {
        setMsg({ ok: false, text: `حجم «${big.name}» از ${toPersianDigits(lim.max_file_mb)} مگابایت بیشتر است.` });
        return;
      }
      if (next.reduce((t, f) => t + f.size, 0) > lim.max_total_mb * 1024 * 1024) {
        setMsg({ ok: false, text: `حجم مجموع پیوست‌ها از ${toPersianDigits(lim.max_total_mb)} مگابایت بیشتر می‌شود.` });
        return;
      }
    }
    setMsg(null);
    setDoneFiles(next);
  }

  async function downloadTaskFile(a) {
    try {
      saveBlob(await downloadTaskAttachment(letter.id, a.id), a.file.name);
    } catch {
      setMsg({ ok: false, text: "دانلود ناموفق بود." });
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
          due_at: refer.due ? jalaliEndOfDay(refer.due) : null,
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

      <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap" sx={{ mb: 2 }}>
        <IconButton onClick={() => navigate("/automation/cartable")}><ArrowForwardIcon /></IconButton>
        {confidential && <LockOutlinedIcon color="error" />}
        <Typography variant="h6" fontWeight={700} sx={{ flex: 1 }}>{letter.subject}</Typography>
        {letter.urgency !== "normal" && <Chip color="warning" label={URGENCY[letter.urgency]} />}
        {confidential && <Chip color="error" label="محرمانه" />}
        <Button variant="outlined" startIcon={<PrintOutlinedIcon />} onClick={() => window.print()} sx={{ height: 40 }}>چاپ</Button>
        {user?.can_oa_access && (
          <>
            <Button variant="outlined" startIcon={<ReplyIcon />} onClick={() => newRelated("reply")} disabled={busy} sx={{ height: 40 }}>
              پاسخ
            </Button>
          </>
        )}
        {letter.permissions.refer && (
          <Button variant="contained" startIcon={<ForwardToInboxOutlinedIcon />} onClick={() => setReferOpen(true)} sx={{ height: 40 }}>ارجاع</Button>
        )}
      </Stack>

      {letter.relations?.length > 0 && (
        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 2 }}>
          {letter.relations.map((r, i) => (
            <Chip
              key={i}
              variant="outlined"
              icon={<LinkIcon />}
              label={`${r.label}: ${r.subject || "نامه‌ای که به آن دسترسی ندارید"}`}
              onClick={r.letter_id ? () => navigate(`/automation/letters/${r.letter_id}`) : undefined}
            />
          ))}
        </Stack>
      )}

      {msg && <Alert severity={msg.ok ? "success" : "error"} sx={{ mb: 2 }}>{msg.text}</Alert>}

      {letter.my_open_tasks.map((t) => (
        <Alert
          key={t.id}
          severity="warning"
          sx={{ mb: 2 }}
          action={
            <Button color="inherit" startIcon={<TaskAltIcon />} onClick={() => { setDoneFor(t); setDoneNote(""); setDoneFiles([]); }} disabled={busy}>
              {t.kind === "info" ? "اعلام رؤیت" : "ثبت نتیجه"}
            </Button>
          }
        >
          {t.kind === "info" ? "این نامه برای اطلاع به شما ارجاع شده است." : "این نامه در انتظار اقدام شماست."}
          {t.instruction ? ` دستور: ${t.instruction}` : ""}
        </Alert>
      ))}

      {/* موبایل: فرستنده/گیرنده ← متن نامه ← پیوست‌ها ← گردش ← یادداشت؛ دسکتاپ: متن نامه در ستون دوم (چسبان) */}
      <Box
        sx={{
          display: "grid",
          gap: 2,
          alignItems: "start",
          gridTemplateColumns: { xs: "minmax(0, 1fr)", lg: "minmax(0, 1fr) minmax(0, 1fr)" },
          gridTemplateAreas: {
            xs: '"info" "text" "att" "flow" "notes"',
            lg: '"info text" "att text" "flow text" "notes text"',
          },
          gridTemplateRows: { lg: "auto auto auto 1fr" },
        }}
      >
          <Card variant="outlined" sx={{ p: 2, borderRadius: 2, gridArea: "info" }}>
            <Stack spacing={1}>
              <Typography variant="body2">
                <b>فرستنده:</b> {letter.sender?.name}{letter.sender?.title ? ` (${letter.sender.title})` : ""} — {fmt(letter.sent_at)}
              </Typography>
              {letter.sender?.sent_by && (
                <Typography variant="caption" color="text.secondary">
                  فرستاده‌شده به‌وسیله‌ی منشی: {letter.sender.sent_by}
                </Typography>
              )}
              <Box><Typography variant="body2" component="span" fontWeight={700}>گیرنده: </Typography>{people(to)}</Box>
              {cc.length > 0 && <Box><Typography variant="body2" component="span" fontWeight={700}>رونوشت: </Typography>{people(cc)}</Box>}
              {letter.recipients.some((r) => r.read_at) && (
                <Typography variant="caption" color="text.secondary">✓ = خوانده شده</Typography>
              )}
              <Typography variant="caption" color="text.secondary">
                {letter.requires_action
                  ? `از گیرنده اقدام خواسته شده${letter.action_due_at ? ` — مهلت ${fmt(letter.action_due_at)}` : ""}`
                  : "برای اطلاع گیرنده (بدون نیاز به اقدام)"}
              </Typography>
              {letter.permissions.make_confidential && (
                <Box>
                  <Button size="small" color="error" startIcon={<LockOutlinedIcon />} onClick={() => setConfirmConfidential(true)}>
                    محرمانه کردن این نامه
                  </Button>
                </Box>
              )}
            </Stack>
          </Card>

        <Card variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: "action.hover", gridArea: "text", minWidth: 0, alignSelf: "start", position: { lg: "sticky" }, top: { lg: 16 } }}>
          <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
            متن نامه — کاغذ <bdi dir="ltr">{letter.paper_size}</bdi>، {toPersianDigits(pages)} صفحه
          </Typography>
          <LetterPreview paper={letter.paper_size} layout={letter.layout} subject={letter.subject} bodyHtml={letter.body_html} fit onPages={handlePages} siteName={letter.site_name} />
        </Card>
          {letter.attachments.length > 0 && (
            <Card variant="outlined" sx={{ p: 2, borderRadius: 2, gridArea: "att" }}>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>پیوست‌ها</Typography>
              {letter.attachments.map((a) => (
                <Stack key={a.id} direction="row" alignItems="center" spacing={1}>
                  <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }} noWrap>{a.file.name}</Typography>
                  <Typography variant="caption" color="text.secondary">{formatSize(a.file.size)}</Typography>
                  <IconButton size="small" onClick={() => download(a)} disabled={!a.file.can_download}><DownloadOutlinedIcon fontSize="small" /></IconButton>
                </Stack>
              ))}
            </Card>
          )}
          <Card variant="outlined" sx={{ p: 2, borderRadius: 2, gridArea: "flow" }}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>گردش و ارجاع‌ها</Typography>
            <LetterFlow letter={letter} onDownloadTaskFile={downloadTaskFile} />
          </Card>

          <Card variant="outlined" sx={{ p: 2, borderRadius: 2, gridArea: "notes" }}>
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
      </Box>

      <LetterPrint paper={letter.paper_size} layout={letter.layout} subject={letter.subject} bodyHtml={letter.body_html} segments={segments} siteName={letter.site_name} />

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
          {doneFor?.kind === "action" && (
            <Box sx={{ mt: 2 }}>
              <input ref={doneFileRef} type="file" multiple hidden onChange={addDoneFiles} />
              <Button size="small" variant="outlined" startIcon={<AttachFileIcon />} onClick={() => doneFileRef.current?.click()} disabled={busy}>
                پیوست فایل
              </Button>
              {letter.action_attachment_limits && (
                <Typography variant="caption" color="text.secondary" sx={{ mx: 1 }}>
                  حداکثر {toPersianDigits(letter.action_attachment_limits.max_files)} فایل، هر کدام تا{" "}
                  {toPersianDigits(letter.action_attachment_limits.max_file_mb)} مگابایت
                </Typography>
              )}
              <Stack direction="row" flexWrap="wrap" gap={0.5} sx={{ mt: 1 }}>
                {doneFiles.map((f, i) => (
                  <Chip
                    key={`${f.name}-${i}`}
                    size="small"
                    label={`${f.name} (${formatSize(f.size)})`}
                    onDelete={busy ? undefined : () => setDoneFiles((list) => list.filter((_, j) => j !== i))}
                  />
                ))}
              </Stack>
              {busy && doneProgress > 0 && doneProgress < 100 && <LinearProgress variant="determinate" value={doneProgress} sx={{ mt: 1 }} />}
            </Box>
          )}
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
            <Box sx={{ maxWidth: 240 }}>
              <JalaliCalendarField label="مهلت (اختیاری)" value={refer.due || null} onChange={(v) => setRefer((r) => ({ ...r, due: v || "" }))} />
            </Box>
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
