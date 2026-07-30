import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import { createNotice, fetchMyNotices, publishNotice } from "../api/notices";

const PRIORITY_LABELS = {
  low: { label: "کم", color: "default" },
  normal: { label: "عادی", color: "info" },
  high: { label: "بالا", color: "warning" },
  urgent: { label: "فوری", color: "error" },
};

const STATUS_LABELS = {
  draft: { label: "پیش‌نویس", color: "default" },
  published: { label: "منتشرشده", color: "success" },
  expired: { label: "منقضی‌شده", color: "default" },
};

const TARGET_TYPES = [
  { value: "all", label: "همه کارکنان" },
  { value: "site", label: "یک سایت" },
  { value: "department", label: "یک واحد سازمانی" },
  { value: "role", label: "یک نقش" },
  { value: "employee", label: "یک پرسنل" },
];

const EMPTY_NOTICE = {
  title: "",
  body: "",
  priority: "normal",
  target_type: "all",
  target_id: "",
};

export default function NoticesPage() {
  const [notices, setNotices] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_NOTICE);
  const [error, setError] = useState("");

  function loadNotices() {
    fetchMyNotices().then(setNotices);
  }

  useEffect(() => {
    loadNotices();
  }, []);

  async function handleCreate() {
    setError("");
    try {
      const target =
        form.target_type === "all"
          ? { target_type: "all" }
          : { target_type: form.target_type, target_id: Number(form.target_id) };

      const created = await createNotice({
        title: form.title,
        body: form.body,
        priority: form.priority,
        targets: [target],
      });
      await publishNotice(created.id);
      setDialogOpen(false);
      setForm(EMPTY_NOTICE);
      loadNotices();
    } catch (err) {
      setError(err.response?.data?.detail?.[0]?.msg || err.response?.data?.detail || "ثبت اطلاعیه ناموفق بود");
    }
  }

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 3, flexWrap: "wrap", gap: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            اطلاعیه‌ها
          </Typography>
          <Typography variant="body2" color="text.secondary">
            اطلاعیه‌های منتشرشده مربوط به شما
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddOutlinedIcon />} onClick={() => setDialogOpen(true)}>
          اطلاعیه جدید
        </Button>
      </Box>

      <Stack spacing={2}>
        {notices.length === 0 && (
          <Card variant="outlined" sx={{ p: 4, borderRadius: 3, textAlign: "center" }}>
            <Typography variant="body2" color="text.secondary">
              در حال حاضر اطلاعیه‌ای برای شما ثبت نشده است.
            </Typography>
          </Card>
        )}
        {notices.map((notice) => (
          <Card key={notice.id} variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2}>
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>
                  {notice.title}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  {notice.body}
                </Typography>
              </Box>
              <Stack direction="row" spacing={1}>
                <Chip size="small" label={PRIORITY_LABELS[notice.priority]?.label} color={PRIORITY_LABELS[notice.priority]?.color} />
                <Chip size="small" label={STATUS_LABELS[notice.status]?.label} color={STATUS_LABELS[notice.status]?.color} variant="outlined" />
              </Stack>
            </Stack>
          </Card>
        ))}
      </Stack>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>اطلاعیه جدید</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label="عنوان"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            fullWidth
          />
          <TextField
            label="متن اطلاعیه"
            value={form.body}
            onChange={(e) => setForm({ ...form, body: e.target.value })}
            multiline
            rows={3}
            fullWidth
          />
          <TextField
            select
            label="اولویت"
            value={form.priority}
            onChange={(e) => setForm({ ...form, priority: e.target.value })}
          >
            {Object.entries(PRIORITY_LABELS).map(([value, { label }]) => (
              <MenuItem key={value} value={value}>
                {label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label="مخاطب"
            value={form.target_type}
            onChange={(e) => setForm({ ...form, target_type: e.target.value })}
          >
            {TARGET_TYPES.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </TextField>
          {form.target_type !== "all" && (
            <TextField
              label="شناسه مقصد (Site/Department/Role/Employee ID)"
              type="number"
              value={form.target_id}
              onChange={(e) => setForm({ ...form, target_id: e.target.value })}
            />
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setDialogOpen(false)}>انصراف</Button>
          <Button variant="contained" onClick={handleCreate}>
            ثبت و انتشار
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
