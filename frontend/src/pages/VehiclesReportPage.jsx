// صفحه‌ی گزارش خودروهای پرسنل.
// فهرست خودروها را با جست‌وجو، فیلتر سایت و مرتب‌سازی (کارتی در موبایل، جدولی در دسکتاپ) نشان می‌دهد
// و برای دارندگان مجوز vehicles.manage امکان ویرایش و حذف خودرو را فراهم می‌کند.
import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  InputAdornment,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TextField,
  Typography,
  useMediaQuery,
} from "@mui/material";
import SearchOutlinedIcon from "@mui/icons-material/SearchOutlined";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import { useAuth } from "../context/AuthContext";
import IranianLicensePlateInput, { isPlateComplete, PlateDisplay } from "../components/IranianLicensePlateInput";
import SiteFilterSelect from "../components/SiteFilterSelect";
import { deleteVehicleAdmin, fetchAllVehicles, updateVehicleAdmin } from "../api/vehicles";

const EMPTY_PLATE = { digits1: "", letter: "", digits2: "", iranCode: "" };  // مقدار خالی پلاک ایرانی

// ستون‌های مرتب‌پذیر جدول (key همان فیلد خودرو؛ plate به‌صورت رشته‌ی ترکیبی مقایسه می‌شود)
const COLUMNS = [
  { key: "employee_name", label: "پرسنل" },
  { key: "site_name", label: "سایت" },
  { key: "department_name", label: "واحد سازمانی" },
  { key: "vehicle_type", label: "نوع خودرو" },
  { key: "color", label: "رنگ" },
  { key: "plate", label: "پلاک" },
];

// ورودی: رکورد خودرو؛ خروجی: اجزای پلاک به‌صورت یک رشته‌ی پیوسته (برای جست‌وجو و مرتب‌سازی)
function plateAsString(v) {
  return `${v.plate_digits1}${v.plate_letter}${v.plate_digits2}${v.plate_iran_code}`;
}

// دیالوگ ویرایش خودرو (نوع، رنگ، پلاک).
// ورودی: خودروی در حال ویرایش (null = بسته)، onClose و onSaved که با خودروی به‌روزشده صدا زده می‌شود.
// یک نمونه‌ی مشترک برای همه‌ی ردیف‌هاست، پس فیلدها با هر تغییر vehicle از نو پر می‌شوند.
function EditVehicleDialog({ vehicle, onClose, onSaved }) {
  const [vehicleType, setVehicleType] = useState("");
  const [color, setColor] = useState("");
  const [plate, setPlate] = useState(EMPTY_PLATE);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    // پر کردن فیلدهای فرم از روی خودروی انتخاب‌شده، هر بار که vehicle عوض شود
    if (!vehicle) return;
    setVehicleType(vehicle.vehicle_type);
    setColor(vehicle.color);
    setPlate({
      digits1: vehicle.plate_digits1,
      letter: vehicle.plate_letter,
      digits2: vehicle.plate_digits2,
      iranCode: vehicle.plate_iran_code,
    });
    setError("");
  }, [vehicle]);

  const canSave = vehicleType.trim() && color.trim() && isPlateComplete(plate) && !isSaving;  // همه‌ی فیلدها و پلاک کامل الزامی است

  // تغییرات خودرو را روی سرور ذخیره و نتیجه را به والد می‌دهد
  async function handleSave() {
    if (!canSave) return;
    setError("");
    setIsSaving(true);
    try {
      const updated = await updateVehicleAdmin(vehicle.id, {
        vehicle_type: vehicleType.trim(),
        color: color.trim(),
        plate_digits1: plate.digits1,
        plate_letter: plate.letter,
        plate_digits2: plate.digits2,
        plate_iran_code: plate.iranCode,
      });
      onSaved(updated);
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره تغییرات با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={Boolean(vehicle)} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>ویرایش خودرو</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          <TextField label="نوع/مدل خودرو" value={vehicleType} onChange={(e) => setVehicleType(e.target.value)} fullWidth />
          <TextField label="رنگ خودرو" value={color} onChange={(e) => setColor(e.target.value)} fullWidth />
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
              شماره پلاک
            </Typography>
            <IranianLicensePlateInput value={plate} onChange={setPlate} disabled={isSaving} />
          </Box>
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ p: 2.5 }}>
        <Button onClick={onClose}>انصراف</Button>
        <Button variant="contained" disabled={!canSave} onClick={handleSave}>
          {isSaving ? "در حال ذخیره..." : "ذخیره"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/**
 * کامپوننت گزارش خودروهای پرسنل؛ ورودی ندارد.
 * با مجوز vehicles.manage دکمه‌های ویرایش/حذف نمایش داده می‌شوند (Backend هم همین مجوز را بررسی می‌کند)؛
 * بدون آن (مثلاً نقش حراست) گزارش فقط‌خواندنی است.
 */
export default function VehiclesReportPage() {
  const { user } = useAuth();
  const isMobile = useMediaQuery((theme) => theme.breakpoints.down("sm"));
  const [vehicles, setVehicles] = useState(null);
  const [search, setSearch] = useState("");
  const [selectedSiteId, setSelectedSiteId] = useState(null);  // null = همه‌ی سایت‌های مجاز
  const [sortKey, setSortKey] = useState("employee_name");
  const [sortDir, setSortDir] = useState("asc");
  const [editingVehicle, setEditingVehicle] = useState(null);  // خودرویی که دیالوگ ویرایشش باز است
  const [vehicleToDelete, setVehicleToDelete] = useState(null);  // خودرویی که دیالوگ تأیید حذفش باز است
  const [deletingId, setDeletingId] = useState(null);  // شناسه‌ی خودرویی که حذفش در جریان است

  // خودروهای سایت انتخاب‌شده را از سرور می‌گیرد
  function loadVehicles() {
    fetchAllVehicles(selectedSiteId).then(setVehicles);
  }

  useEffect(() => {
    // بارگذاری مجدد خودروها با تغییر فیلتر سایت
    loadVehicles();
  }, [selectedSiteId]);

  // خودروی انتخاب‌شده را حذف و از فهرست برمی‌دارد
  async function handleConfirmDelete() {
    if (!vehicleToDelete) return;
    setDeletingId(vehicleToDelete.id);
    try {
      await deleteVehicleAdmin(vehicleToDelete.id);
      setVehicles((prev) => prev.filter((v) => v.id !== vehicleToDelete.id));
      setVehicleToDelete(null);
    } finally {
      setDeletingId(null);
    }
  }

  // خودروی ویرایش‌شده را در فهرست ادغام و دیالوگ را می‌بندد
  function handleSaved(updated) {
    setVehicles((prev) => prev.map((v) => (v.id === updated.id ? { ...v, ...updated } : v)));
    setEditingVehicle(null);
  }

  // کلیک روی سرستون: برعکس‌کردن جهت همان ستون یا مرتب‌سازی صعودی ستون جدید
  function handleSort(key) {
    if (sortKey === key) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  // جست‌وجو و مرتب‌سازی سمت فرانت‌اند روی کل فهرست؛ خروجی: فهرست نمایشی یا null در حال بارگذاری
  const displayedVehicles = useMemo(() => {
    if (vehicles === null) return null;
    const term = search.trim().toLowerCase();
    const filtered = term
      ? vehicles.filter((v) =>
          [v.employee_name, v.site_name, v.department_name, v.vehicle_type, v.color, plateAsString(v)]
            .filter(Boolean)
            .some((field) => field.toLowerCase().includes(term))
        )
      : vehicles;

    const sorted = [...filtered].sort((a, b) => {
      const aVal = sortKey === "plate" ? plateAsString(a) : a[sortKey] || "";
      const bVal = sortKey === "plate" ? plateAsString(b) : b[sortKey] || "";
      const cmp = aVal.localeCompare(bVal, "fa");
      return sortDir === "asc" ? cmp : -cmp;
    });
    return sorted;
  }, [vehicles, search, sortKey, sortDir]);

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        خودروهای پرسنل
      </Typography>

      <Stack direction="row" spacing={2} sx={{ mb: 2 }} flexWrap="wrap" rowGap={2}>
        <TextField
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="جست‌وجو بر اساس نام، واحد، نوع خودرو، رنگ یا شماره پلاک..."
          size="small"
          sx={{ flex: 1, minWidth: 240, maxWidth: 480 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchOutlinedIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
        />
        {/* فیلتر سایت بر اساس سایت‌های مجاز کاربر برای vehicles.view_all */}
        <SiteFilterSelect value={selectedSiteId} permission="vehicles.view_all" onChange={setSelectedSiteId} />
      </Stack>

      {/* محتوا: بارگذاری / فهرست خالی / کارت‌های موبایل / جدول دسکتاپ */}
      {displayedVehicles === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : displayedVehicles.length === 0 ? (
        <Card variant="outlined" sx={{ p: 4, borderRadius: 2, textAlign: "center" }}>
          <Typography variant="body2" color="text.secondary">
            {search ? "چیزی با این مشخصات پیدا نشد." : "هیچ خودرویی ثبت نشده است."}
          </Typography>
        </Card>
      ) : isMobile ? (
        // نمایش کارتی — موبایل
        <Stack spacing={1.5}>
          {displayedVehicles.map((v) => (
            <Card key={v.id} variant="outlined" sx={{ borderRadius: 2, p: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 1 }}>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="body2" fontWeight={700} noWrap>
                    {v.employee_name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" noWrap>
                    {[v.site_name, v.department_name].filter(Boolean).join(" — ") || "—"}
                  </Typography>
                </Box>
                {user?.can_manage_vehicles && (
                  <Stack direction="row" sx={{ flexShrink: 0 }}>
                    <IconButton size="small" onClick={() => setEditingVehicle(v)} aria-label="ویرایش">
                      <EditOutlinedIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      color="error"
                      disabled={deletingId === v.id}
                      onClick={() => setVehicleToDelete(v)}
                      aria-label="حذف"
                    >
                      <DeleteOutlineOutlinedIcon fontSize="small" />
                    </IconButton>
                  </Stack>
                )}
              </Stack>
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Box>
                  <Typography variant="body2">{v.vehicle_type}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {v.color}
                  </Typography>
                </Box>
                <PlateDisplay
                  digits1={v.plate_digits1}
                  letter={v.plate_letter}
                  digits2={v.plate_digits2}
                  iranCode={v.plate_iran_code}
                />
              </Stack>
            </Card>
          ))}
        </Stack>
      ) : (
        // نمایش جدولی — دسکتاپ
        <Card variant="outlined" sx={{ borderRadius: 2, overflow: "hidden" }}>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  {COLUMNS.map((col) => (
                    <TableCell key={col.key}>
                      <TableSortLabel
                        active={sortKey === col.key}
                        direction={sortKey === col.key ? sortDir : "asc"}
                        onClick={() => handleSort(col.key)}
                      >
                        {col.label}
                      </TableSortLabel>
                    </TableCell>
                  ))}
                  {user?.can_manage_vehicles && <TableCell align="left">عملیات</TableCell>}
                </TableRow>
              </TableHead>
              <TableBody>
                {displayedVehicles.map((v) => (
                  <TableRow key={v.id} hover>
                    <TableCell>{v.employee_name}</TableCell>
                    <TableCell>{v.site_name || "—"}</TableCell>
                    <TableCell>{v.department_name || "—"}</TableCell>
                    <TableCell>{v.vehicle_type}</TableCell>
                    <TableCell>{v.color}</TableCell>
                    <TableCell>
                      <PlateDisplay
                        digits1={v.plate_digits1}
                        letter={v.plate_letter}
                        digits2={v.plate_digits2}
                        iranCode={v.plate_iran_code}
                      />
                    </TableCell>
                    {user?.can_manage_vehicles && (
                      <TableCell align="left">
                        <IconButton size="small" onClick={() => setEditingVehicle(v)} aria-label="ویرایش">
                          <EditOutlinedIcon fontSize="small" />
                        </IconButton>
                        <IconButton
                          size="small"
                          color="error"
                          disabled={deletingId === v.id}
                          onClick={() => setVehicleToDelete(v)}
                          aria-label="حذف"
                        >
                          <DeleteOutlineOutlinedIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Card>
      )}

      {/* دیالوگ ویرایش خودرو */}
      <EditVehicleDialog vehicle={editingVehicle} onClose={() => setEditingVehicle(null)} onSaved={handleSaved} />

      {/* دیالوگ تأیید حذف خودرو */}
      <Dialog open={Boolean(vehicleToDelete)} onClose={() => setVehicleToDelete(null)} maxWidth="xs" fullWidth>
        <DialogTitle>حذف خودرو</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            آیا از حذف خودروی {vehicleToDelete?.vehicle_type} متعلق به {vehicleToDelete?.employee_name} مطمئن هستید؟
            این عمل قابل‌بازگشت نیست.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setVehicleToDelete(null)}>انصراف</Button>
          <Button variant="contained" color="error" disabled={deletingId !== null} onClick={handleConfirmDelete}>
            حذف
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
