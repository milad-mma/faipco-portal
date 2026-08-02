import { useEffect, useState } from "react";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Card,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import { createNotice, fetchAvailableTargets, fetchMyNotices, publishNotice } from "../api/notices";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import { fetchEmployees } from "../api/employees";

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

const EMPTY_FORM = {
  title: "",
  body: "",
  priority: "normal",
  targetAll: false,
  siteIds: [],
  departmentIds: [],
  employees: [], // آرایه‌ای از خودِ شیء Employee (برای نمایش نام در Chip ها)
};

export default function NoticesPage() {
  const [notices, setNotices] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");

  const [availableTargets, setAvailableTargets] = useState(null);
  const [sites, setSites] = useState([]);
  const [departments, setDepartments] = useState([]);

  const [employeeSearch, setEmployeeSearch] = useState("");
  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [employeeSearchLoading, setEmployeeSearchLoading] = useState(false);

  function loadNotices() {
    fetchMyNotices().then(setNotices);
  }

  useEffect(() => {
    loadNotices();
    fetchAvailableTargets().then(setAvailableTargets);
    fetchSites().then(setSites);
    fetchDepartments().then(setDepartments);
  }, []);

  // جستجوی پرسنل با کمی تأخیر، برای انتخاب گیرنده‌های خاص اطلاعیه
  useEffect(() => {
    if (!employeeSearch) {
      setEmployeeOptions([]);
      return;
    }
    setEmployeeSearchLoading(true);
    const timer = setTimeout(() => {
      fetchEmployees({ search: employeeSearch })
        .then(setEmployeeOptions)
        .finally(() => setEmployeeSearchLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [employeeSearch]);

  const canCreateAnything =
    availableTargets &&
    (availableTargets.can_target_all ||
      availableTargets.site_ids.length > 0 ||
      availableTargets.department_ids.length > 0 ||
      availableTargets.can_target_employee);

  const allowedSites = sites.filter((s) => availableTargets?.site_ids.includes(s.id));
  const allowedDepartments = departments.filter((d) => availableTargets?.department_ids.includes(d.id));

  function openDialog() {
    setError("");
    setForm(EMPTY_FORM);
    setEmployeeSearch("");
    setEmployeeOptions([]);
    setDialogOpen(true);
  }

  async function handleCreate() {
    setError("");
    const targets = [];
    if (form.targetAll) targets.push({ target_type: "all" });
    form.siteIds.forEach((id) => targets.push({ target_type: "site", target_id: id }));
    form.departmentIds.forEach((id) => targets.push({ target_type: "department", target_id: id }));
    form.employees.forEach((emp) => targets.push({ target_type: "employee", target_id: emp.id }));

    if (targets.length === 0) {
      setError("حداقل یک مخاطب (سایت، واحد یا شخص) انتخاب کنید.");
      return;
    }

    try {
      const created = await createNotice({
        title: form.title,
        body: form.body,
        priority: form.priority,
        targets,
      });
      await publishNotice(created.id);
      setDialogOpen(false);
      setForm(EMPTY_FORM);
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
        {canCreateAnything && (
          <Button variant="contained" startIcon={<AddOutlinedIcon />} onClick={openDialog}>
            اطلاعیه جدید
          </Button>
        )}
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

          <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 1 }}>
            مخاطبان
          </Typography>

          {availableTargets?.can_target_all && (
            <FormControlLabel
              control={
                <Checkbox
                  checked={form.targetAll}
                  onChange={(e) => setForm({ ...form, targetAll: e.target.checked })}
                />
              }
              label="ارسال به کل سازمان (Broadcast)"
            />
          )}

          {allowedSites.length > 0 && (
            <Autocomplete
              multiple
              options={allowedSites}
              getOptionLabel={(s) => s.name}
              value={allowedSites.filter((s) => form.siteIds.includes(s.id))}
              onChange={(_, selected) => setForm({ ...form, siteIds: selected.map((s) => s.id) })}
              renderInput={(params) => <TextField {...params} label="ارسال به کل این سایت‌ها" />}
              renderTags={(value, getTagProps) =>
                value.map((option, index) => (
                  <Chip size="small" label={option.name} {...getTagProps({ index })} key={option.id} />
                ))
              }
            />
          )}

          {allowedDepartments.length > 0 && (
            <Autocomplete
              multiple
              options={allowedDepartments}
              getOptionLabel={(d) => d.name}
              value={allowedDepartments.filter((d) => form.departmentIds.includes(d.id))}
              onChange={(_, selected) => setForm({ ...form, departmentIds: selected.map((d) => d.id) })}
              renderInput={(params) => <TextField {...params} label="ارسال به یک یا چند واحد سازمانی" />}
              renderTags={(value, getTagProps) =>
                value.map((option, index) => (
                  <Chip size="small" label={option.name} {...getTagProps({ index })} key={option.id} />
                ))
              }
            />
          )}

          {availableTargets?.can_target_employee && (
            <Autocomplete
              multiple
              options={employeeOptions}
              loading={employeeSearchLoading}
              filterOptions={(x) => x} // فیلتر توسط خودِ Backend انجام می‌شود
              getOptionLabel={(e) => `${e.first_name} ${e.last_name} (${e.personnel_code})`}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              value={form.employees}
              onChange={(_, selected) => setForm({ ...form, employees: selected })}
              onInputChange={(_, value) => setEmployeeSearch(value)}
              renderInput={(params) => (
                <TextField {...params} label="ارسال به یک یا چند شخص خاص (جستجو کنید)" />
              )}
              renderTags={(value, getTagProps) =>
                value.map((option, index) => (
                  <Chip
                    size="small"
                    label={`${option.first_name} ${option.last_name}`}
                    {...getTagProps({ index })}
                    key={option.id}
                  />
                ))
              }
              noOptionsText="برای جستجو تایپ کنید..."
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
