import { useEffect, useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  MenuItem,
  Stack,
  Switch,
  FormControlLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import BackLink from "../components/BackLink";
import EmployeePicker from "../components/EmployeePicker";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import {
  addLeaveRequestType,
  deleteLeaveRequestType,
  fetchLeaveRequestApprovers,
  fetchLeaveRequestMapping,
  fetchLeaveRequestTypes,
  removeLeaveRequestApprover,
  saveLeaveRequestMapping,
  setLeaveRequestApprover,
  updateLeaveRequestType,
} from "../api/leaveRequestsAdmin";

const DEFAULT_MAPPING = {
  table_name: "WF_Requests",
  request_id_column: "RequestId",
  emp_no_column: "Emp_No",
  submitting_date_column: "SubmittingDate",
  card_no_column: "Card_No",
  start_date_column: "StartDate",
  end_date_column: "EndDate",
  start_hour_column: "StartHour",
  end_hour_column: "EndHour",
  duration_column: "Duration",
  is_final_approved_column: "IsFinalApproved",
  approval_by_manager_column: "ApprovalByManagerEmp_No",
  approval_date_column: "ApprovalDate",
  operations_id_column: "OperationsID",
  description_column: "Description",
  cur_emp_no_column: "CurEmp_NO",
  manager_idea_column: "ManagerIdea",
  is_first_time_shift_column: "IsFirstTimeShift",
  persian_start_date_column: "PersianStartDate",
  application_id_column: "ApplicationId",
  source_column: "Source",
  destination_column: "Distination",
  action_id_column: "ActionId",
  branch_code_column: "BranchCode",
  branch_code_value: null,
  application_id_value: 4,
};

function MappingSection({ siteId, onError }) {
  const [mapping, setMapping] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState("");

  useEffect(() => {
    fetchLeaveRequestMapping(siteId).then((data) => setMapping(data || DEFAULT_MAPPING));
  }, [siteId]);

  function updateField(key, value) {
    setMapping((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    setSavedMessage("");
    setIsSaving(true);
    try {
      await saveLeaveRequestMapping(siteId, mapping);
      setSavedMessage("ذخیره شد.");
    } catch (err) {
      onError(err.response?.data?.detail || "ذخیره تنظیمات با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  if (mapping === null) return null;

  const fieldGroups = [
    {
      title: "اتصال پایه",
      fields: [
        ["table_name", "نام جدول"],
        ["request_id_column", "ستون شناسه درخواست"],
        ["emp_no_column", "ستون کد پرسنلی"],
        ["submitting_date_column", "ستون تاریخ ثبت"],
        ["card_no_column", "ستون Card_No"],
      ],
    },
    {
      title: "تاریخ/ساعت درخواست",
      fields: [
        ["start_date_column", "ستون تاریخ شروع"],
        ["end_date_column", "ستون تاریخ پایان"],
        ["start_hour_column", "ستون ساعت شروع"],
        ["end_hour_column", "ستون ساعت پایان"],
        ["duration_column", "ستون مدت"],
        ["persian_start_date_column", "ستون تاریخ شمسی شروع"],
      ],
    },
    {
      title: "تأیید/رد",
      fields: [
        ["is_final_approved_column", "ستون تأیید نهایی"],
        ["approval_by_manager_column", "ستون تأییدکننده"],
        ["approval_date_column", "ستون تاریخ تأیید"],
        ["cur_emp_no_column", "ستون تأییدکننده فعلی"],
        ["manager_idea_column", "ستون نظر تأییدکننده"],
      ],
    },
    {
      title: "سایر",
      fields: [
        ["operations_id_column", "ستون نوع عملیات"],
        ["description_column", "ستون توضیحات"],
        ["is_first_time_shift_column", "ستون IsFirstTimeShift"],
        ["application_id_column", "ستون ApplicationId"],
        ["source_column", "ستون مبدأ (ماموریت)"],
        ["destination_column", "ستون مقصد (ماموریت)"],
        ["action_id_column", "ستون ActionId (اختیاری)"],
      ],
    },
  ];

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        نام جدول/ستون‌های جدول خام WF_Requests این سایت - مقادیر پیش‌فرض دقیقاً مطابق نمونه‌ای است که
        بررسی شد؛ فقط اگر نصب شما نام‌گذاری متفاوتی دارد تغییر دهید.
      </Typography>

      {fieldGroups.map((group) => (
        <Box key={group.title} sx={{ mb: 2 }}>
          <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
            {group.title}
          </Typography>
          <Stack direction="row" flexWrap="wrap" useFlexGap spacing={1.5}>
            {group.fields.map(([key, label]) => (
              <TextField
                key={key}
                size="small"
                label={label}
                value={mapping[key] || ""}
                onChange={(e) => updateField(key, e.target.value)}
                sx={{ minWidth: 220 }}
              />
            ))}
          </Stack>
        </Box>
      ))}

      <Box sx={{ mb: 2 }}>
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
          دیتابیس/جدول مشترک بین چند سایت (اختیاری)
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
          فقط اگر این سایت با سایت‌های دیگر یک دیتابیس/جدول مشترک دارد پر کنید - مقدار BranchCode
          مخصوص همین سایت.
        </Typography>
        <Stack direction="row" spacing={1.5}>
          <TextField
            size="small"
            label="ستون BranchCode"
            value={mapping.branch_code_column || ""}
            onChange={(e) => updateField("branch_code_column", e.target.value || null)}
          />
          <TextField
            size="small"
            type="number"
            label="مقدار BranchCode این سایت"
            value={mapping.branch_code_value ?? ""}
            onChange={(e) => updateField("branch_code_value", e.target.value === "" ? null : Number(e.target.value))}
          />
        </Stack>
      </Box>

      {savedMessage && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {savedMessage}
        </Alert>
      )}
      <Button variant="contained" onClick={handleSave} disabled={isSaving}>
        {isSaving ? "در حال ذخیره..." : "ذخیره تنظیمات"}
      </Button>
    </Box>
  );
}

function TypesSection({ siteId, onError }) {
  const [types, setTypes] = useState(null);
  const [title, setTitle] = useState("");
  const [isMission, setIsMission] = useState(false);
  const [isHourly, setIsHourly] = useState(false);
  const [actionId, setActionId] = useState("1");
  const [actionIdTouched, setActionIdTouched] = useState(false);

  // ⚠️ طبق تحلیل دقیق داده واقعی WF_Requests (۷ ردیف تستی): ActionId
  // فقط به همین دو بعد بستگی دارد - این فقط یک پیشنهاد خودکار است؛ اگر
  // کاربر دستی مقدار را عوض کند، دیگر خودکار به‌روزرسانی نمی‌شود.
  function suggestActionId(mission, hourly) {
    if (!mission && !hourly) return "1";
    if (mission && !hourly) return "2";
    if (!mission && hourly) return "3";
    return "9";
  }

  function handleMissionChange(value) {
    setIsMission(value);
    if (!actionIdTouched) setActionId(suggestActionId(value, isHourly));
  }

  function handleHourlyChange(value) {
    setIsHourly(value);
    if (!actionIdTouched) setActionId(suggestActionId(isMission, value));
  }

  function load() {
    fetchLeaveRequestTypes(siteId).then(setTypes);
  }

  useEffect(load, [siteId]);

  async function handleAdd() {
    if (!title.trim()) return;
    try {
      await addLeaveRequestType(siteId, {
        title: title.trim(),
        is_mission: isMission,
        is_hourly: isHourly,
        action_id: actionId === "" ? null : Number(actionId),
      });
      setTitle("");
      setIsMission(false);
      setIsHourly(false);
      setActionId("1");
      setActionIdTouched(false);
      load();
    } catch (err) {
      onError(err.response?.data?.detail || "افزودن نوع درخواست با خطا مواجه شد.");
    }
  }

  async function handleToggleActive(type) {
    try {
      await updateLeaveRequestType(type.id, { is_active: !type.is_active });
      load();
    } catch (err) {
      onError(err.response?.data?.detail || "ویرایش نوع درخواست با خطا مواجه شد.");
    }
  }

  async function handleDelete(type) {
    try {
      await deleteLeaveRequestType(type.id);
      load();
    } catch (err) {
      onError(err.response?.data?.detail || "حذف نوع درخواست با خطا مواجه شد.");
    }
  }

  if (types === null) return null;

  return (
    <Box>
      <TableContainer sx={{ mb: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>عنوان</TableCell>
              <TableCell>نوع</TableCell>
              <TableCell>واحد زمان</TableCell>
              <TableCell>ActionId</TableCell>
              <TableCell>فعال</TableCell>
              <TableCell>حذف</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {types.map((t) => (
              <TableRow key={t.id}>
                <TableCell>{t.title}</TableCell>
                <TableCell>{t.is_mission ? "ماموریت" : "مرخصی"}</TableCell>
                <TableCell>{t.is_hourly ? "ساعتی" : "روزانه"}</TableCell>
                <TableCell>{t.action_id ?? "—"}</TableCell>
                <TableCell>
                  <Switch checked={t.is_active} onChange={() => handleToggleActive(t)} size="small" />
                </TableCell>
                <TableCell>
                  <IconButton size="small" onClick={() => handleDelete(t)}>
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
        <TextField size="small" label="عنوان نوع جدید" value={title} onChange={(e) => setTitle(e.target.value)} />
        <FormControlLabel
          control={<Switch checked={isMission} onChange={(e) => handleMissionChange(e.target.checked)} />}
          label="ماموریت (خاموش=مرخصی)"
        />
        <FormControlLabel
          control={<Switch checked={isHourly} onChange={(e) => handleHourlyChange(e.target.checked)} />}
          label="ساعتی (خاموش=روزانه)"
        />
        <TextField
          size="small"
          type="number"
          label="ActionId (پیشنهادی، قابل‌ویرایش)"
          value={actionId}
          onChange={(e) => {
            setActionId(e.target.value);
            setActionIdTouched(true);
          }}
          sx={{ width: 200 }}
        />
        <Button startIcon={<AddOutlinedIcon />} onClick={handleAdd} disabled={!title.trim()}>
          افزودن
        </Button>
      </Stack>
    </Box>
  );
}

function ApproversSection({ siteId, onError }) {
  const [departments, setDepartments] = useState(null);
  const [approvers, setApprovers] = useState(null);

  function load() {
    fetchDepartments(siteId).then(setDepartments);
    fetchLeaveRequestApprovers(siteId).then(setApprovers);
  }

  useEffect(load, [siteId]);

  async function handleSetApprover(departmentId, employee) {
    try {
      await setLeaveRequestApprover(departmentId, employee.id);
      load();
    } catch (err) {
      onError(err.response?.data?.detail || "تعیین تأییدکننده با خطا مواجه شد.");
    }
  }

  async function handleRemoveApprover(departmentId) {
    try {
      await removeLeaveRequestApprover(departmentId);
      load();
    } catch (err) {
      onError(err.response?.data?.detail || "حذف تأییدکننده با خطا مواجه شد.");
    }
  }

  if (departments === null || approvers === null) return null;

  return (
    <Stack spacing={1.5}>
      {departments.map((department) => {
        const current = approvers.find((a) => a.department_id === department.id);
        return (
          <Box key={department.id} sx={{ p: 1.5, border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
            <Typography fontWeight={700} sx={{ mb: 1 }}>
              {department.name}
            </Typography>
            {current ? (
              <Chip
                label={`${current.approver_employee.first_name} ${current.approver_employee.last_name}`}
                onDelete={() => handleRemoveApprover(department.id)}
                sx={{ mb: 1 }}
              />
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                هنوز تأییدکننده‌ای تعیین نشده.
              </Typography>
            )}
            <EmployeePicker
              siteId={siteId}
              label="تعیین/تغییر تأییدکننده"
              onSelect={(employee) => handleSetApprover(department.id, employee)}
            />
          </Box>
        );
      })}
    </Stack>
  );
}

export default function LeaveRequestStructurePage() {
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetchSites().then((data) => {
      setSites(data);
      if (data.length > 0) setSiteId(data[0].id);
    });
  }, []);

  return (
    <Box>
      <BackLink to="/access" label="بازگشت" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 1 }}>
        تنظیمات درخواست مرخصی/ماموریت
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        نگاشت ستون‌های جدول خام، نوع‌های قابل‌انتخاب پرسنل، و تأییدکننده هر واحد سازمانی.
      </Typography>

      <TextField
        select
        label="سایت"
        value={siteId}
        onChange={(e) => setSiteId(e.target.value)}
        sx={{ minWidth: 240, mb: 3 }}
      >
        {sites.map((site) => (
          <MenuItem key={site.id} value={site.id}>
            {site.name}
          </MenuItem>
        ))}
      </TextField>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {siteId && (
        <Stack spacing={2}>
          <Accordion variant="outlined">
            <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
              <Typography fontWeight={700}>نگاشت ستون‌های جدول خام</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <MappingSection siteId={siteId} onError={setError} />
            </AccordionDetails>
          </Accordion>

          <Accordion variant="outlined">
            <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
              <Typography fontWeight={700}>نوع‌های درخواست</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <TypesSection siteId={siteId} onError={setError} />
            </AccordionDetails>
          </Accordion>

          <Accordion variant="outlined">
            <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
              <Typography fontWeight={700}>تأییدکننده هر واحد سازمانی</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <ApproversSection siteId={siteId} onError={setError} />
            </AccordionDetails>
          </Accordion>
        </Stack>
      )}
    </Box>
  );
}
