import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import { fetchSites } from "../api/sites";
import JalaliDateTimePicker from "../components/JalaliDateTimePicker";
import {
  createEvaluationPeriod,
  fetchEvaluationPeriods,
  updateEvaluationPeriod,
  updateEvaluationPeriodStatus,
  deleteEvaluationPeriod,
} from "../api/evaluationPeriods";

const STATUS_LABELS = {
  draft: "پیش‌نویس",
  scheduled: "زمان‌بندی‌شده",
  active: "فعال",
  closed: "بسته‌شده",
  archived: "بایگانی‌شده",
};

const STATUS_COLORS = {
  draft: "default",
  scheduled: "info",
  active: "success",
  closed: "warning",
  archived: "default",
};

const EMPTY_FORM = { site_id: "", title: "", description: "", start_date: null, end_date: null };

function PeriodDialog({ open, onClose, onSaved, sites, editingPeriod }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (editingPeriod) {
      setForm({
        site_id: editingPeriod.site_id ?? "",
        title: editingPeriod.title,
        description: editingPeriod.description || "",
        start_date: new Date(editingPeriod.start_date),
        end_date: new Date(editingPeriod.end_date),
      });
    } else {
      setForm({ ...EMPTY_FORM, start_date: new Date(), end_date: new Date() });
    }
    setError("");
  }, [editingPeriod, open]);

  async function handleSave() {
    setError("");
    setIsSaving(true);
    try {
      const payload = {
        site_id: form.site_id === "" ? null : form.site_id,
        title: form.title,
        description: form.description || null,
        start_date: form.start_date.toISOString(),
        end_date: form.end_date.toISOString(),
      };
      if (editingPeriod) {
        await updateEvaluationPeriod(editingPeriod.id, payload);
      } else {
        await createEvaluationPeriod(payload);
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره دوره ارزیابی با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{editingPeriod ? "ویرایش دوره ارزیابی" : "دوره ارزیابی جدید"}</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        <TextField
          select
          label="سایت (اختیاری - خالی یعنی همه سایت‌ها)"
          value={form.site_id}
          onChange={(e) => setForm({ ...form, site_id: e.target.value })}
        >
          <MenuItem value="">همه سایت‌ها</MenuItem>
          {sites.map((site) => (
            <MenuItem key={site.id} value={site.id}>
              {site.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label="عنوان دوره"
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
          placeholder="مثلاً ارزیابی عملکرد نیمه اول ۱۴۰۵"
        />
        <TextField
          label="توضیحات (اختیاری)"
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          multiline
          minRows={2}
        />
        {form.start_date && (
          <JalaliDateTimePicker
            label="تاریخ و ساعت شروع"
            value={form.start_date}
            onChange={(d) => setForm({ ...form, start_date: d })}
          />
        )}
        {form.end_date && (
          <JalaliDateTimePicker
            label="تاریخ و ساعت پایان"
            value={form.end_date}
            onChange={(d) => setForm({ ...form, end_date: d })}
          />
        )}
        {error && <Alert severity="error">{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isSaving}>
          انصراف
        </Button>
        <Button variant="contained" onClick={handleSave} disabled={isSaving || !form.title.trim()}>
          {isSaving ? "در حال ذخیره..." : "ذخیره"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function EvaluationPeriodsPage() {
  const [sites, setSites] = useState([]);
  const [periods, setPeriods] = useState([]);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPeriod, setEditingPeriod] = useState(null);

  useEffect(() => {
    fetchSites().then(setSites);
  }, []);

  function loadPeriods() {
    setError("");
    fetchEvaluationPeriods()
      .then(setPeriods)
      .catch((err) => setError(err.response?.data?.detail || "دریافت دوره‌های ارزیابی با خطا مواجه شد."));
  }

  useEffect(loadPeriods, []);

  function siteName(siteId) {
    if (siteId === null) return "همه سایت‌ها";
    return sites.find((s) => s.id === siteId)?.name || "—";
  }

  async function handleStatusChange(period, status) {
    try {
      await updateEvaluationPeriodStatus(period.id, status);
      loadPeriods();
    } catch (err) {
      setError(err.response?.data?.detail || "تغییر وضعیت با خطا مواجه شد.");
    }
  }

  async function handleDelete(period) {
    try {
      await deleteEvaluationPeriod(period.id);
      loadPeriods();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف دوره ارزیابی با خطا مواجه شد.");
    }
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h5" fontWeight={700}>
          دوره‌های ارزیابی
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddOutlinedIcon />}
          onClick={() => {
            setEditingPeriod(null);
            setDialogOpen(true);
          }}
        >
          دوره جدید
        </Button>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>عنوان</TableCell>
              <TableCell>سایت</TableCell>
              <TableCell>بازه</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {periods.map((period) => (
              <TableRow key={period.id}>
                <TableCell>{period.title}</TableCell>
                <TableCell>{siteName(period.site_id)}</TableCell>
                <TableCell>
                  {new Date(period.start_date).toLocaleDateString("fa-IR")} تا{" "}
                  {new Date(period.end_date).toLocaleDateString("fa-IR")}
                </TableCell>
                <TableCell>
                  <TextField
                    select
                    size="small"
                    value={period.status}
                    onChange={(e) => handleStatusChange(period, e.target.value)}
                    sx={{ minWidth: 150 }}
                  >
                    {Object.entries(STATUS_LABELS).map(([value, label]) => (
                      <MenuItem key={value} value={value}>
                        <Chip size="small" color={STATUS_COLORS[value]} label={label} />
                      </MenuItem>
                    ))}
                  </TextField>
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={1}>
                    {period.status === "draft" && (
                      <>
                        <Button
                          size="small"
                          onClick={() => {
                            setEditingPeriod(period);
                            setDialogOpen(true);
                          }}
                        >
                          ویرایش
                        </Button>
                        <Button size="small" color="error" onClick={() => handleDelete(period)}>
                          حذف
                        </Button>
                      </>
                    )}
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <PeriodDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSaved={loadPeriods}
        sites={sites}
        editingPeriod={editingPeriod}
      />
    </Box>
  );
}
