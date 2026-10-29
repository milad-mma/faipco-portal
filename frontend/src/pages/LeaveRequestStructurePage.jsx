import { useCallback, useEffect, useState } from "react";
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
  Grid,
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
import NotificationTemplatesEditor from "../components/NotificationTemplatesEditor";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import {
  fetchLeaveNotificationTemplates,
  saveLeaveNotificationTemplates,
  addLeaveRequestType,
  deleteLeaveRequestType,
  fetchActionLookup,
  fetchOperationLookup,
  fetchCardLookup,
  fetchLeaveRequestApprovers,
  fetchLeaveRequestHrOfficer,
  fetchLeaveStuckRequests,
  reassignLeaveApprovers,
  fetchLeaveRequestModuleStatus,
  setLeavePunchTolerance,
  fetchLeaveRequestTypes,
  removeLeaveRequestApprover,
  removeLeaveRequestHrOfficer,
  setLeaveRequestApprover,
  setLeaveRequestHrOfficer,
  setLeaveRequestModuleDisabled,
  updateLeaveRequestType,
} from "../api/leaveRequestsAdmin";
import { searchFilterOptions } from "../utils/searchText";

/**
 * بخش مدیریت نوع‌های درخواست یک سایت.
 * ورودی: siteId و onError برای نمایش خطا در والد.
 * جدول نوع‌های موجود (با سوئیچ فعال/غیرفعال و حذف) و فرم افزودن نوع جدید با کدهای ActionId/OperationId/Card_No کاراوب.
 */
// مقدار فیلد مهلت → عدد یا null (خالی = بدون محدودیت)
function dayLimit(value) {
  const text = String(value ?? "").replace(/[۰-۹]/g, (d) => "۰۱۲۳۴۵۶۷۸۹".indexOf(d)).trim();
  return text === "" ? null : Math.max(0, Math.min(365, Number(text) || 0));
}

/**
 * مهلت ثبت یک نوع (Migration 126): «گذشته» = تا چند روز بعد از تاریخ درخواست، «آینده» = تا چند روز جلوتر.
 * خالی = بدون محدودیت، ۰ = ممنوع. با خروج از فیلد ذخیره می‌شود.
 */
function SubmitWindowCell({ type, onSave }) {
  const [past, setPast] = useState(type.max_past_days ?? "");
  const [future, setFuture] = useState(type.max_future_days ?? "");
  useEffect(() => {
    setPast(type.max_past_days ?? "");
    setFuture(type.max_future_days ?? "");
  }, [type.max_past_days, type.max_future_days]);
  function save(key, value) {
    const next = dayLimit(value);
    if (next !== (type[key] ?? null)) onSave(type, { [key]: next });
  }
  const field = (label, value, setValue, key, hidden) =>
    hidden ? null : (
      <TextField
        size="small"
        label={label}
        value={value}
        placeholder="آزاد"
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => save(key, value)}
        inputProps={{ inputMode: "numeric", dir: "ltr" }}
        sx={{ width: 96 }}
      />
    );
  return (
    <Stack direction="row" spacing={1}>
      {field("گذشته (روز)", past, setPast, "max_past_days", false)}
      {field("آینده (روز)", future, setFuture, "max_future_days", type.is_forgotten_punch)}
    </Stack>
  );
}

function TypesSection({ siteId, onError }) {
  const [types, setTypes] = useState(null); // نوع‌های تعریف‌شده‌ی سایت؛ null = هنوز بارگذاری نشده
  const [title, setTitle] = useState(""); // عنوان نوع جدید
  const [isMission, setIsMission] = useState(false); // ماموریت (خاموش = مرخصی)
  const [isHourly, setIsHourly] = useState(false); // ساعتی (خاموش = روزانه)
  const [isForgottenPunch, setIsForgottenPunch] = useState(false); // نوع «تردد فراموش‌شده»
  const [isExitPermit, setIsExitPermit] = useState(false); // نوع «مجوز خروج» (فقط ساعت خروج بعد از پایان شیفت)
  const [actionId, setActionId] = useState("1"); // ActionId کاراوب (رشته‌ای؛ خالی = null)
  const [actionIdTouched, setActionIdTouched] = useState(false); // کاربر ActionId را دستی/از فهرست تعیین کرده؛ پیشنهاد خودکار متوقف می‌شود
  const [actionLookup, setActionLookup] = useState([]); // فهرست رسمی WF_Action سایت
  const [operationId, setOperationId] = useState(""); // OperationId کاراوب
  const [operationLookup, setOperationLookup] = useState([]); // فهرست رسمی WF_OperationTypes سایت
  const [cardNo, setCardNo] = useState(""); // Card_No کاراوب
  const [cardLookup, setCardLookup] = useState([]); // فهرست رسمی Cards سایت
  const [maxPast, setMaxPast] = useState(""); // مهلت ثبت گذشته (روز؛ خالی = آزاد)
  const [maxFuture, setMaxFuture] = useState(""); // مهلت ثبت آینده (روز؛ خالی = آزاد)

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
        is_exit_permit: isExitPermit,
        max_past_days: dayLimit(maxPast),
        max_future_days: isForgottenPunch ? null : dayLimit(maxFuture),
      });
      setTitle("");
      setMaxPast("");
      setMaxFuture("");
      setIsForgottenPunch(false);
      setIsExitPermit(false);
      setIsMission(false);
      setIsHourly(false);
      setActionId("1");
      setActionIdTouched(false);
      setOperationId("");
      setCardNo("");
      load();
    } catch (err) {
      onError(
        err.response?.data?.detail || "افزودن نوع درخواست با خطا مواجه شد.",
      );
    }
  }

  // فعال/غیرفعال کردن یک نوع
  async function handleToggleActive(type) {
    try {
      await updateLeaveRequestType(type.id, { is_active: !type.is_active });
      load();
    } catch (err) {
      onError(
        err.response?.data?.detail || "ویرایش نوع درخواست با خطا مواجه شد.",
      );
    }
  }

  // ذخیره‌ی مهلت ثبت یک نوع
  async function handleSaveWindow(type, data) {
    try {
      await updateLeaveRequestType(type.id, data);
      load();
    } catch (err) {
      onError(err.response?.data?.detail || "ذخیره‌ی مهلت ثبت با خطا مواجه شد.");
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
              <TableCell>مهلت ثبت</TableCell>
              <TableCell>فعال</TableCell>
              <TableCell>حذف</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {types.map((t) => (
              <TableRow key={t.id}>
                <TableCell>{t.title}</TableCell>
                <TableCell>
                  {t.is_forgotten_punch
                    ? "تردد فراموش‌شده"
                    : t.is_exit_permit
                      ? "مجوز خروج"
                      : t.is_mission
                      ? "ماموریت"
                      : "مرخصی"}
                </TableCell>
                <TableCell>
                  {t.is_forgotten_punch || t.is_exit_permit
                    ? "—"
                    : t.is_hourly
                      ? "ساعتی"
                      : "روزانه"}
                </TableCell>
                <TableCell>{t.action_id ?? "—"}</TableCell>
                <TableCell>{t.operation_id ?? "—"}</TableCell>
                <TableCell>{t.card_no ?? "—"}</TableCell>
                <TableCell>
                  <SubmitWindowCell type={t} onSave={handleSaveWindow} />
                </TableCell>
                <TableCell>
                  <Switch
                    checked={t.is_active}
                    onChange={() => handleToggleActive(t)}
                    size="small"
                  />
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
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
        مهلت ثبت (روز تقویمی نسبت به امروز): «گذشته» = تا چند روز بعد از تاریخ مرخصی/ماموریت/تردد می‌شود ثبت کرد،
        «آینده» = تا چند روز جلوتر. خالی = بدون محدودیت، ۰ = ممنوع (مثلاً گذشته ۰ یعنی فقط امروز و آینده). تردد
        فراموش‌شده همیشه فقط گذشته است و اگر خالی بماند ۳۱ روز. با خروج از فیلد ذخیره می‌شود.
      </Typography>

      {/* فرم افزودن نوع جدید: سه فهرست مرجع کاراوب در یک ردیف، فیلدهای کد در ردیف دوم، سوئیچ‌ها و دکمه در ردیف سوم */}
      <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 2.5, mb: 1 }}>
        افزودن نوع جدید
      </Typography>
      {(actionLookup.length > 0 ||
        operationLookup.length > 0 ||
        cardLookup.length > 0) && (
        <Grid container spacing={1.5} sx={{ mb: 1.5 }}>
          {cardLookup.length > 0 && (
            <Grid item xs={12} md={4}>
              {/* انتخاب کارت: Card_No و ActionId مشتق از کارت را پر می‌کند */}
              <Autocomplete
                filterOptions={searchFilterOptions}
                options={cardLookup}
                getOptionLabel={(item) =>
                  `${item.title} (Card_No=${item.card_no})`
                }
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
                  <TextField
                    {...params}
                    size="small"
                    label="کارت (Cards)"
                    helperText="بدون کارت، ثبت درخواست این نوع خطا می‌دهد."
                  />
                )}
              />
            </Grid>
          )}
          {actionLookup.length > 0 && (
            <Grid item xs={12} md={4}>
              {/* انتخاب از WF_Action: عنوان و ActionId را پر می‌کند */}
              <Autocomplete
                filterOptions={searchFilterOptions}
                options={actionLookup}
                getOptionLabel={(item) =>
                  `${item.title} (ActionId=${item.action_id})`
                }
                onChange={(_, item) => {
                  if (item) {
                    setTitle(item.title);
                    setActionId(String(item.action_id));
                    setActionIdTouched(true);
                  }
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    size="small"
                    label="عملیات (WF_Action)"
                    helperText="عنوان و ActionId را پر می‌کند."
                  />
                )}
              />
            </Grid>
          )}
          {operationLookup.length > 0 && (
            <Grid item xs={12} md={4}>
              {/* انتخاب از WF_OperationTypes: OperationId را پر می‌کند */}
              <Autocomplete
                filterOptions={searchFilterOptions}
                options={operationLookup}
                getOptionLabel={(item) =>
                  `${item.title} (OperationId=${item.operation_id})`
                }
                onChange={(_, item) => {
                  if (item) setOperationId(String(item.operation_id));
                }}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    size="small"
                    label="نوع عملیات (WF_OperationTypes)"
                    helperText="OperationId را پر می‌کند."
                  />
                )}
              />
            </Grid>
          )}
        </Grid>
      )}
      <Grid container spacing={1.5} sx={{ mb: 1 }}>
        <Grid item xs={12} md={4}>
          <TextField
            size="small"
            fullWidth
            label="عنوان نوع جدید"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </Grid>
        <Grid item xs={4} md={2.66}>
          <TextField
            size="small"
            fullWidth
            type="number"
            label="ActionId"
            value={actionId}
            onChange={(e) => {
              setActionId(e.target.value);
              setActionIdTouched(true);
            }}
          />
        </Grid>
        <Grid item xs={4} md={2.66}>
          <TextField
            size="small"
            fullWidth
            type="number"
            label="OperationId"
            value={operationId}
            onChange={(e) => setOperationId(e.target.value)}
          />
        </Grid>
        <Grid item xs={4} md={2.66}>
          <TextField
            size="small"
            fullWidth
            type="number"
            label="Card_No"
            value={cardNo}
            onChange={(e) => setCardNo(e.target.value)}
          />
        </Grid>
        <Grid item xs={6} md={2}>
          <TextField
            size="small"
            fullWidth
            label="مهلت گذشته (روز)"
            placeholder="آزاد"
            value={maxPast}
            onChange={(e) => setMaxPast(e.target.value)}
            inputProps={{ inputMode: "numeric", dir: "ltr" }}
          />
        </Grid>
        {!isForgottenPunch && (
          <Grid item xs={6} md={2}>
            <TextField
              size="small"
              fullWidth
              label="مهلت آینده (روز)"
              placeholder="آزاد"
              value={maxFuture}
              onChange={(e) => setMaxFuture(e.target.value)}
              inputProps={{ inputMode: "numeric", dir: "ltr" }}
            />
          </Grid>
        )}
      </Grid>
      {/* سوئیچ‌ها (تردد فراموش‌شده، ماموریت و ساعتی را قفل می‌کند) و دکمه‌ی افزودن در یک ردیف هم‌تراز */}
      <Stack
        direction="row"
        spacing={1.5}
        alignItems="center"
        flexWrap="wrap"
        useFlexGap
      >
        <FormControlLabel
          control={
            <Switch
              checked={isForgottenPunch}
              onChange={(e) => {
                setIsForgottenPunch(e.target.checked);
                if (e.target.checked) {
                  setIsExitPermit(false);
                  setIsMission(false);
                  setIsHourly(true);
                }
              }}
            />
          }
          label="تردد فراموش‌شده"
        />
        <FormControlLabel
          control={
            <Switch
              checked={isExitPermit}
              onChange={(e) => {
                setIsExitPermit(e.target.checked);
                if (e.target.checked) {
                  setIsForgottenPunch(false);
                  setIsMission(false);
                  setIsHourly(true);
                }
              }}
            />
          }
          label="مجوز خروج (فقط ساعت خروج)"
        />
        {!isForgottenPunch && !isExitPermit && (
          <>
            <FormControlLabel
              control={
                <Switch
                  checked={isMission}
                  onChange={(e) => handleMissionChange(e.target.checked)}
                />
              }
              label="ماموریت (خاموش=مرخصی)"
            />
            <FormControlLabel
              control={
                <Switch
                  checked={isHourly}
                  onChange={(e) => handleHourlyChange(e.target.checked)}
                />
              }
              label="ساعتی (خاموش=روزانه)"
            />
          </>
        )}
        <Box sx={{ flex: 1 }} />
        <Button
          variant="contained"
          startIcon={<AddOutlinedIcon />}
          onClick={handleAdd}
          disabled={!title.trim()}
        >
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
// پیام نتیجه‌ی انتقال درخواست‌ها بعد از تغییر تأییدکننده (پاسخ ذخیره: reassigned / unresolved_count)
function reassignNotice(res) {
  if (!res?.reassigned && !res?.unresolved_count) return "";
  let text = res.reassigned ? `${res.reassigned} درخواست بدون تصمیم به تأییدکننده‌ی جدید منتقل شد.` : "";
  if (res.unresolved_count) text += ` برای ${res.unresolved_count} درخواست تأییدکننده‌ی جایگزین پیدا نشد.`;
  return text.trim();
}

/**
 * هشدار درخواست‌های مانده پیش تأییدکننده‌ی ترک‌کار + دکمه‌ی «انتقال به تأییدکننده‌های فعلی» (مثل وام و مساعده).
 * Sync هنگام ترک کار خودکار منتقل می‌کند؛ این بخش برای مواردی است که جایگزین پیدا نشده یا قبلاً مانده‌اند.
 */
function StuckRequestsSection({ siteId, refreshKey, onError, onNotice }) {
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    fetchLeaveStuckRequests(siteId)
      .then(setItems)
      .catch(() => setItems([]));
  }, [siteId]);

  useEffect(load, [load, refreshKey]);

  async function handleReassign() {
    setBusy(true);
    try {
      const res = await reassignLeaveApprovers(siteId);
      onNotice(
        reassignNotice({ reassigned: res.reassigned, unresolved_count: res.unresolved }) ||
          "درخواستی برای انتقال پیدا نشد.",
      );
      load();
    } catch (err) {
      onError(err.response?.data?.detail || "انتقال درخواست‌ها با خطا مواجه شد.");
    } finally {
      setBusy(false);
    }
  }

  if (!items || items.length === 0) return null;

  return (
    <Alert
      severity="warning"
      sx={{ mb: 2 }}
      action={
        <Button color="inherit" size="small" disabled={busy} onClick={handleReassign} sx={{ whiteSpace: "nowrap" }}>
          انتقال به تأییدکننده‌های فعلی
        </Button>
      }
    >
      <Typography variant="body2" fontWeight={700}>
        {items.length} درخواست بدون تصمیم پیش تأییدکننده‌ی ترک‌کار مانده است.
      </Typography>
      <Typography variant="caption" display="block" sx={{ mb: 0.5 }}>
        انتقال: سرپرست امروز (زنجیره‌ی سازمانی کاراوب، بعد تأییدکننده‌ی دستی واحد) یا مسئول نیروی انسانی فعلی. اگر
        جایگزینی پیدا نشود، تأییدکننده‌ی دستی واحد یا مسئول نیروی انسانی را تعیین کنید.
      </Typography>
      {items.slice(0, 10).map((item) => (
        <Typography key={item.request_id} variant="caption" display="block">
          • {item.requester_name || "—"} — {item.type_title || "درخواست"} — پیش {item.current_approver_name || "—"}
        </Typography>
      ))}
      {items.length > 10 && (
        <Typography variant="caption" display="block">
          و {items.length - 10} مورد دیگر…
        </Typography>
      )}
    </Alert>
  );
}

function ApproversSection({ siteId, onError, onNotice }) {
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
      const res = await setLeaveRequestApprover(departmentId, employee.id);
      onNotice(reassignNotice(res));
      load();
    } catch (err) {
      onError(
        err.response?.data?.detail || "تعیین تأییدکننده با خطا مواجه شد.",
      );
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
    // جدول فشرده (مثل صفحه‌ی «واحدهای سازمانی»): واحد | تأییدکننده‌ی فعلی | تعیین/تغییر
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>واحد سازمانی</TableCell>
            <TableCell>تأییدکننده‌ی فعلی</TableCell>
            <TableCell sx={{ width: { md: "45%" } }}>
              تعیین/تغییر تأییدکننده
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {departments.map((department) => {
            const current = approvers.find(
              (a) => a.department_id === department.id,
            ); // تأییدکننده‌ی فعلی این واحد
            return (
              <TableRow key={department.id}>
                <TableCell sx={{ fontWeight: 700, whiteSpace: "nowrap" }}>
                  {department.name}
                </TableCell>
                <TableCell>
                  {current ? (
                    <Chip
                      size="small"
                      label={`${current.approver_employee.first_name} ${current.approver_employee.last_name}`}
                      onDelete={() => handleRemoveApprover(department.id)}
                    />
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      تعیین نشده
                    </Typography>
                  )}
                </TableCell>
                <TableCell>
                  <EmployeePicker
                    siteId={siteId}
                    placeholder="جست‌وجوی پرسنل…"
                    onSelect={(employee) =>
                      handleSetApprover(department.id, employee)
                    }
                  />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

/**
 * بخش تعیین مسئول نیروی انسانی سایت.
 * ورودی: siteId و onError. «تردد فراموش‌شده» بعد از تأیید سرپرست، توسط این فرد تأیید نهایی می‌شود.
 */
function HrOfficerSection({ siteId, onError, onNotice }) {
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
      const res = await setLeaveRequestHrOfficer(siteId, employee.id);
      onNotice(reassignNotice(res));
      load();
    } catch (err) {
      onError(
        err.response?.data?.detail ||
          "تعیین مسئول نیروی انسانی با خطا مواجه شد.",
      );
    }
  }

  // حذف مسئول نیروی انسانی
  async function handleRemove() {
    try {
      await removeLeaveRequestHrOfficer(siteId);
      load();
    } catch (err) {
      onError(
        err.response?.data?.detail || "حذف مسئول نیروی انسانی با خطا مواجه شد.",
      );
    }
  }

  if (officer === undefined) return null;

  return (
    <Stack spacing={1.5}>
      <Typography variant="body2" color="text.secondary">
        درخواست «تردد فراموش‌شده» اول توسط سرپرست پرسنل تأیید می‌شود و بعد برای
        این فرد ارجاع می‌شود؛ تردد فقط پس از تأیید او در کاراوب ثبت می‌شود.
      </Typography>
      {officer ? (
        <Box>
          <Chip
            label={`${officer.employee.first_name} ${officer.employee.last_name} (${officer.employee.personnel_code})`}
            onDelete={handleRemove}
          />
        </Box>
      ) : (
        <Alert severity="warning">
          هنوز مسئول نیروی انسانی تعیین نشده - ثبت تردد فراموش‌شده ممکن نیست.
        </Alert>
      )}
      <EmployeePicker
        siteId={siteId}
        label="تعیین/تغییر مسئول نیروی انسانی"
        onSelect={handleSet}
      />
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
  const [tolerance, setTolerance] = useState(""); // تلرانس تطبیق تردد (دقیقه) در فرم
  const [savingTolerance, setSavingTolerance] = useState(false);

  // بارگذاری وضعیت ماژول با هر تغییر سایت
  useEffect(() => {
    setModuleStatus(null);
    fetchLeaveRequestModuleStatus(siteId)
      .then((data) => {
        setModuleStatus(data);
        setTolerance(String(data?.punch_tolerance_minutes ?? 30));
      })
      .catch(() => setModuleStatus(null));
  }, [siteId]);

  // ذخیره‌ی تلرانس (۰ تا ۱۸۰ دقیقه)
  async function handleSaveTolerance() {
    const minutes = Number(tolerance);
    if (!Number.isInteger(minutes) || minutes < 0 || minutes > 180) {
      onError("تلرانس باید عددی بین ۰ تا ۱۸۰ دقیقه باشد.");
      return;
    }
    setSavingTolerance(true);
    try {
      const data = await setLeavePunchTolerance(siteId, minutes);
      setModuleStatus(data);
      setTolerance(String(data.punch_tolerance_minutes));
    } catch (err) {
      onError(err.response?.data?.detail || "ذخیره‌ی تلرانس با خطا مواجه شد.");
    } finally {
      setSavingTolerance(false);
    }
  }

  // تغییر سوئیچ: سوئیچ روشن = فعال، پس مقدار disabled معکوس آن ارسال می‌شود
  async function handleToggle(event) {
    setSaving(true);
    try {
      setModuleStatus(
        await setLeaveRequestModuleDisabled(siteId, !event.target.checked),
      );
    } catch (err) {
      onError(
        err.response?.data?.detail || "تغییر وضعیت ماژول با خطا مواجه شد.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (moduleStatus === null) return null;

  // بدون نگاشت کاراوب، ماژول اصلاً در دسترس نیست
  if (!moduleStatus.has_mapping) {
    return (
      <Alert severity="warning" sx={{ mb: 2 }}>
        برای این سایت هنوز نگاشت مرخصی/ماموریت تنظیم نشده است؛ تا تنظیم نشود،
        درخواست مرخصی/ماموریت در دسترس پرسنل نیست.
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
        control={
          <Switch checked={enabled} onChange={handleToggle} disabled={saving} />
        }
        label={
          <Typography fontWeight={700}>
            درخواست مرخصی/ماموریت برای این سایت{" "}
            {enabled ? "فعال است" : "غیرفعال است"}
          </Typography>
        }
      />
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
        {enabled
          ? "با غیرفعال‌کردن، صفحه درخواست برای پرسنل این سایت بسته می‌شود و کارت داشبورد «غیرفعال» نشان می‌دهد. تنظیمات حفظ می‌شوند."
          : "پرسنل این سایت نمی‌توانند درخواست ثبت کنند و سرپرستان هم از پرتال نمی‌توانند درخواست‌ها را تأیید/رد کنند. مشاهده و ویرایش مدیریتی همچنان در دسترس است."}
      </Typography>
      {/* تلرانس تطبیق تردد با مرخصی/ماموریت ساعتی (مثل WF_TL کاراوب) */}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1}
        alignItems={{ xs: "stretch", sm: "flex-end" }}
        sx={{ mt: 2 }}
      >
        <TextField
          size="small"
          type="number"
          label="تلرانس تطبیق تردد (دقیقه)"
          value={tolerance}
          onChange={(e) => setTolerance(e.target.value)}
          inputProps={{ min: 0, max: 180 }}
          sx={{ width: { sm: 220 } }}
        />
        <Button
          variant="outlined"
          onClick={handleSaveTolerance}
          disabled={savingTolerance || tolerance === String(moduleStatus.punch_tolerance_minutes)}
          sx={{ height: 40 }}
        >
          ذخیره
        </Button>
      </Stack>
      <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
        ترددی که تا این مقدار قبل از شروع یا بعد از پایان مرخصی/ماموریت ساعتیِ تأییدشده زده شود، به‌عنوان همان
        مرخصی/ماموریت در کاراوب ثبت می‌شود (حتی اگر تأیید قبل از تردد بوده باشد).
      </Typography>
    </Box>
  );
}

// متن اعلان‌های مرخصی/ماموریت و تردد فراموش‌شده‌ی همین سایت
function LeaveNotifySection({ siteId }) {
  const load = useCallback(
    () => fetchLeaveNotificationTemplates(siteId),
    [siteId],
  );
  const save = useCallback(
    (texts) => saveLeaveNotificationTemplates(siteId, texts),
    [siteId],
  );
  return <NotificationTemplatesEditor key={siteId} load={load} save={save} />;
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
  const [notice, setNotice] = useState(""); // نتیجه‌ی انتقال درخواست‌ها به تأییدکننده‌ی جدید
  const [stuckKey, setStuckKey] = useState(0); // تازه‌سازی هشدار درخواست‌های مانده بعد از تغییر تأییدکننده
  const handleNotice = useCallback((text) => {
    setNotice(text);
    setStuckKey((k) => k + 1);
  }, []);

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
        نوع‌های قابل‌انتخاب پرسنل، تأییدکننده هر واحد سازمانی و مسئول نیروی
        انسانی سایت.
      </Typography>
      <Alert severity="info" sx={{ mb: 2 }}>
        نگاشت ستون‌های جدول‌های کاراوب در «تنظیمات سایت» است - از صفحه سایت
        موردنظر، تب «نگاشت مرخصی/ماموریت» را باز کنید.
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

      {notice && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice("")}>
          {notice}
        </Alert>
      )}

      {/* وضعیت ماژول برای سایت انتخابی */}
      {siteId && <ModuleStatusSection siteId={siteId} onError={setError} />}

      {/* درخواست‌های مانده پیش تأییدکننده‌ی ترک‌کار */}
      {siteId && (
        <StuckRequestsSection siteId={siteId} refreshKey={stuckKey} onError={setError} onNotice={handleNotice} />
      )}

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
              <Typography fontWeight={700}>
                تأییدکننده هر واحد سازمانی
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <ApproversSection siteId={siteId} onError={setError} onNotice={handleNotice} />
            </AccordionDetails>
          </Accordion>

          <Accordion variant="outlined">
            <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
              <Typography fontWeight={700}>
                مسئول نیروی انسانی (تأیید نهایی تردد فراموش‌شده)
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <HrOfficerSection siteId={siteId} onError={setError} onNotice={handleNotice} />
            </AccordionDetails>
          </Accordion>

          <Accordion variant="outlined">
            <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
              <Typography fontWeight={700}>متن اعلان‌ها</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <LeaveNotifySection siteId={siteId} />
            </AccordionDetails>
          </Accordion>
        </Stack>
      )}
    </Box>
  );
}
