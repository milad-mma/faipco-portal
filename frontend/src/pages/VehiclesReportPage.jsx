import { useEffect, useState } from "react";
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
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import { useAuth } from "../context/AuthContext";
import IranianLicensePlateInput, { isPlateComplete, PlateDisplay } from "../components/IranianLicensePlateInput";
import { deleteVehicleAdmin, fetchAllVehicles, updateVehicleAdmin } from "../api/vehicles";

const EMPTY_PLATE = { digits1: "", letter: "", digits2: "", iranCode: "" };

function EditVehicleDialog({ vehicle, onClose, onSaved }) {
  const [vehicleType, setVehicleType] = useState(vehicle?.vehicle_type || "");
  const [color, setColor] = useState(vehicle?.color || "");
  const [plate, setPlate] = useState(
    vehicle
      ? {
          digits1: vehicle.plate_digits1,
          letter: vehicle.plate_letter,
          digits2: vehicle.plate_digits2,
          iranCode: vehicle.plate_iran_code,
        }
      : EMPTY_PLATE
  );
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  const canSave = vehicleType.trim() && color.trim() && isPlateComplete(plate) && !isSaving;

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
      setError(err.response?.data?.detail || "ذخیره تغییرات ناموفق بود.");
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
 * گزارش خودروهای همه پرسنل — برای Admin کامل (ویرایش/حذف)، برای نقش
 * «حراست» فقط‌خواندنی (بدون دکمه ویرایش/حذف) — دقیقاً همان تصمیمی که
 * Backend هم با require_permission("vehicles.manage") فقط برای Admin
 * واقعی اعمال می‌کند؛ این‌جا هم برای تجربه کاربری، همان دکمه‌ها اصلاً
 * برای غیر-Admin نمایش داده نمی‌شوند.
 */
export default function VehiclesReportPage() {
  const { user } = useAuth();
  const [vehicles, setVehicles] = useState(null);
  const [editingVehicle, setEditingVehicle] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  function loadVehicles() {
    fetchAllVehicles().then(setVehicles);
  }

  useEffect(() => {
    loadVehicles();
  }, []);

  async function handleDelete(vehicleId) {
    setDeletingId(vehicleId);
    try {
      await deleteVehicleAdmin(vehicleId);
      setVehicles((prev) => prev.filter((v) => v.id !== vehicleId));
    } finally {
      setDeletingId(null);
    }
  }

  function handleSaved(updated) {
    setVehicles((prev) =>
      prev.map((v) => (v.id === updated.id ? { ...v, ...updated } : v))
    );
    setEditingVehicle(null);
  }

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 3 }}>
        گزارش خودروهای پرسنل
      </Typography>

      <Card variant="outlined" sx={{ borderRadius: 2, overflow: "hidden" }}>
        {vehicles === null ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
            <CircularProgress />
          </Box>
        ) : vehicles.length === 0 ? (
          <Box sx={{ p: 4, textAlign: "center" }}>
            <Typography variant="body2" color="text.secondary">
              هیچ خودرویی ثبت نشده است.
            </Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>پرسنل</TableCell>
                  <TableCell>کد پرسنلی</TableCell>
                  <TableCell>سایت</TableCell>
                  <TableCell>واحد سازمانی</TableCell>
                  <TableCell>نوع خودرو</TableCell>
                  <TableCell>رنگ</TableCell>
                  <TableCell>پلاک</TableCell>
                  {user?.is_superuser && <TableCell align="left">عملیات</TableCell>}
                </TableRow>
              </TableHead>
              <TableBody>
                {vehicles.map((v) => (
                  <TableRow key={v.id} hover>
                    <TableCell>{v.employee_name}</TableCell>
                    <TableCell>{v.personnel_code}</TableCell>
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
                    {user?.is_superuser && (
                      <TableCell align="left">
                        <IconButton size="small" onClick={() => setEditingVehicle(v)} aria-label="ویرایش">
                          <EditOutlinedIcon fontSize="small" />
                        </IconButton>
                        <IconButton
                          size="small"
                          color="error"
                          disabled={deletingId === v.id}
                          onClick={() => handleDelete(v.id)}
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
        )}
      </Card>

      <EditVehicleDialog vehicle={editingVehicle} onClose={() => setEditingVehicle(null)} onSaved={handleSaved} />
    </Box>
  );
}
