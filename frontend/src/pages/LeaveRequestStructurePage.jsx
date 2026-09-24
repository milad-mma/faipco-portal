import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
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
  fetchLeaveRequestHrOfficer,
  fetchLeaveRequestModuleStatus,
  fetchLeaveRequestTypes,
  removeLeaveRequestApprover,
  removeLeaveRequestHrOfficer,
  setLeaveRequestApprover,
  setLeaveRequestHrOfficer,
  setLeaveRequestModuleDisabled,
  updateLeaveRequestType,
} from "../api/leaveRequestsAdmin";

/**
 * بخش مدیریت نوع‌های درخواست یک سایت.
 * ورودی: siteId و onError برای نمایش خطا در والد.
 * جدول نوع‌های موجود (با سوئیچ فعال/غیرفعال و حذف) و فرم افزودن نوع جدید با کدهای ActionId/OperationId/Card_No کاراوب.
 */
function TypesSection({ siteId, onError }) {
  const [types, setTypes] = useState(null); // نوع‌های تعریف‌شده‌ی سایت؛ null = هنوز بارگذاری نشده
  const [title, setTitle] = useState(""); // عنوان نوع جدید
  const [isMission, setIsMission] = useState(false); // ماموریت (خاموش = مرخصی)
  const [isHourly, setIsHourly] = useState(false); // ساعتی (خاموش = روزانه)
  const [isForgottenPunch, setIsForgottenPunch] = useState(false); // نوع «تردد فراموش‌شده»
  const [actionId, setActionId] = useState("1"); // ActionId کاراوب (رشته‌ای؛ خالی = null)
  const [actionIdTouched, setActionIdTouched] = useState(false); // کاربر ActionId را دستی/از فهرست تعیین کرده؛ پیشنهاد خودکار متوقف می‌شود
  const [actionLookup, setActionLookup] = useState([]); // فهرست رسمی WF_Action سایت
  const [operationId, setOperationId] = useState(""); // OperationId کاراوب
  const [operationLookup, setOperationLookup] = useState([]); // فهرست رسمی WF_OperationTypes سایت
  const [cardNo, setCardNo] = useState(""); // Card_No کاراوب
  const [cardLookup, setCardLookup] = useState([]); // فهرست رسمی Cards سایت

  // بارگذاری سه فهرست مرجع کاراوب؛ در خطا فهرست خالی (Autocomplete مربوطه نمایش داده نمی‌شود)
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

  // پیشنهاد خودکار ActionId از ترکیب ماموریت/ساعتی: مرخصی روزانه=1، ماموریت روزانه=2، مرخصی ساعتی=3، ماموریت ساعتی=9
  function suggestActionId(mission, hourly) {
    if (!mission && !hourly) return "1";
    if (mission && !hourly) return "2";
    if (!mission && hourly) return "3";
    return "9";
  }

  // تغییر سوئیچ ماموریت؛ تا وقتی کاربر ActionId را دستی عوض نکرده، پیشنهاد خودکار به‌روز می‌شود
  function handleMissionChange(value) {
    setIsMission(value);
    if (!actionIdTouched) setActionId(suggestActionId(value, isHourly));
  }

  // تغییر سوئیچ ساعتی؛ مانند handleMissionChange
  function handleHourlyChange(value) {
    setIsHourly(value);
    if (!actionIdTouched) setActionId(suggestActionId(isMission, value));
  }

  // بارگذاری نوع‌های سایت
  function load() {
    fetchLeaveRequestTypes(siteId).then(setTypes);
  }

  useEffect(load, [siteId]);

  // افزودن نوع جدید با مقادیر فرم، سپس بازنشانی فرم و بارگذاری مجدد لیست
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
        is_forgotten_punch: isForgottenPunch,
      });
      setTitle("");
      setIsForgottenPunch(false);
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

  // فعال/غیرفعال کردن یک نوع
  async function handleToggleActive(type) {
    try {
      await updateLeaveRequestType(type.id, { is_active: !type.is_active });
      load();
    } catch (err) {
      onError(err.response?.data?.detail || "ویرایش نوع درخواست با خطا مواجه شد.");
    }
  }

  // حذف یک نوع
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
      {/* جدول نوع‌های موجود */}
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
                <TableCell>{t.is_forgotten_punch ? "تردد فراموش‌شده" : t.is_mission ? "ماموریت" : "مرخصی"}</TableCell>
                <TableCell>{t.is_forgotten_punch ? "—" : t.is_hourly ? "ساعتی" : "روزانه"}</TableCell>
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

      {/* انتخاب از فهرست WF_Action: عنوان و ActionId را پر می‌کند */}
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

      {/* انتخاب از فهرست WF_OperationTypes: OperationId را پر می‌کند */}
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

      {/* انتخاب کارت از فهرست Cards: Card_No و ActionId مشتق از کارت را پر می‌کند */}
      {cardLookup.length > 0 && (
        <Box sx={{ mb: 1.5 }}>
          <Autocomplete
            options={cardLookup}
            getOptionLabel={(item) => `${item.title} (Card_No=${item.card_no})`}
            onChange={(_, item) => {
              if (item) {
                setCardNo(String(item.card_no));
                // ActionId در کاراوب از کارت مشتق می‌شود؛ با انتخاب کارت خودکار پر می‌شود
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

      {/* فرم افزودن نوع جدید: عنوان، سوئیچ‌ها (تردد فراموش‌شده، ماموریت و ساعتی را قفل می‌کند)، کدهای کاراوب و دکمه‌ی افزودن */}
      <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
        <TextField size="small" label="عنوان نوع جدید" value={title} onChange={(e) => setTitle(e.target.value)} />
        <FormControlLabel
          control={
            <Switch
              checked={isForgottenPunch}
              onChange={(e) => {
                setIsForgottenPunch(e.target.checked);
                if (e.target.checked) {
                  setIsMission(false);
                  setIsHourly(true);
                }
              }}
            />
          }
          label="تردد فراموش‌شده"
        />
        {!isForgottenPunch && (
          <>
            <FormControlLabel
              control={<Switch checked={isMission} onChange={(e) => handleMissionChange(e.target.checked)} />}
              label="ماموریت (خاموش=مرخصی)"
            />
            <FormControlLabel
              control={<Switch checked={isHourly} onChange={(e) => handleHourlyChange(e.target.checked)} />}
              label="ساعتی (خاموش=روزانه)"
            />
          </>
        )}
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

/**
 * بخش تعیین تأییدکننده‌ی هر واحد سازمانی سایت.
 * ورودی: siteId و onError. برای هر واحد، تأییدکننده‌ی فعلی (قابل حذف) و انتخاب‌گر پرسنل نمایش داده می‌شود.
 */
function ApproversSection({ siteId, onError }) {
  const [departments, setDepartments] = useState(null); // واحدهای سازمانی سایت
  const [approvers, setApprovers] = useState(null); // تأییدکننده‌های تعیین‌شده به ازای واحد

  // بارگذاری واحدها و تأییدکننده‌ها
  function load() {
    fetchDepartments(siteId).then(setDepartments);
    fetchLeaveRequestApprovers(siteId).then(setApprovers);
  }

  useEffect(load, [siteId]);

  // تعیین/تغییر تأییدکننده‌ی یک واحد
  async function handleSetApprover(departmentId, employee) {
    try {
      await setLeaveRequestApprover(departmentId, employee.id);
      load();
    } catch (err) {
      onError(err.response?.data?.detail || "تعیین تأییدکننده با خطا مواجه شد.");
    }
  }

  // حذف تأییدکننده‌ی یک واحد
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
      {/* یک کارت به ازای هر واحد سازمانی */}
      {departments.map((department) => {
        const current = approvers.find((a) => a.department_id === department.id); // تأییدکننده‌ی فعلی این واحد
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

/**
 * بخش تعیین مسئول نیروی انسانی سایت.
 * ورودی: siteId و onError. «تردد فراموش‌شده» بعد از تأیید سرپرست، توسط این فرد تأیید نهایی می‌شود.
 */
function HrOfficerSection({ siteId, onError }) {
  const [officer, setOfficer] = useState(undefined); // undefined = هنوز بارگذاری نشده، null = تعیین نشده

  // بارگذاری مسئول فعلی
  function load() {
    fetchLeaveRequestHrOfficer(siteId)
      .then(setOfficer)
      .catch(() => setOfficer(null));
  }

  useEffect(load, [siteId]);

  // تعیین/تغییر مسئول نیروی انسانی
  async function handleSet(employee) {
    try {
      await setLeaveRequestHrOfficer(siteId, employee.id);
      load();
    } catch (err) {
      onError(err.response?.data?.detail || "تعیین مسئول نیروی انسانی با خطا مواجه شد.");
    }
  }

  // حذف مسئول نیروی انسانی
  async function handleRemove() {
    try {
      await removeLeaveRequestHrOfficer(siteId);
      load();
    } catch (err) {
      onError(err.response?.data?.detail || "حذف مسئول نیروی انسانی با خطا مواجه شد.");
    }
  }

  if (officer === undefined) return null;

  return (
    <Stack spacing={1.5}>
      <Typography variant="body2" color="text.secondary">
        درخواست «تردد فراموش‌شده» اول توسط سرپرست پرسنل تأیید می‌شود و بعد برای این فرد ارجاع می‌شود؛ تردد فقط
        پس از تأیید او در کاراوب ثبت می‌شود.
      </Typography>
      {officer ? (
        <Box>
          <Chip
            label={`${officer.employee.first_name} ${officer.employee.last_name} (${officer.employee.personnel_code})`}
            onDelete={handleRemove}
          />
        </Box>
      ) : (
        <Alert severity="warning">هنوز مسئول نیروی انسانی تعیین نشده - ثبت تردد فراموش‌شده ممکن نیست.</Alert>
      )}
      <EmployeePicker siteId={siteId} label="تعیین/تغییر مسئول نیروی انسانی" onSelect={handleSet} />
    </Stack>
  );
}

/**
 * بخش فعال/غیرفعال کردن کل ماژول درخواست مرخصی برای یک سایت.
 * ورودی: siteId و onError. وقتی غیرفعال است صفحه‌ی درخواست پرسنل بسته و کارت داشبورد «غیرفعال» است؛
 * نگاشت و تنظیمات دست‌نخورده می‌مانند. اگر سایت نگاشت نداشته باشد فقط هشدار نشان می‌دهد.
 */
function ModuleStatusSection({ siteId, onError }) {
  const [moduleStatus, setModuleStatus] = useState(null); // { has_mapping, is_disabled }؛ null = هنوز بارگذاری نشده
  const [saving, setSaving] = useState(false); // در حال ذخیره‌ی تغییر سوئیچ

  // بارگذاری وضعیت ماژول با هر تغییر سایت
  useEffect(() => {
    setModuleStatus(null);
    fetchLeaveRequestModuleStatus(siteId)
      .then(setModuleStatus)
      .catch(() => setModuleStatus(null));
  }, [siteId]);

  // تغییر سوئیچ: سوئیچ روشن = فعال، پس مقدار disabled معکوس آن ارسال می‌شود
  async function handleToggle(event) {
    setSaving(true);
    try {
      setModuleStatus(await setLeaveRequestModuleDisabled(siteId, !event.target.checked));
    } catch (err) {
      onError(err.response?.data?.detail || "تغییر وضعیت ماژول با خطا مواجه شد.");
    } finally {
      setSaving(false);
    }
  }

  if (moduleStatus === null) return null;

  // بدون نگاشت کاراوب، ماژول اصلاً در دسترس نیست
  if (!moduleStatus.has_mapping) {
    return (
      <Alert severity="warning" sx={{ mb: 2 }}>
        برای این سایت هنوز نگاشت مرخصی/ماموریت تنظیم نشده است؛ تا تنظیم نشود، درخواست مرخصی/ماموریت در دسترس پرسنل
        نیست.
      </Alert>
    );
  }

  const enabled = !moduleStatus.is_disabled;
  return (
    <Box
      sx={{
        mb: 2,
        p: 2,
        border: "1px solid",
        borderColor: enabled ? "divider" : "warning.main",
        borderRadius: 2,
        bgcolor: enabled ? "background.paper" : "rgba(237, 108, 2, 0.06)",
      }}
    >
      <FormControlLabel
        control={<Switch checked={enabled} onChange={handleToggle} disabled={saving} />}
        label={
          <Typography fontWeight={700}>
            درخواست مرخصی/ماموریت برای این سایت {enabled ? "فعال است" : "غیرفعال است"}
          </Typography>
        }
      />
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
        {enabled
          ? "با غیرفعال‌کردن، صفحه درخواست برای پرسنل این سایت بسته می‌شود و کارت داشبورد «غیرفعال» نشان می‌دهد. تنظیمات حفظ می‌شوند."
          : "پرسنل این سایت نمی‌توانند درخواست ثبت کنند و سرپرستان هم از پرتال نمی‌توانند درخواست‌ها را تأیید/رد کنند. مشاهده و ویرایش مدیریتی همچنان در دسترس است."}
      </Typography>
    </Box>
  );
}

/**
 * صفحه‌ی تنظیمات درخواست مرخصی/ماموریت (مدیریتی).
 * سایت انتخاب می‌شود (پیش‌فرض از query string یا اولین سایت) و سپس چهار بخش نمایش داده می‌شود:
 * وضعیت ماژول، نوع‌های درخواست، تأییدکننده‌ی هر واحد و مسئول نیروی انسانی.
 */
export default function LeaveRequestStructurePage() {
  const [searchParams] = useSearchParams();
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState(""); // سایت انتخابی
  const [error, setError] = useState(""); // خطای مشترک همه‌ی بخش‌ها

  // بارگذاری سایت‌ها و انتخاب سایت اولیه
  useEffect(() => {
    fetchSites().then((data) => {
      setSites(data);
      // اگر از تب «نگاشت مرخصی/ماموریت» تنظیمات سایت آمده باشیم، همان سایت انتخاب می‌شود
      const requested = Number(searchParams.get("site"));
      const match = data.find((site) => site.id === requested);
      if (match) setSiteId(match.id);
      else if (data.length > 0) setSiteId(data[0].id);
    });
  }, []);

  return (
    <Box>
      <BackLink to="/sites" label="بازگشت" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 1 }}>
        تنظیمات درخواست مرخصی/ماموریت
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        نوع‌های قابل‌انتخاب پرسنل، تأییدکننده هر واحد سازمانی و مسئول نیروی انسانی سایت.
      </Typography>
      <Alert severity="info" sx={{ mb: 2 }}>
        نگاشت ستون‌های جدول‌های کاراوب در «تنظیمات سایت» است - از صفحه سایت موردنظر، تب «نگاشت مرخصی/ماموریت» را
        باز کنید.
      </Alert>

      {/* انتخاب سایت */}
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

      {/* وضعیت ماژول برای سایت انتخابی */}
      {siteId && <ModuleStatusSection siteId={siteId} onError={setError} />}

      {/* سه بخش تنظیمات در آکاردئون */}
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

          <Accordion variant="outlined">
            <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
              <Typography fontWeight={700}>مسئول نیروی انسانی (تأیید نهایی تردد فراموش‌شده)</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <HrOfficerSection siteId={siteId} onError={setError} />
            </AccordionDetails>
          </Accordion>
        </Stack>
      )}
    </Box>
  );
}
