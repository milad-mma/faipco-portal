// گیرندگان (اصلی/رونوشت) و پیوست‌های پیش‌نویس نامه — هر تغییر فوراً در سرور ذخیره می‌شود.
// props: draftId، recipients، attachments، onChange({recipients, attachments})، disabled
import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  IconButton,
  LinearProgress,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import PersonAddAltOutlinedIcon from "@mui/icons-material/PersonAddAltOutlined";
import AttachFileIcon from "@mui/icons-material/AttachFile";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import {
  downloadLetterAttachment,
  removeDraftAttachment,
  saveDraftRecipients,
  uploadDraftAttachment,
} from "../../api/automationLetters";
import PersonPicker from "./PersonPicker";
import { toPersianDigits } from "../../utils/searchText";

export function formatSize(bytes) {
  if (bytes == null) return "";
  if (bytes < 1024 * 1024) return `${toPersianDigits(Math.max(1, Math.round(bytes / 1024)))} کیلوبایت`;
  return `${toPersianDigits((bytes / 1024 / 1024).toFixed(1))} مگابایت`;
}

export async function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name || "file";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

export default function DraftExtras({ draftId, recipients, attachments, onChange, disabled }) {
  const [picker, setPicker] = useState(null); // "to" | "cc" | null
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploadPct, setUploadPct] = useState(null);

  async function saveRecipients(list) {
    setBusy(true);
    setError("");
    try {
      const res = await saveDraftRecipients(
        draftId,
        list.map((r) => ({ employee_id: r.employee_id, role: r.role, selected_via: r.selected_via || "direct" })),
      );
      onChange({ recipients: res.recipients, attachments: res.attachments });
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره‌ی گیرندگان ناموفق بود.");
    } finally {
      setBusy(false);
    }
  }

  function addPeople(role, people) {
    setPicker(null);
    const existing = new Set(recipients.map((r) => r.employee_id));
    saveRecipients([...recipients, ...people.filter((p) => !existing.has(p.employee_id)).map((p) => ({ ...p, role }))]);
  }

  async function handleUpload(file) {
    if (!file) return;
    setError("");
    setUploadPct(0);
    try {
      const res = await uploadDraftAttachment(draftId, file, setUploadPct);
      onChange({ recipients, attachments: res.attachments });
    } catch (err) {
      setError(err.response?.data?.detail || "بارگذاری پیوست ناموفق بود.");
    } finally {
      setUploadPct(null);
    }
  }

  async function handleRemove(id) {
    setError("");
    try {
      const res = await removeDraftAttachment(draftId, id);
      onChange({ recipients, attachments: res.attachments });
    } catch (err) {
      setError(err.response?.data?.detail || "حذف پیوست ناموفق بود.");
    }
  }

  async function handleDownload(a) {
    try {
      saveBlob(await downloadLetterAttachment({ letterId: draftId, attachmentId: a.id, draft: true }), a.file.name);
    } catch {
      setError("دانلود ناموفق بود.");
    }
  }

  const group = (role, label) => {
    const list = recipients.filter((r) => r.role === role);
    return (
      <Stack spacing={1}>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography variant="body2" fontWeight={700} sx={{ minWidth: 70 }}>{label}</Typography>
          <Button size="small" startIcon={<PersonAddAltOutlinedIcon />} onClick={() => setPicker(role)} disabled={disabled || busy}>
            افزودن
          </Button>
        </Stack>
        <Stack direction="row" flexWrap="wrap" gap={1}>
          {list.length === 0 && <Typography variant="caption" color="text.secondary">—</Typography>}
          {list.map((r) => (
            <Tooltip key={r.employee_id} title={[r.title, r.department].filter(Boolean).join(" — ")}>
              <Chip
                label={r.name}
                color={role === "to" ? "primary" : "default"}
                variant={role === "to" ? "filled" : "outlined"}
                onDelete={disabled ? undefined : () => saveRecipients(recipients.filter((x) => x.employee_id !== r.employee_id))}
              />
            </Tooltip>
          ))}
        </Stack>
      </Stack>
    );
  };

  return (
    <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <Stack spacing={2}>
        {group("to", "گیرنده")}
        {group("cc", "رونوشت")}
        <Box>
          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography variant="body2" fontWeight={700} sx={{ minWidth: 70 }}>پیوست‌ها</Typography>
            <Button size="small" component="label" startIcon={<AttachFileIcon />} disabled={disabled || uploadPct !== null}>
              افزودن فایل
              <input hidden type="file" onChange={(e) => { handleUpload(e.target.files?.[0]); e.target.value = ""; }} />
            </Button>
          </Stack>
          {uploadPct !== null && <LinearProgress variant="determinate" value={uploadPct} sx={{ my: 1 }} />}
          <Stack spacing={0.5} sx={{ mt: 1 }}>
            {attachments.map((a) => (
              <Stack key={a.id} direction="row" alignItems="center" spacing={1}>
                <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }} noWrap>
                  {a.file.name}
                </Typography>
                <Typography variant="caption" color="text.secondary">{formatSize(a.file.size)}</Typography>
                <Chip size="small" label={a.file.status_label} color={a.file.can_download ? "success" : "warning"} variant="outlined" />
                {a.file.can_download && (
                  <IconButton size="small" onClick={() => handleDownload(a)}><DownloadOutlinedIcon fontSize="small" /></IconButton>
                )}
                {!disabled && (
                  <IconButton size="small" onClick={() => handleRemove(a.id)}><DeleteOutlineIcon fontSize="small" /></IconButton>
                )}
              </Stack>
            ))}
          </Stack>
        </Box>
        {error && <Alert severity="error">{error}</Alert>}
      </Stack>
      <PersonPicker
        open={Boolean(picker)}
        title={picker === "cc" ? "افزودن رونوشت" : "افزودن گیرنده"}
        exclude={recipients.map((r) => r.employee_id)}
        onClose={() => setPicker(null)}
        onConfirm={(people) => addPeople(picker, people)}
      />
    </Card>
  );
}
