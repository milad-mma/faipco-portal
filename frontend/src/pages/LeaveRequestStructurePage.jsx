import { useEffect, useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Autocomplete,
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
  fetchActionLookup,
  fetchOperationLookup,
  fetchCardLookup,
  fetchLeaveRequestApprovers,
  fetchLeaveRequestTypes,
  removeLeaveRequestApprover,
  setLeaveRequestApprover,
  updateLeaveRequestType,
} from "../api/leaveRequestsAdmin";

function TypesSection({ siteId, onError }) {
  const [types, setTypes] = useState(null);
  const [title, setTitle] = useState("");
  const [isMission, setIsMission] = useState(false);
  const [isHourly, setIsHourly] = useState(false);
  const [actionId, setActionId] = useState("1");
  const [actionIdTouched, setActionIdTouched] = useState(false);
  const [actionLookup, setActionLookup] = useState([]);
  const [operationId, setOperationId] = useState("");
  const [operationLookup, setOperationLookup] = useState([]);
  const [cardNo, setCardNo] = useState("");
  const [cardLookup, setCardLookup] = useState([]);

  useEffect(() => {
    fetchActionLookup(siteId)
      .then(setActionLookup)
      .catch(() => setActionLookup([]));
    fetchOperationLookup(siteId)
      .then(setOperationLookup)
      .catch(() => setOperationLookup([]));
    fetchCardLookup(siteId)
      .then(setCardLookup)
      .catch(() => setCardLookup([]));
  }, [siteId]);

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
        operation_id: operationId === "" ? null : Number(operationId),
        card_no: cardNo === "" ? null : Number(cardNo),
      });
      setTitle("");
      setIsMission(false);
      setIsHourly(false);
      setActionId("1");
      setActionIdTouched(false);
      setOperationId("");
      setCardNo("");
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
              <TableCell>OperationId</TableCell>
              <TableCell>Card_No</TableCell>
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
                <TableCell>{t.operation_id ?? "—"}</TableCell>
                <TableCell>{t.card_no ?? "—"}</TableCell>
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

      {actionLookup.length > 0 && (
        <Box sx={{ mb: 1.5 }}>
          <Autocomplete
            options={actionLookup}
            getOptionLabel={(item) => `${item.title} (ActionId=${item.action_id})`}
            onChange={(_, item) => {
              if (item) {
                setTitle(item.title);
                setActionId(String(item.action_id));
                setActionIdTouched(true);
              }
            }}
            renderInput={(params) => (
              <TextField {...params} size="small" label="انتخاب از فهرست رسمی WF_Action (اختیاری)" />
            )}
            sx={{ maxWidth: 400 }}
          />
          <Typography variant="caption" color="text.secondary">
            با انتخاب از این فهرست، عنوان و ActionId خودکار پر می‌شود - سوئیچ‌های ماموریت/ساعتی را هم
            دستی تنظیم کنید.
          </Typography>
        </Box>
      )}

      {operationLookup.length > 0 && (
        <Box sx={{ mb: 1.5 }}>
          <Autocomplete
            options={operationLookup}
            getOptionLabel={(item) => `${item.title} (OperationId=${item.operation_id})`}
            onChange={(_, item) => {
              if (item) setOperationId(String(item.operation_id));
            }}
            renderInput={(params) => (
              <TextField {...params} size="small" label="انتخاب از فهرست رسمی WF_OperationTypes (اختیاری)" />
            )}
            sx={{ maxWidth: 400 }}
          />
        </Box>
      )}

      {cardLookup.length > 0 && (
        <Box sx={{ mb: 1.5 }}>
          <Autocomplete
            options={cardLookup}
            getOptionLabel={(item) => `${item.title} (Card_No=${item.card_no})`}
            onChange={(_, item) => {
              if (item) {
                setCardNo(String(item.card_no));
                // ⚠️ کشف حیاتی (تأییدشده با بررسی مستقیم دیتابیس): ActionId
                // همیشه از همین کارت مشتق می‌شود، نه مستقل - با انتخاب
                // کارت، خودکار هم‌زمان پر می‌شود.
                if (item.action_id != null) {
                  setActionId(String(item.action_id));
                  setActionIdTouched(true);
                }
              }
            }}
            renderInput={(params) => (
              <TextField {...params} size="small" label="انتخاب کارت از فهرست رسمی Cards (الزامی)" />
            )}
            sx={{ maxWidth: 400 }}
          />
          <Typography variant="caption" color="text.secondary">
            بدون انتخاب کارت، ثبت درخواست از این نوع با خطا مواجه می‌شود (Card_No در WF_Requests به
            جدول Cards وصل است) - با انتخاب کارت، ActionId هم خودکار درست پر می‌شود.
          </Typography>
        </Box>
      )}

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
        <TextField
          size="small"
          type="number"
          label="OperationId (اختیاری)"
          value={operationId}
          onChange={(e) => setOperationId(e.target.value)}
          sx={{ width: 180 }}
        />
        <TextField
          size="small"
          type="number"
          label="Card_No (اختیاری)"
          value={cardNo}
          onChange={(e) => setCardNo(e.target.value)}
          sx={{ width: 160 }}
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
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        نوع‌های قابل‌انتخاب پرسنل و تأییدکننده هر واحد سازمانی.
      </Typography>
      <Alert severity="info" sx={{ mb: 2 }}>
        نگاشت ستون‌های جدول خام WF_Requests به «تنظیمات سایت» منتقل شد - از صفحه سایت موردنظر، تب
        «نگاشت مرخصی/ماموریت» را باز کنید.
      </Alert>

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
