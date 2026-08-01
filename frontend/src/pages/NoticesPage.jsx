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
import { createNotice, fetchAvailableTargets, fetchMyNotices, publishNotice } from "../api/notices";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import { fetchRoles } from "../api/users";

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

const EMPTY_NOTICE = {
  title: "",
  body: "",
  priority: "normal",
  target_type: "",
  target_id: "",
};

export default function NoticesPage() {
  const [notices, setNotices] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_NOTICE);
  const [error, setError] = useState("");

  const [availableTargets, setAvailableTargets] = useState(null);
  const [sites, setSites] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [roles, setRoles] = useState([]);

  function loadNotices() {
    fetchMyNotices().then(setNotices);
  }

  useEffect(() => {
    loadNotices();
    fetchSites().then(setSites);
    fetchDepartments().then(setDepartments);
  }, []);

  async function openDialog() {
    setError("");
    setForm(EMPTY_NOTICE);
    const targets = await fetchAvailableTargets();
    setAvailableTargets(targets);
    if (targets.can_target_role) {
      fetchRoles().then(setRoles);
    }
  }

  // گزینه‌های نوع مخاطب، فقط بر اساس چیزی که کاربر واقعاً اجازه دارد
  const targetTypeOptions = availableTargets
    ? [
        availableTargets.can_target_all && { value: "all", label: "همه سازمان" },
        availableTargets.site_ids.length > 0 && { value: "site", label: "یک سایت" },
        availableTargets.department_ids.length > 0 && { value: "department", label: "یک واحد سازمانی" },
        availableTargets.can_target_role && { value: "role", label: "یک نقش" },
        (availableTargets.site_ids.length > 0 || availableTargets.department_ids.length > 0) && {
          value: "employee",
          label: "یک پرسنل خاص (با شناسه)",
        },
      ].filter(Boolean)
    : [];

  const allowedSites = sites.filter((s) => availableTargets?.site_ids.includes(s.id));
  const allowedDepartments = departments.filter((d) => availableTargets?.department_ids.includes(d.id));

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
        <Button
          variant="contained"
          startIcon={<AddOutlinedIcon />}
          onClick={async () => {
            await openDialog();
            setDialogOpen(true);
          }}
        >
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
            <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2} flexWrap="wrap">
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

          {targetTypeOptions.length === 0 && (
            <Alert severity="warning">
              شما در حال حاضر مجوز ارسال اطلاعیه به هیچ مقصدی ندارید. از بخش «مدیریت دسترسی»
              یک نقش (مثل مدیر سایت یا مدیر منابع انسانی) به حساب خود اختصاص دهید، یا سرپرست
              یک واحد سازمانی شوید.
            </Alert>
          )}

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
            onChange={(e) => setForm({ ...form, target_type: e.target.value, target_id: "" })}
          >
            {targetTypeOptions.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </TextField>

          {form.target_type === "site" && (
            <TextField
              select
              label="انتخاب سایت"
              value={form.target_id}
              onChange={(e) => setForm({ ...form, target_id: e.target.value })}
            >
              {allowedSites.map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.name}
                </MenuItem>
              ))}
            </TextField>
          )}

          {form.target_type === "department" && (
            <TextField
              select
              label="انتخاب واحد سازمانی"
              value={form.target_id}
              onChange={(e) => setForm({ ...form, target_id: e.target.value })}
            >
              {allowedDepartments.map((d) => (
                <MenuItem key={d.id} value={d.id}>
                  {d.name}
                </MenuItem>
              ))}
            </TextField>
          )}

          {form.target_type === "role" && (
            <TextField
              select
              label="انتخاب نقش"
              value={form.target_id}
              onChange={(e) => setForm({ ...form, target_id: e.target.value })}
            >
              {roles.map((r) => (
                <MenuItem key={r.id} value={r.id}>
                  {r.name}
                </MenuItem>
              ))}
            </TextField>
          )}

          {form.target_type === "employee" && (
            <TextField
              label="شناسه پرسنل (Employee ID)"
              type="number"
              value={form.target_id}
              onChange={(e) => setForm({ ...form, target_id: e.target.value })}
              helperText="شناسه پرسنل را از صفحه «پرسنل» پیدا کنید"
            />
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setDialogOpen(false)}>انصراف</Button>
          <Button variant="contained" disabled={!form.target_type} onClick={handleCreate}>
            ثبت و انتشار
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
