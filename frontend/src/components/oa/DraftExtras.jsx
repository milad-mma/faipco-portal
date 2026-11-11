// گیرندگان و پیوست‌های پیش‌نویس نامه (ظاهر شبیه ایمیل) — هر تغییر فوراً در سرور ذخیره می‌شود.
// useDraftExtras: منطق مشترک؛ RecipientRow: ردیف «گیرنده»/«رونوشت» با چیپ؛ AttachmentChips: پیوست‌ها زیر متن؛
// AttachButton: انتخاب چند فایل طبق سقف تنظیمات اتوماسیون سایت.
import { useEffect, useRef, useState } from "react";
import { Box, Chip, IconButton, LinearProgress, Stack, Tooltip, Typography } from "@mui/material";
import PersonAddAltOutlinedIcon from "@mui/icons-material/PersonAddAltOutlined";
import AttachFileIcon from "@mui/icons-material/AttachFile";
import InsertDriveFileOutlinedIcon from "@mui/icons-material/InsertDriveFileOutlined";
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

/** منطق گیرنده/پیوست؛ extras: {recipients, attachments, attachment_limits}، setExtras از والد. */
export function useDraftExtras(draftId, extras, setExtras) {
  const [error, setError] = useState("");
  const [pending, setPending] = useState(0);
  const [upload, setUpload] = useState(null);
  const pendingRef = useRef(new Set());
  const failureRef = useRef("");
  const recipientQueueRef = useRef(Promise.resolve());
  const desiredRecipientsRef = useRef(extras.recipients);
  // When the server returns the latest recipients, synchronize the working copy.
  useEffect(() => {
    if (!pendingRef.current.size) desiredRecipientsRef.current = extras.recipients;
  }, [extras.recipients]);

  function track(operation) {
    pendingRef.current.add(operation);
    setPending(pendingRef.current.size);
    const done = operation.catch((err) => {
      const message = err.response?.data?.detail || err.message || "ذخیره تغییرات ناموفق بود.";
      failureRef.current = message;
      setError(message);
    }).finally(() => {
      pendingRef.current.delete(operation);
      setPending(pendingRef.current.size);
    });
    return done;
  }

  async function awaitIdle() {
    while (pendingRef.current.size) {
      await Promise.allSettled(Array.from(pendingRef.current));
    }
    if (failureRef.current) throw new Error(failureRef.current);
  }

  function saveRecipients(list) {
    desiredRecipientsRef.current = list;
    failureRef.current = "";
    setError("");
    // Serialize updates so two quick changes cannot overwrite each other.
    const operation = recipientQueueRef.current.then(async () => {
      const res = await saveDraftRecipients(
        draftId,
        list.map((r) => ({ employee_id: r.employee_id, role: r.role, selected_via: r.selected_via || "direct" })),
      );
      setExtras((x) => ({ ...x, recipients: res.recipients, attachments: res.attachments }));
    });
    recipientQueueRef.current = operation.catch(() => {});
    return track(operation);
  }

  function addPeople(role, people) {
    const current = desiredRecipientsRef.current;
    const existing = new Set(current.map((r) => r.employee_id));
    return saveRecipients([...current, ...people.filter((p) => !existing.has(p.employee_id)).map((p) => ({ ...p, role }))]);
  }

  function removeRecipient(employeeId) {
    return saveRecipients(desiredRecipientsRef.current.filter((x) => x.employee_id !== employeeId));
  }

  function uploadFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return Promise.resolve();
    failureRef.current = "";
    setError("");
    return track((async () => {
      const lim = extras.attachment_limits || {};
      const room = lim.max_files ? Math.max(0, lim.max_files - extras.attachments.length) : files.length;
      const problems = [];
      let queue = files;
      if (files.length > room) {
        problems.push(`حداکثر ${toPersianDigits(lim.max_files)} پیوست مجاز است؛ ${toPersianDigits(files.length - room)} فایل اضافه نشد.`);
        queue = files.slice(0, room);
      }
      if (lim.max_file_mb) {
        const big = queue.filter((f) => f.size > lim.max_file_mb * 1024 * 1024);
        if (big.length) problems.push(`فایل بزرگ‌تر از ${toPersianDigits(lim.max_file_mb)} مگابایت: ${big.map((f) => f.name).join("، ")}`);
        queue = queue.filter((f) => f.size <= lim.max_file_mb * 1024 * 1024);
      }
      try {
        for (let i = 0; i < queue.length; i += 1) {
          const file = queue[i];
          setUpload({ index: i + 1, total: queue.length, pct: 0, name: file.name });
          try {
            const res = await uploadDraftAttachment(draftId, file, (pct) => setUpload((u) => u ? ({ ...u, pct }) : u));
            setExtras((x) => ({ ...x, attachments: res.attachments }));
          } catch (err) {
            problems.push(`${file.name}: ${err.response?.data?.detail || "بارگذاری ناموفق بود"}`);
          }
        }
      } finally {
        setUpload(null);
      }
      if (problems.length) throw new Error(problems.join("\n"));
    })());
  }

  function removeAttachment(id) {
    failureRef.current = "";
    setError("");
    return track((async () => {
      const res = await removeDraftAttachment(draftId, id);
      setExtras((x) => ({ ...x, attachments: res.attachments }));
    })());
  }

  async function download(a) {
    try {
      saveBlob(await downloadLetterAttachment({ letterId: draftId, attachmentId: a.id, draft: true }), a.file.name);
    } catch {
      setError("دانلود ناموفق بود.");
    }
  }

  return {
    error, setError, busy: pending > 0, pending, upload, awaitIdle,
    addPeople, removeRecipient, uploadFiles, removeAttachment, download,
  };
}

/** ردیف «گیرنده» یا «رونوشت» مثل ایمیل: برچسب، چیپ‌ها و دکمه‌ی افزودن؛ end: محتوای انتهای ردیف (مثلاً «رونوشت»). */
export function RecipientRow({ label, role, extras, api, disabled, end }) {
  const [open, setOpen] = useState(false);
  const list = extras.recipients.filter((r) => r.role === role);
  return (
    <Stack direction="row" alignItems="center" sx={{ px: 2, py: 0.75, minHeight: 48, borderBottom: 1, borderColor: "divider", minWidth: 0 }} gap={1}>
      <Typography variant="body2" color="text.secondary" sx={{ minWidth: 56 }}>{label}</Typography>
      <Stack direction="row" flexWrap="wrap" gap={0.75} sx={{ flex: 1, minWidth: 0 }}>
        {list.map((r) => (
          <Tooltip key={r.employee_id} title={[r.title, r.department].filter(Boolean).join(" — ")}>
            <Chip
              size="small"
              label={r.name}
              variant={role === "to" ? "filled" : "outlined"}
              onDelete={disabled || api.busy ? undefined : () => api.removeRecipient(r.employee_id)}
              sx={{ maxWidth: { xs: 180, sm: 260 }, "& .MuiChip-label": { overflow: "hidden", textOverflow: "ellipsis" } }}
            />
          </Tooltip>
        ))}
        <Tooltip title={role === "cc" ? "افزودن رونوشت" : "افزودن گیرنده"}>
          <span>
            <IconButton size="small" onClick={() => setOpen(true)} disabled={disabled || api.busy}>
              <PersonAddAltOutlinedIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>
      </Stack>
      {end}
      <PersonPicker
        open={open}
        title={role === "cc" ? "افزودن رونوشت" : "افزودن گیرنده"}
        exclude={extras.recipients.map((r) => r.employee_id)}
        onClose={() => setOpen(false)}
        onConfirm={(people) => {
          setOpen(false);
          api.addPeople(role, people);
        }}
      />
    </Stack>
  );
}

/** پیوست‌ها به‌صورت کارت‌های کوچک زیر متن (مثل جیمیل) + نوار پیشرفت بارگذاری. */
export function AttachmentChips({ extras, api, disabled }) {
  if (!extras.attachments.length && !api.upload) return null;
  return (
    <Box sx={{ px: 2, py: 1.5 }}>
      <Stack direction="row" flexWrap="wrap" gap={1}>
        {extras.attachments.map((a) => (
          <Chip
            key={a.id}
            icon={<InsertDriveFileOutlinedIcon />}
            variant="outlined"
            color={a.file.can_download ? "default" : "warning"}
            label={`${a.file.name} (${formatSize(a.file.size)})${a.file.can_download ? "" : ` — ${a.file.status_label}`}`}
            onClick={a.file.can_download ? () => api.download(a) : undefined}
            onDelete={disabled || api.busy ? undefined : () => api.removeAttachment(a.id)}
            sx={{ maxWidth: { xs: "100%", sm: 320 }, "& .MuiChip-label": { overflow: "hidden", textOverflow: "ellipsis" } }}
          />
        ))}
      </Stack>
      {api.upload && (
        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary">
            بارگذاری {toPersianDigits(api.upload.index)} از {toPersianDigits(api.upload.total)}: {api.upload.name}
          </Typography>
          <LinearProgress variant="determinate" value={api.upload.pct} />
        </Box>
      )}
    </Box>
  );
}

/** دکمه‌ی پیوست (گیره) با انتخاب چند فایل. */
export function AttachButton({ extras, api, disabled }) {
  const input = useRef(null);
  const lim = extras.attachment_limits;
  const full = lim?.max_files && extras.attachments.length >= lim.max_files;
  const tip = lim
    ? `پیوست فایل — حداکثر ${toPersianDigits(lim.max_files)} فایل، هر فایل تا ${toPersianDigits(lim.max_file_mb)} مگابایت`
    : "پیوست فایل";
  return (
    <>
      <Tooltip title={full ? "به سقف تعداد پیوست رسیده‌اید" : tip}>
        <span>
          <IconButton onClick={() => input.current?.click()} disabled={disabled || api.busy || Boolean(api.upload) || Boolean(full)}>
            <AttachFileIcon />
          </IconButton>
        </span>
      </Tooltip>
      <input
        ref={input}
        hidden
        type="file"
        multiple
        onChange={(e) => {
          api.uploadFiles(e.target.files);
          e.target.value = "";
        }}
      />
    </>
  );
}
