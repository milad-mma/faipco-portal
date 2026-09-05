import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  Checkbox,
  CircularProgress,
  Divider,
  FormControlLabel,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import ArrowForwardOutlinedIcon from "@mui/icons-material/ArrowForwardOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import {
  deleteSiteAttendanceMapping,
  deleteSiteConnection,
  deleteSiteMapping,
  fetchSiteAttendanceMapping,
  fetchSiteConnection,
  fetchSiteMapping,
  fetchSites,
  updateSiteGpsLocation,
  upsertSiteAttendanceMapping,
  upsertSiteConnection,
  upsertSiteMapping,
} from "../api/sites";
import SchemaDiscoveryDialog from "../components/SchemaDiscoveryDialog";

const DB_TYPES = [
  { value: "postgresql", label: "PostgreSQL" },
  { value: "mysql", label: "MySQL" },
  { value: "mssql", label: "SQL Server" },
];

const EMPTY_CONNECTION = {
  db_type: "postgresql",
  host: "",
  port: 5432,
  database_name: "",
  username: "",
  password: "",
};
const EMPTY_MAPPING = {
  table_name: "",
  personnel_code_column: "",
  national_code_column: "",
  first_name_column: "",
  last_name_column: "",
  mobile_column: "",
  email_column: "",
  birth_date_column: "",
  is_active_column: "",
  is_active_inverted: false,
  department_column: "",
  department_lookup_table: "",
  department_lookup_id_column: "",
  department_lookup_name_column: "",
  position_column: "",
  position_lookup_table: "",
  position_lookup_id_column: "",
  position_lookup_name_column: "",
  photo_table: "",
  photo_emp_no_column: "",
  photo_thumbnail_column: "",
};
const EMPTY_ATTENDANCE_MAPPING = {
  table_name: "",
  personnel_code_column: "",
  mapping_mode: "single_column",
  date_column: "",
  time_column: "",
  enter_date_column: "",
  enter_time_column: "",
  exit_date_column: "",
  exit_time_column: "",
  calendar_table_name: "",
  calendar_year_column: "",
  calendar_month_column: "",
  calendar_day_column_prefix: "",
};

export default function SiteSettingsPage() {
  const { siteId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = ["mapping", "gps", "attendance-mapping"].includes(searchParams.get("tab"))
    ? searchParams.get("tab")
    : "connection";

  const [site, setSite] = useState(null);
  const [attendanceMappingForm, setAttendanceMappingForm] = useState(EMPTY_ATTENDANCE_MAPPING);
  const [hasExistingAttendanceMapping, setHasExistingAttendanceMapping] = useState(false);
  const [isSavingAttendanceMapping, setIsSavingAttendanceMapping] = useState(false);
  const [attendanceMappingResult, setAttendanceMappingResult] = useState(null); // { success, message } | null
  const [tab, setTab] = useState(initialTab);
  const [isLoading, setIsLoading] = useState(true);

  const [connectionForm, setConnectionForm] = useState(EMPTY_CONNECTION);
  const [hasExistingConnection, setHasExistingConnection] = useState(false);
  const [schemaDiscoveryOpen, setSchemaDiscoveryOpen] = useState(false);
  const [mappingForm, setMappingForm] = useState(EMPTY_MAPPING);
  const [hasExistingMapping, setHasExistingMapping] = useState(false);
  const [gpsForm, setGpsForm] = useState({ gps_latitude: "", gps_longitude: "", gps_radius_meters: "" });
  const [isSavingGps, setIsSavingGps] = useState(false);
  const [gpsResult, setGpsResult] = useState(null);

  const [error, setError] = useState("");
  const [result, setResult] = useState(null); // { success, message } | null
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    Promise.all([
      fetchSites().then((sites) => sites.find((s) => String(s.id) === siteId)),
      fetchSiteConnection(siteId).catch(() => null),
      fetchSiteMapping(siteId).catch(() => null),
      fetchSiteAttendanceMapping(siteId).catch(() => null),
    ]).then(([siteData, connection, mapping, attendanceMapping]) => {
      setSite(siteData || null);
      if (siteData) {
        setGpsForm({
          gps_latitude: siteData.gps_latitude ?? "",
          gps_longitude: siteData.gps_longitude ?? "",
          gps_radius_meters: siteData.gps_radius_meters ?? "",
        });
      }
      if (connection) {
        setConnectionForm({
          db_type: connection.db_type,
          host: connection.host,
          port: connection.port,
          database_name: connection.database_name,
          username: connection.username,
          password: "", // پسورد هرگز از سرور برنمی‌گردد؛ خالی یعنی بدون تغییر
        });
        setHasExistingConnection(true);
      }
      if (mapping) {
        setMappingForm({
          table_name: mapping.table_name,
          personnel_code_column: mapping.personnel_code_column,
          national_code_column: mapping.national_code_column || "",
          first_name_column: mapping.first_name_column,
          last_name_column: mapping.last_name_column,
          mobile_column: mapping.mobile_column || "",
          email_column: mapping.email_column || "",
          birth_date_column: mapping.birth_date_column || "",
          is_active_column: mapping.is_active_column || "",
          is_active_inverted: mapping.is_active_inverted || false,
          department_column: mapping.department_column || "",
          department_lookup_table: mapping.department_lookup_table || "",
          department_lookup_id_column: mapping.department_lookup_id_column || "",
          department_lookup_name_column: mapping.department_lookup_name_column || "",
          position_column: mapping.position_column || "",
          position_lookup_table: mapping.position_lookup_table || "",
          position_lookup_id_column: mapping.position_lookup_id_column || "",
          position_lookup_name_column: mapping.position_lookup_name_column || "",
          photo_table: mapping.photo_table || "",
          photo_emp_no_column: mapping.photo_emp_no_column || "",
          photo_thumbnail_column: mapping.photo_thumbnail_column || "",
        });
        setHasExistingMapping(true);
      }
      if (attendanceMapping) {
        setAttendanceMappingForm({
          table_name: attendanceMapping.table_name,
          personnel_code_column: attendanceMapping.personnel_code_column,
          mapping_mode: attendanceMapping.mapping_mode || "single_column",
          date_column: attendanceMapping.date_column || "",
          time_column: attendanceMapping.time_column || "",
          enter_date_column: attendanceMapping.enter_date_column || "",
          enter_time_column: attendanceMapping.enter_time_column || "",
          exit_date_column: attendanceMapping.exit_date_column || "",
          exit_time_column: attendanceMapping.exit_time_column || "",
          calendar_table_name: attendanceMapping.calendar_table_name || "",
          calendar_year_column: attendanceMapping.calendar_year_column || "",
          calendar_month_column: attendanceMapping.calendar_month_column || "",
          calendar_day_column_prefix: attendanceMapping.calendar_day_column_prefix || "",
        });
        setHasExistingAttendanceMapping(true);
      }
      setIsLoading(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [siteId]);

  function handleTabChange(_, value) {
    setTab(value);
    setResult(null);
    setError("");
    setSearchParams({ tab: value });
  }

  async function handleSaveConnection() {
    setError("");
    setResult(null);
    setIsSaving(true);
    try {
      await upsertSiteConnection(siteId, connectionForm);
      setHasExistingConnection(true);
      setResult({ success: true, message: "اطلاعات اتصال دیتابیس ذخیره شد." });
    } catch (err) {
      setResult({ success: false, message: err.response?.data?.detail || "ذخیره اتصال با خطا مواجه شد." });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDeleteConnection() {
    if (!window.confirm("اتصال دیتابیس این سایت حذف شود؟")) return;
    setIsSaving(true);
    try {
      await deleteSiteConnection(siteId);
      setConnectionForm(EMPTY_CONNECTION);
      setHasExistingConnection(false);
      setResult({ success: true, message: "اتصال دیتابیس حذف شد." });
    } catch (err) {
      setResult({ success: false, message: err.response?.data?.detail || "حذف اتصال با خطا مواجه شد." });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSaveMapping() {
    setError("");
    setResult(null);
    setIsSaving(true);
    try {
      await upsertSiteMapping(siteId, mappingForm);
      setHasExistingMapping(true);
      setResult({ success: true, message: "Mapping ستون‌ها ذخیره شد." });
    } catch (err) {
      setResult({ success: false, message: err.response?.data?.detail || "ذخیره Mapping با خطا مواجه شد." });
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDeleteMapping() {
    if (!window.confirm("Mapping ستون‌های این سایت حذف شود؟")) return;
    setIsSaving(true);
    try {
      await deleteSiteMapping(siteId);
      setMappingForm(EMPTY_MAPPING);
      setHasExistingMapping(false);
      setResult({ success: true, message: "Mapping ستون‌ها حذف شد." });
    } catch (err) {
      setResult({ success: false, message: err.response?.data?.detail || "حذف Mapping با خطا مواجه شد." });
    } finally {
      setIsSaving(false);
    }
  }

  function handleUseCurrentLocation() {
    if (!("geolocation" in navigator)) {
      setGpsResult({ success: false, message: "مرورگر شما از موقعیت‌یابی پشتیبانی نمی‌کند." });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setGpsForm((prev) => ({
          ...prev,
          gps_latitude: position.coords.latitude,
          gps_longitude: position.coords.longitude,
        }));
      },
      () => {
        setGpsResult({ success: false, message: "دریافت موقعیت فعلی با خطا مواجه شد — دسترسی مکان را بررسی کنید." });
      },
      { enableHighAccuracy: true, timeout: 15000 }
    );
  }

  async function handleSaveGps() {
    setGpsResult(null);
    setIsSavingGps(true);
    try {
      const hasAny = gpsForm.gps_latitude !== "" || gpsForm.gps_longitude !== "" || gpsForm.gps_radius_meters !== "";
      const hasAll = gpsForm.gps_latitude !== "" && gpsForm.gps_longitude !== "" && gpsForm.gps_radius_meters !== "";
      if (hasAny && !hasAll) {
        setGpsResult({ success: false, message: "برای تنظیم موقعیت، هر سه فیلد را پر کنید (یا برای پاک‌کردن، هر سه را خالی بگذارید)." });
        return;
      }
      const updated = await updateSiteGpsLocation(siteId, {
        gps_latitude: hasAll ? Number(gpsForm.gps_latitude) : null,
        gps_longitude: hasAll ? Number(gpsForm.gps_longitude) : null,
        gps_radius_meters: hasAll ? Number(gpsForm.gps_radius_meters) : null,
      });
      setGpsForm({
        gps_latitude: updated.gps_latitude ?? "",
        gps_longitude: updated.gps_longitude ?? "",
        gps_radius_meters: updated.gps_radius_meters ?? "",
      });
      setGpsResult({ success: true, message: hasAll ? "موقعیت GPS ذخیره شد." : "محدودیت مکانی این سایت غیرفعال شد." });
    } catch (err) {
      setGpsResult({ success: false, message: err.response?.data?.detail || "ذخیره با خطا مواجه شد." });
    } finally {
      setIsSavingGps(false);
    }
  }

  async function handleSaveAttendanceMapping() {
    setAttendanceMappingResult(null);
    setIsSavingAttendanceMapping(true);
    try {
      await upsertSiteAttendanceMapping(siteId, attendanceMappingForm);
      setHasExistingAttendanceMapping(true);
      setAttendanceMappingResult({ success: true, message: "نگاشت تردد ذخیره شد." });
    } catch (err) {
      setAttendanceMappingResult({
        success: false,
        message: err.response?.data?.detail || "ذخیره نگاشت تردد با خطا مواجه شد.",
      });
    } finally {
      setIsSavingAttendanceMapping(false);
    }
  }

  async function handleDeleteAttendanceMapping() {
    if (!window.confirm("نگاشت تردد این سایت حذف شود؟ گزارش تردد ماهانه برای پرسنل این سایت دیگر در دسترس نخواهد بود.")) return;
    setIsSavingAttendanceMapping(true);
    try {
      await deleteSiteAttendanceMapping(siteId);
      setAttendanceMappingForm(EMPTY_ATTENDANCE_MAPPING);
      setHasExistingAttendanceMapping(false);
      setAttendanceMappingResult({ success: true, message: "نگاشت تردد حذف شد." });
    } catch (err) {
      setAttendanceMappingResult({
        success: false,
        message: err.response?.data?.detail || "حذف نگاشت تردد با خطا مواجه شد.",
      });
    } finally {
      setIsSavingAttendanceMapping(false);
    }
  }

  if (isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <Stack direction="row" alignItems="center" spacing={1.5} sx={{ mb: 3 }}>
        <Button startIcon={<ArrowForwardOutlinedIcon />} onClick={() => navigate("/sites")}>
          بازگشت
        </Button>
        <Typography variant="h5" fontWeight={700}>
          تنظیمات سایت {site ? `— ${site.name}` : ""}
        </Typography>
      </Stack>

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
        <Tabs value={tab} onChange={handleTabChange} sx={{ mb: 3 }}>
          <Tab value="connection" label="اتصال دیتابیس" disabled={isSaving} />
          <Tab value="mapping" label="Mapping ستون‌ها" disabled={isSaving} />
          <Tab value="gps" label="موقعیت GPS" disabled={isSaving} />
          <Tab value="attendance-mapping" label="نگاشت تردد" disabled={isSaving} />
        </Tabs>

        {tab === "connection" && (
          <Stack spacing={2}>
            <TextField
              select
              label="نوع دیتابیس"
              value={connectionForm.db_type}
              onChange={(e) => setConnectionForm({ ...connectionForm, db_type: e.target.value })}
              disabled={isSaving}
            >
              {DB_TYPES.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Host"
              value={connectionForm.host}
              onChange={(e) => setConnectionForm({ ...connectionForm, host: e.target.value })}
              disabled={isSaving}
            />
            <TextField
              label="Port"
              type="number"
              value={connectionForm.port}
              onChange={(e) => setConnectionForm({ ...connectionForm, port: Number(e.target.value) })}
              disabled={isSaving}
            />
            <TextField
              label="نام دیتابیس"
              value={connectionForm.database_name}
              onChange={(e) => setConnectionForm({ ...connectionForm, database_name: e.target.value })}
              disabled={isSaving}
            />
            <TextField
              label="نام کاربری"
              value={connectionForm.username}
              onChange={(e) => setConnectionForm({ ...connectionForm, username: e.target.value })}
              disabled={isSaving}
            />
            <TextField
              label="رمز عبور"
              type="password"
              value={connectionForm.password}
              onChange={(e) => setConnectionForm({ ...connectionForm, password: e.target.value })}
              disabled={isSaving}
              helperText={
                hasExistingConnection
                  ? "برای حفظ رمز فعلی، این فیلد را خالی بگذارید"
                  : "در دیتابیس Portal به‌صورت رمزنگاری‌شده ذخیره می‌شود"
              }
            />

            {(result || error) && (
              <Alert severity={error || !result?.success ? "error" : "success"}>{error || result.message}</Alert>
            )}
            <Stack direction="row" spacing={1.5} sx={{ pt: 1 }}>
              <Button
                variant="contained"
                startIcon={isSaving ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />}
                onClick={handleSaveConnection}
                disabled={isSaving}
              >
                {isSaving ? "در حال ذخیره..." : "ذخیره"}
              </Button>
              {hasExistingConnection && (
                <Button
                  color="error"
                  variant="outlined"
                  startIcon={<DeleteOutlineIcon />}
                  onClick={handleDeleteConnection}
                  disabled={isSaving}
                >
                  حذف اتصال
                </Button>
              )}
              {hasExistingConnection && (
                <Button variant="outlined" onClick={() => setSchemaDiscoveryOpen(true)}>
                  کشف ساختار دیتابیس
                </Button>
              )}
            </Stack>
          </Stack>
        )}

        {tab === "mapping" && (
          <Stack spacing={2}>
            <Typography variant="subtitle2" fontWeight={700}>
              جدول اصلی پرسنل
            </Typography>
            <TextField
              label="نام جدول"
              value={mappingForm.table_name}
              onChange={(e) => setMappingForm({ ...mappingForm, table_name: e.target.value })}
              disabled={isSaving}
            />
            <TextField
              label="ستون کد پرسنلی"
              value={mappingForm.personnel_code_column}
              onChange={(e) => setMappingForm({ ...mappingForm, personnel_code_column: e.target.value })}
              disabled={isSaving}
            />
            <TextField
              label="ستون کد ملی (اختیاری)"
              value={mappingForm.national_code_column}
              onChange={(e) => setMappingForm({ ...mappingForm, national_code_column: e.target.value })}
              disabled={isSaving}
            />
            <TextField
              label="ستون نام"
              value={mappingForm.first_name_column}
              onChange={(e) => setMappingForm({ ...mappingForm, first_name_column: e.target.value })}
              disabled={isSaving}
            />
            <TextField
              label="ستون نام خانوادگی"
              value={mappingForm.last_name_column}
              onChange={(e) => setMappingForm({ ...mappingForm, last_name_column: e.target.value })}
              disabled={isSaving}
            />
            <TextField
              label="ستون موبایل (اختیاری)"
              value={mappingForm.mobile_column}
              onChange={(e) => setMappingForm({ ...mappingForm, mobile_column: e.target.value })}
              disabled={isSaving}
            />
            <TextField
              label="ستون ایمیل (اختیاری)"
              value={mappingForm.email_column}
              onChange={(e) => setMappingForm({ ...mappingForm, email_column: e.target.value })}
              disabled={isSaving}
              helperText="برای «فراموشی رمز عبور» و ارسال بکاپ به ایمیل استفاده می‌شود"
            />
            <TextField
              label="ستون تاریخ تولد شمسی (اختیاری — برای کارت «متولدین روز جاری» در داشبورد)"
              value={mappingForm.birth_date_column}
              onChange={(e) => setMappingForm({ ...mappingForm, birth_date_column: e.target.value })}
              helperText='فرمت مورد انتظار مثل «1370/05/21» یا «13700521»'
              disabled={isSaving}
            />
            <TextField
              label="ستون وضعیت فعال/غیرفعال (اختیاری)"
              value={mappingForm.is_active_column}
              onChange={(e) => setMappingForm({ ...mappingForm, is_active_column: e.target.value })}
              helperText="اگر منبع ستونی مثل IsActive یا IsCut دارد که با ۰/۱ نشان می‌دهد"
              disabled={isSaving}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={mappingForm.is_active_inverted}
                  onChange={(e) => setMappingForm({ ...mappingForm, is_active_inverted: e.target.checked })}
                  disabled={isSaving}
                />
              }
              label="منطق این ستون برعکس است (مثل IsCut: ۱=غیرفعال، ۰=فعال)"
            />

            <Divider sx={{ my: 1 }} />

            <Typography variant="subtitle2" fontWeight={700}>
              واحد سازمانی (اختیاری)
            </Typography>
            <TextField
              label="ستون کد واحد در جدول پرسنل"
              value={mappingForm.department_column}
              onChange={(e) => setMappingForm({ ...mappingForm, department_column: e.target.value })}
              helperText="مثال: Sec_No"
              disabled={isSaving}
            />
            <Typography variant="caption" color="text.secondary">
              اگر جدول جداگانه‌ای این کد را به نام واقعی واحد ترجمه می‌کند (مثل dbo.Sections)،
              سه فیلد زیر را هم پر کنید تا نام واحدها خودکار همگام شود:
            </Typography>
            <TextField
              label="نام جدول Lookup"
              value={mappingForm.department_lookup_table}
              onChange={(e) => setMappingForm({ ...mappingForm, department_lookup_table: e.target.value })}
              helperText="مثال: dbo.Sections"
              disabled={isSaving}
            />
            <TextField
              label="ستون کد در جدول Lookup"
              value={mappingForm.department_lookup_id_column}
              onChange={(e) => setMappingForm({ ...mappingForm, department_lookup_id_column: e.target.value })}
              helperText="مثال: Sec_No"
              disabled={isSaving}
            />
            <TextField
              label="ستون نام واحد در جدول Lookup"
              value={mappingForm.department_lookup_name_column}
              onChange={(e) =>
                setMappingForm({ ...mappingForm, department_lookup_name_column: e.target.value })
              }
              helperText="مثال: Title"
              disabled={isSaving}
            />

            <Divider sx={{ my: 1 }} />

            <Typography variant="subtitle2" fontWeight={700}>
              سمت / عنوان شغلی (اختیاری)
            </Typography>
            <TextField
              label="ستون کد سمت در جدول پرسنل"
              value={mappingForm.position_column}
              onChange={(e) => setMappingForm({ ...mappingForm, position_column: e.target.value })}
              helperText="مثال: Pos_No"
              disabled={isSaving}
            />
            <Typography variant="caption" color="text.secondary">
              اگر جدول جداگانه‌ای این کد را به نام واقعی سمت ترجمه می‌کند (مثل Position با
              ستون‌های Pos_No/Title)، سه فیلد زیر را هم پر کنید:
            </Typography>
            <TextField
              label="نام جدول Lookup"
              value={mappingForm.position_lookup_table}
              onChange={(e) => setMappingForm({ ...mappingForm, position_lookup_table: e.target.value })}
              helperText="مثال: Position"
              disabled={isSaving}
            />
            <TextField
              label="ستون کد در جدول Lookup"
              value={mappingForm.position_lookup_id_column}
              onChange={(e) => setMappingForm({ ...mappingForm, position_lookup_id_column: e.target.value })}
              helperText="مثال: Pos_No"
              disabled={isSaving}
            />
            <TextField
              label="ستون عنوان سمت در جدول Lookup"
              value={mappingForm.position_lookup_name_column}
              onChange={(e) =>
                setMappingForm({ ...mappingForm, position_lookup_name_column: e.target.value })
              }
              helperText="مثال: Title"
              disabled={isSaving}
            />

            <Divider sx={{ my: 1 }} />

            <Typography variant="subtitle2" fontWeight={700}>
              عکس پرسنل (اختیاری)
            </Typography>
            <Typography variant="caption" color="text.secondary">
              اگر جدول جداگانه‌ای عکس بندانگشتی پرسنل را نگه می‌دارد (مثل EmployeeExtendedInfo)،
              هر سه فیلد زیر را پر کنید:
            </Typography>
            <TextField
              label="نام جدول عکس"
              value={mappingForm.photo_table}
              onChange={(e) => setMappingForm({ ...mappingForm, photo_table: e.target.value })}
              helperText="مثال: EmployeeExtendedInfo"
              disabled={isSaving}
            />
            <TextField
              label="ستون کد پرسنلی در جدول عکس"
              value={mappingForm.photo_emp_no_column}
              onChange={(e) => setMappingForm({ ...mappingForm, photo_emp_no_column: e.target.value })}
              helperText="مثال: Emp_No"
              disabled={isSaving}
            />
            <TextField
              label="ستون تصویر بندانگشتی"
              value={mappingForm.photo_thumbnail_column}
              onChange={(e) => setMappingForm({ ...mappingForm, photo_thumbnail_column: e.target.value })}
              helperText="مثال: ThumbnailImg"
              disabled={isSaving}
            />

            {(result || error) && (
              <Alert severity={error || !result?.success ? "error" : "success"}>{error || result.message}</Alert>
            )}
            <Stack direction="row" spacing={1.5} sx={{ pt: 1 }}>
              <Button
                variant="contained"
                startIcon={isSaving ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />}
                onClick={handleSaveMapping}
                disabled={isSaving}
              >
                {isSaving ? "در حال ذخیره..." : "ذخیره"}
              </Button>
              {hasExistingMapping && (
                <Button
                  color="error"
                  variant="outlined"
                  startIcon={<DeleteOutlineIcon />}
                  onClick={handleDeleteMapping}
                  disabled={isSaving}
                >
                  حذف Mapping
                </Button>
              )}
            </Stack>
          </Stack>
        )}

        {tab === "gps" && (
          <Stack spacing={2.5}>
            <Alert severity="info">
              اگر هر سه فیلد را پر و ذخیره کنید، «حضور دوره‌ای» و «ثبت ورود/خروج آزمایشی» فقط برای
              پرسنل این سایت وقتی داخل این شعاع باشند مجاز می‌شود. اگر خالی بماند، هیچ محدودیت مکانی
              برای این سایت اعمال نمی‌شود.
            </Alert>
            <Alert severity="warning">
              دقت GPS داخل ساختمان‌های صنعتی معمولاً ضعیف می‌شود (گاهی ۵۰ تا ۱۰۰+ متر خطا). حداقل
              ۱۰۰ تا ۱۵۰ متر شعاع پیشنهاد می‌شود تا پرسنلی که واقعاً حاضرند به‌اشتباه رد نشوند.
            </Alert>

            <Stack direction="row" spacing={2}>
              <TextField
                label="عرض جغرافیایی (Latitude)"
                type="number"
                value={gpsForm.gps_latitude}
                onChange={(e) => setGpsForm({ ...gpsForm, gps_latitude: e.target.value })}
                disabled={isSavingGps}
                fullWidth
                inputProps={{ step: "any" }}
              />
              <TextField
                label="طول جغرافیایی (Longitude)"
                type="number"
                value={gpsForm.gps_longitude}
                onChange={(e) => setGpsForm({ ...gpsForm, gps_longitude: e.target.value })}
                disabled={isSavingGps}
                fullWidth
                inputProps={{ step: "any" }}
              />
            </Stack>
            <TextField
              label="شعاع مجاز (متر)"
              type="number"
              value={gpsForm.gps_radius_meters}
              onChange={(e) => setGpsForm({ ...gpsForm, gps_radius_meters: e.target.value })}
              disabled={isSavingGps}
              helperText="پیشنهاد: حداقل ۱۰۰ تا ۱۵۰ متر"
              inputProps={{ min: 1 }}
            />

            <Box>
              <Button onClick={handleUseCurrentLocation} disabled={isSavingGps}>
                استفاده از موقعیت فعلی من
              </Button>
            </Box>

            {gpsResult && (
              <Alert severity={gpsResult.success ? "success" : "error"}>{gpsResult.message}</Alert>
            )}
            <Stack direction="row" spacing={1.5}>
              <Button
                variant="contained"
                startIcon={isSavingGps ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />}
                onClick={handleSaveGps}
                disabled={isSavingGps}
              >
                {isSavingGps ? "در حال ذخیره..." : "ذخیره"}
              </Button>
            </Stack>
          </Stack>
        )}

        {tab === "attendance-mapping" && (
          <Stack spacing={2.5}>
            <Alert severity="info">
              اگر تنظیم شود، پرسنل این سایت می‌توانند تردد ماهانه واقعی خودشان (از دستگاه‌های حضور و
              غیاب کارخانه) را در پنل کاربری خودشان ببینند — از همین اتصال دیتابیس بالا (تب «اتصال
              دیتابیس») خوانده می‌شود. چون نرم‌افزارهای مختلف حضور و غیاب دستگاهی نام جدول/ستون‌های
              متفاوتی دارند، این‌ها را دقیقاً مطابق دیتابیس واقعی این سایت وارد کنید.
            </Alert>

            <TextField
              label="نام جدول"
              value={attendanceMappingForm.table_name}
              onChange={(e) => setAttendanceMappingForm({ ...attendanceMappingForm, table_name: e.target.value })}
              disabled={isSavingAttendanceMapping}
              helperText="نام جدولی که رکوردهای خام ورود/خروج دستگاه در آن ذخیره می‌شود"
            />
            <TextField
              label="ستون کد پرسنلی"
              value={attendanceMappingForm.personnel_code_column}
              onChange={(e) =>
                setAttendanceMappingForm({ ...attendanceMappingForm, personnel_code_column: e.target.value })
              }
              disabled={isSavingAttendanceMapping}
            />
            <TextField
              select
              label="روش نگاشت تردد"
              value={attendanceMappingForm.mapping_mode}
              onChange={(e) =>
                setAttendanceMappingForm({
                  ...attendanceMappingForm,
                  mapping_mode: e.target.value,
                  date_column: "",
                  time_column: "",
                  enter_date_column: "",
                  enter_time_column: "",
                  exit_date_column: "",
                  exit_time_column: "",
                })
              }
              disabled={isSavingAttendanceMapping}
              helperText="بر اساس ساختار جدول واقعی نرم‌افزار حضور و غیاب این سایت انتخاب کنید"
            >
              <MenuItem value="single_column">یک ستون تاریخ + یک ستون ساعت (هر ردیف = یک تردد منفرد)</MenuItem>
              <MenuItem value="enter_exit_columns">ستون‌های جدای ورود و خروج (هر ردیف = یک نشست کامل)</MenuItem>
            </TextField>

            {attendanceMappingForm.mapping_mode === "single_column" ? (
              <>
                <TextField
                  label="ستون تاریخ"
                  value={attendanceMappingForm.date_column}
                  onChange={(e) => setAttendanceMappingForm({ ...attendanceMappingForm, date_column: e.target.value })}
                  disabled={isSavingAttendanceMapping}
                  helperText='فرمت مورد انتظار: عدد شمسی فشرده بدون جداکننده، مثل 14050524'
                />
                <TextField
                  label="ستون ساعت"
                  value={attendanceMappingForm.time_column}
                  onChange={(e) => setAttendanceMappingForm({ ...attendanceMappingForm, time_column: e.target.value })}
                  disabled={isSavingAttendanceMapping}
                  helperText='فرمت مورد انتظار: عدد فشرده بدون جداکننده، مثل 618 برای 06:18 یا 1401 برای 14:01'
                />
              </>
            ) : (
              <>
                <TextField
                  label="ستون تاریخ ورود"
                  value={attendanceMappingForm.enter_date_column}
                  onChange={(e) =>
                    setAttendanceMappingForm({ ...attendanceMappingForm, enter_date_column: e.target.value })
                  }
                  disabled={isSavingAttendanceMapping}
                  helperText='مثلاً enterdate — فرمت: عدد شمسی فشرده، مثل 14050524'
                />
                <TextField
                  label="ستون ساعت ورود"
                  value={attendanceMappingForm.enter_time_column}
                  onChange={(e) =>
                    setAttendanceMappingForm({ ...attendanceMappingForm, enter_time_column: e.target.value })
                  }
                  disabled={isSavingAttendanceMapping}
                  helperText='مثلاً entertime — فرمت: عدد فشرده، مثل 618 یا 1401'
                />
                <TextField
                  label="ستون تاریخ خروج"
                  value={attendanceMappingForm.exit_date_column}
                  onChange={(e) =>
                    setAttendanceMappingForm({ ...attendanceMappingForm, exit_date_column: e.target.value })
                  }
                  disabled={isSavingAttendanceMapping}
                  helperText='مثلاً exitdate'
                />
                <TextField
                  label="ستون ساعت خروج"
                  value={attendanceMappingForm.exit_time_column}
                  onChange={(e) =>
                    setAttendanceMappingForm({ ...attendanceMappingForm, exit_time_column: e.target.value })
                  }
                  disabled={isSavingAttendanceMapping}
                  helperText='مثلاً exittime — اگر کاربری هنوز خروج نزده باشد، این ستون‌ها می‌توانند خالی (NULL) باشند'
                />
              </>
            )}

            <Divider sx={{ my: 1 }} />
            <Typography variant="subtitle2" fontWeight={700}>
              تقویم و تعطیلات (اختیاری)
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ mt: -1.5 }}>
              اگر پر شود، روزهای تعطیل در گزارش تردد با رنگ قرمز مشخص می‌شوند. یک جدول با یک ردیف
              به‌ازای هر (سال، ماه شمسی) و ستون‌های روز شماره‌گذاری‌شده (مثلاً D1 تا D31) — هر ستون
              روز، صفر یعنی روز عادی و هر عدد غیرصفر یعنی آن روز تعطیل است.
            </Typography>
            <TextField
              label="نام جدول تقویم"
              value={attendanceMappingForm.calendar_table_name}
              onChange={(e) =>
                setAttendanceMappingForm({ ...attendanceMappingForm, calendar_table_name: e.target.value })
              }
              disabled={isSavingAttendanceMapping}
            />
            <TextField
              label="ستون سال"
              value={attendanceMappingForm.calendar_year_column}
              onChange={(e) =>
                setAttendanceMappingForm({ ...attendanceMappingForm, calendar_year_column: e.target.value })
              }
              disabled={isSavingAttendanceMapping}
              helperText="ستونی که سال شمسی را دارد (مثلاً 1405)"
            />
            <TextField
              label="ستون ماه"
              value={attendanceMappingForm.calendar_month_column}
              onChange={(e) =>
                setAttendanceMappingForm({ ...attendanceMappingForm, calendar_month_column: e.target.value })
              }
              disabled={isSavingAttendanceMapping}
              helperText="ستونی که شماره ماه شمسی را دارد (۱ تا ۱۲)"
            />
            <TextField
              label="پیشوند ستون‌های روز"
              value={attendanceMappingForm.calendar_day_column_prefix}
              onChange={(e) =>
                setAttendanceMappingForm({ ...attendanceMappingForm, calendar_day_column_prefix: e.target.value })
              }
              disabled={isSavingAttendanceMapping}
              helperText='مثلاً "D" اگر ستون‌ها D1، D2، ... D31 نامگذاری شده‌اند'
            />

            {attendanceMappingResult && (
              <Alert severity={attendanceMappingResult.success ? "success" : "error"}>
                {attendanceMappingResult.message}
              </Alert>
            )}
            <Stack direction="row" spacing={1.5} sx={{ pt: 1 }}>
              <Button
                variant="contained"
                startIcon={isSavingAttendanceMapping ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />}
                onClick={handleSaveAttendanceMapping}
                disabled={isSavingAttendanceMapping}
              >
                {isSavingAttendanceMapping ? "در حال ذخیره..." : "ذخیره"}
              </Button>
              {hasExistingAttendanceMapping && (
                <Button
                  color="error"
                  variant="outlined"
                  startIcon={<DeleteOutlineIcon />}
                  onClick={handleDeleteAttendanceMapping}
                  disabled={isSavingAttendanceMapping}
                >
                  حذف نگاشت
                </Button>
              )}
            </Stack>
          </Stack>
        )}
      </Card>

      <SchemaDiscoveryDialog
        open={schemaDiscoveryOpen}
        onClose={() => setSchemaDiscoveryOpen(false)}
        siteId={siteId}
      />
    </Box>
  );
}
