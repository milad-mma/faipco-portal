import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from "@mui/material";
import { errText } from "./loans/LoanShared";

/**
 * دیالوگ گرفتن «دلیل/توضیح» برای تأیید، رد یا لغو (مشترک وام و مساعده).
 * ورودی: open، title، confirmLabel، required (دلیل اجباری — برای رد)، warning (متن راهنما)، onClose، onConfirm(note) async.
 * خطای onConfirm داخل همین دیالوگ نمایش داده می‌شود.
 */
export default function NoteDialog({
  open,
  title,
  confirmLabel,
  required,
  warning,
  onClose,
  onConfirm,
}) {
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setNote("");
      setError("");
    }
  }, [open]);
  const confirm = async () => {
    setSaving(true);
    setError("");
    try {
      await onConfirm(note);
    } catch (e) {
      setError(errText(e, "عملیات ناموفق بود"));
    } finally {
      setSaving(false);
    }
  };
  return (
    <Dialog
      open={open}
      onClose={saving ? undefined : onClose}
      fullWidth
      maxWidth="xs"
    >
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        {warning && (
          <Alert severity="info" sx={{ mb: 2 }}>
            {warning}
          </Alert>
        )}
        <TextField
          label={required ? "دلیل" : "توضیح (اختیاری)"}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          fullWidth
          multiline
          minRows={2}
          autoFocus
          inputProps={{ maxLength: 2000 }}
        />
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          انصراف
        </Button>
        <Button
          variant="contained"
          onClick={confirm}
          disabled={saving || (required && !note.trim())}
        >
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
