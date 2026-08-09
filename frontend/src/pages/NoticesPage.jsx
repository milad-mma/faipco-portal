import { useEffect, useState } from "react";
import {
  Alert,
  Autocomplete,
  Backdrop,
  Box,
  Button,
  Card,
  Checkbox,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import MailOutlineIcon from "@mui/icons-material/MailOutline";
import DraftsOutlinedIcon from "@mui/icons-material/DraftsOutlined";
import {
  createNotice,
  fetchAvailableTargets,
  fetchMyNotices,
  fetchSentByMe,
  markNoticeRead,
  publishNotice,
} from "../api/notices";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import { fetchEmployees } from "../api/employees";
import NoticeReportTable from "../components/NoticeReportTable";

const PRIORITY_LABELS = {
  low: { label: "کم", color: "default" },
  normal: { label: "عادی", color: "info" },
  high: { label: "بالا", color: "warning" },
  urgent: { label: "فوری", color: "error" },
};

const EMPTY_FORM = {
  title: "",
  body: "",
  priority: "normal",
  targetAll: false,
  siteIds: [],
  departmentIds: [],
  employees: [],
  supervisors: [],
};

function ReceivedNoticeCard({ notice, onOpened }) {
  const [expanded, setExpanded] = useState(false);
  const isUnread = !notice.is_read;

  function handleToggle() {
    if (!expanded && isUnread) {
      markNoticeRead(notice.id).catch(() => {});
      onOpened?.(notice.id);
    }
    setExpanded((v) => !v);
  }

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        overflow: "hidden",
        borderInlineStart: isUnread ? "4px solid" : "4px solid transparent",
        borderInlineStartColor: isUnread ? "secondary.main" : "transparent",
        backgroundColor: isUnread ? "rgba(224, 164, 88, 0.06)" : "transparent",
      }}
    >
      <Box
        onClick={handleToggle}
        sx={{
          p: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          cursor: "pointer",
          gap: 2,
          "&:hover": { backgroundColor: "action.hover" },
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ minWidth: 0 }}>
          {isUnread ? <MailOutlineIcon color="secondary" /> : <DraftsOutlinedIcon color="disabled" />}
          <Box sx={{ minWidth: 0 }}>
            <Typography
              variant="body1"
              fontWeight={isUnread ? 700 : 400}
              color={isUnread ? "text.primary" : "text.secondary"}
              noWrap
            >
              {notice.title}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {new Date(notice.created_at).toLocaleString("fa-IR")}
            </Typography>
          </Box>
        </Stack>
        <Chip
          size="small"
          label={PRIORITY_LABELS[notice.priority]?.label}
          color={PRIORITY_LABELS[notice.priority]?.color}
        />
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ px: 2, pb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            {notice.body}
          </Typography>
        </Box>
      </Collapse>
    </Card>
  );
}

export default function NoticesPage() {
  const [tab, setTab] = useState("received");
  const [notices, setNotices] = useState([]);
  const [sentNotices, setSentNotices] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [availableTargets, setAvailableTargets] = useState(null);
  const [sites, setSites] = useState([]);
  const [departments, setDepartments] = useState([]);

  const [employeeSearch, setEmployeeSearch] = useState("");
  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [employeeSearchLoading, setEmployeeSearchLoading] = useState(false);

  function loadNotices() {
    fetchMyNotices().then(setNotices);
  }

  function loadSentNotices() {
    fetchSentByMe().then(setSentNotices);
  }

  useEffect(() => {
    loadNotices();
    fetchAvailableTargets().then(setAvailableTargets);
    fetchSites().then(setSites);
    fetchDepartments().then(setDepartments);
  }, []);

  // پیام از Service Worker وقتی یک Push جدید می‌رسد — لیست را بدون Reload
  // صفحه، دوباره از سرور می‌خوانیم (چه در تب دریافتی، چه ارسالی من).
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    function handleMessage(event) {
      if (event.data?.type === "faipco-notice-push") {
        loadNotices();
        if (tab === "sent") loadSentNotices();
      }
    }
    navigator.serviceWorker.addEventListener("message", handleMessage);
    return () => navigator.serviceWorker.removeEventListener("message", handleMessage);
  }, [tab]);

  useEffect(() => {
    if (tab === "sent") loadSentNotices();
  }, [tab]);

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

  function handleMarkedRead(noticeId) {
    setNotices((prev) => prev.map((n) => (n.id === noticeId ? { ...n, is_read: true } : n)));
  }

  async function handleCreate() {
    if (isSubmitting) return; // جلوگیری از ارسال تکراری با کلیک چندباره
    setError("");

    const targets = [];
    if (form.targetAll) targets.push({ target_type: "all" });
    form.siteIds.forEach((id) => targets.push({ target_type: "site", target_id: id }));
    form.departmentIds.forEach((id) => targets.push({ target_type: "department", target_id: id }));

    const employeeIds = new Set();
    [...form.employees, ...form.supervisors].forEach((emp) => {
      if (!employeeIds.has(emp.id)) {
        employeeIds.add(emp.id);
        targets.push({ target_type: "employee", target_id: emp.id });
      }
    });

    if (targets.length === 0) {
      setError("حداقل یک مخاطب (سایت، واحد یا شخص) انتخاب کنید.");
      return;
    }

    setIsSubmitting(true);
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
      if (tab === "sent") loadSentNotices();
    } catch (err) {
      setError(err.response?.data?.detail?.[0]?.msg || err.response?.data?.detail || "ثبت اطلاعیه ناموفق بود");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, flexWrap: "wrap", gap: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            اطلاعیه‌ها
          </Typography>
        </Box>
        {canCreateAnything && (
          <Button variant="contained" startIcon={<AddOutlinedIcon />} onClick={openDialog}>
            اطلاعیه جدید
          </Button>
        )}
      </Box>

      {canCreateAnything && (
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
          <Tab value="received" label="دریافتی" />
          <Tab value="sent" label="ارسالی من" />
        </Tabs>
      )}

      {tab === "received" && (
        <Stack spacing={1.5}>
          {notices.length === 0 && (
            <Card variant="outlined" sx={{ p: 4, borderRadius: 3, textAlign: "center" }}>
              <Typography variant="body2" color="text.secondary">
                در حال حاضر اطلاعیه‌ای برای شما ثبت نشده است.
              </Typography>
            </Card>
          )}
          {notices.map((notice) => (
            <ReceivedNoticeCard key={notice.id} notice={notice} onOpened={handleMarkedRead} />
          ))}
        </Stack>
      )}

      {tab === "sent" && (
        <Card variant="outlined" sx={{ borderRadius: 3, p: 1 }}>
          <NoticeReportTable
            notices={sentNotices}
            showSender={false}
            allowDelete
            onChanged={loadSentNotices}
          />
        </Card>
      )}

      <Dialog
        open={dialogOpen}
        onClose={() => !isSubmitting && setDialogOpen(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>اطلاعیه جدید</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1, position: "relative" }}>
          {/* حین ارسال، کل فرم غیرقابل‌دستکاری می‌شود تا کلیک چندباره ممکن نباشد */}
          <Backdrop
            open={isSubmitting}
            sx={{
              position: "absolute",
              zIndex: 10,
              backgroundColor: "rgba(255,255,255,0.7)",
              borderRadius: 2,
            }}
          >
            <Stack alignItems="center" spacing={1}>
              <CircularProgress size={32} />
              <Typography variant="caption" color="text.secondary">
                در حال ثبت و انتشار...
              </Typography>
            </Stack>
          </Backdrop>

          {error && <Alert severity="error">{error}</Alert>}

          <TextField
            label="عنوان"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            fullWidth
            disabled={isSubmitting}
          />
          <TextField
            label="متن اطلاعیه"
            value={form.body}
            onChange={(e) => setForm({ ...form, body: e.target.value })}
            multiline
            rows={3}
            fullWidth
            disabled={isSubmitting}
          />
          <TextField
            select
            label="اولویت"
            value={form.priority}
            onChange={(e) => setForm({ ...form, priority: e.target.value })}
            disabled={isSubmitting}
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
                  disabled={isSubmitting}
                />
              }
              label="ارسال به کل سازمان (Broadcast)"
            />
          )}

          {allowedSites.length > 0 && (
            <Autocomplete
              multiple
              disabled={isSubmitting}
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
              disabled={isSubmitting}
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

          {availableTargets?.supervisor_employees?.length > 0 && (
            <Autocomplete
              multiple
              disabled={isSubmitting}
              options={availableTargets.supervisor_employees}
              getOptionLabel={(e) => `${e.first_name} ${e.last_name} (${e.personnel_code})`}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              value={form.supervisors}
              onChange={(_, selected) => setForm({ ...form, supervisors: selected })}
              renderInput={(params) => (
                <TextField {...params} label="میان‌بر: ارسال به یک یا چند سرپرست واحد" />
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
            />
          )}

          {availableTargets?.can_target_employee && (
            <Autocomplete
              multiple
              disabled={isSubmitting}
              options={employeeOptions}
              loading={employeeSearchLoading}
              filterOptions={(x) => x}
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
          <Button onClick={() => setDialogOpen(false)} disabled={isSubmitting}>
            انصراف
          </Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={isSubmitting}
            startIcon={isSubmitting ? <CircularProgress size={16} color="inherit" /> : null}
          >
            {isSubmitting ? "در حال ارسال..." : "ثبت و انتشار"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
