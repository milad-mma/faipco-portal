// تنظیمات اعلان شخصی اتوماسیون: هر کس برای خودش تعیین می‌کند برای کدام رویدادها اعلان گوشی/مرورگر بگیرد (پیش‌فرض همه).
// شمارنده‌ی منو و کارتابل همیشه کار می‌کنند؛ این‌جا فقط اعلان Push است.
import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  Switch,
  Typography,
} from "@mui/material";
import { fetchNotificationPrefs, saveNotificationPrefs } from "../../api/automationLetters";

export default function NotificationPrefsDialog({ open, onClose }) {
  const [events, setEvents] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setError("");
    setEvents(null);
    fetchNotificationPrefs()
      .then((d) => setEvents(d.events))
      .catch((err) => setError(err.response?.data?.detail || "دریافت تنظیمات ناموفق بود."));
  }, [open]);

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      await saveNotificationPrefs(Object.fromEntries(events.map((e) => [e.key, e.enabled])));
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره ناموفق بود.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>تنظیمات اعلان نامه‌ها</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          برای کدام موارد اعلان گوشی/مرورگر بگیرید؟ شمارنده‌ی منو و کارتابل همیشه به‌روز است.
        </Typography>
        {!events && !error && <CircularProgress size={22} />}
        {events && (
          <Stack>
            {events.map((e) => (
              <FormControlLabel
                key={e.key}
                control={
                  <Switch
                    checked={e.enabled}
                    onChange={(ev) => setEvents((list) => list.map((x) => (x.key === e.key ? { ...x, enabled: ev.target.checked } : x)))}
                  />
                }
                label={e.label}
              />
            ))}
          </Stack>
        )}
        {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" onClick={handleSave} disabled={!events || saving}>
          {saving ? "در حال ذخیره..." : "ذخیره"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
