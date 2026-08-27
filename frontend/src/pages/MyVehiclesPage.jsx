import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import DirectionsCarFilledOutlinedIcon from "@mui/icons-material/DirectionsCarFilledOutlined";
import PaletteOutlinedIcon from "@mui/icons-material/PaletteOutlined";
import IranianLicensePlateInput, { isPlateComplete, PlateDisplay } from "../components/IranianLicensePlateInput";
import { createMyVehicle, deleteMyVehicle, fetchMyVehicles } from "../api/vehicles";

const EMPTY_PLATE = { digits1: "", letter: "", digits2: "", iranCode: "" };

/**
 * قابلیت «خودروهای من» — هر پرسنل می‌تواند یک یا چند خودرو برای خودش ثبت
 * کند؛ همین صفحه لیست خودروهای خودش را هم نشان می‌دهد. برای همه پرسنل
 * (بدون نیاز به مجوز خاص) در دسترس است.
 */
export default function MyVehiclesPage() {
  const [vehicles, setVehicles] = useState(null);
  const [vehicleType, setVehicleType] = useState("");
  const [color, setColor] = useState("");
  const [plate, setPlate] = useState(EMPTY_PLATE);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState(null);

  function loadVehicles() {
    fetchMyVehicles().then(setVehicles);
  }

  useEffect(() => {
    loadVehicles();
  }, []);

  const canSubmit = vehicleType.trim() && color.trim() && isPlateComplete(plate) && !isSubmitting;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!canSubmit) return;
    setError("");
    setIsSubmitting(true);
    try {
      await createMyVehicle({
        vehicle_type: vehicleType.trim(),
        color: color.trim(),
        plate_digits1: plate.digits1,
        plate_letter: plate.letter,
        plate_digits2: plate.digits2,
        plate_iran_code: plate.iranCode,
      });
      setVehicleType("");
      setColor("");
      setPlate(EMPTY_PLATE);
      loadVehicles();
    } catch (err) {
      setError(err.response?.data?.detail || "ثبت خودرو ناموفق بود.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const [vehicleToDelete, setVehicleToDelete] = useState(null);

  async function handleConfirmDelete() {
    if (!vehicleToDelete) return;
    setDeletingId(vehicleToDelete.id);
    try {
      await deleteMyVehicle(vehicleToDelete.id);
      setVehicles((prev) => prev.filter((v) => v.id !== vehicleToDelete.id));
      setVehicleToDelete(null);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <Box sx={{ maxWidth: { xs: "100%", md: 600 } }}>
      <Typography variant="h5" fontWeight={800} sx={{ mb: 2 }}>
        خودروهای من
      </Typography>

      <Card variant="outlined" sx={{ borderRadius: 2, p: 2.5, mb: 3 }}>
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2 }}>
          ثبت خودروی جدید
        </Typography>
        <Box component="form" onSubmit={handleSubmit}>
          <Stack spacing={2}>
            <TextField
              label="نوع/مدل خودرو"
              placeholder="مثلاً پراید ۱۳۱، ۲۰۶"
              value={vehicleType}
              onChange={(e) => setVehicleType(e.target.value)}
              fullWidth
              InputProps={{
                startAdornment: <DirectionsCarFilledOutlinedIcon fontSize="small" sx={{ mr: 1, color: "action.active" }} />,
              }}
            />
            <TextField
              label="رنگ خودرو"
              placeholder="مثلاً سفید، مشکی"
              value={color}
              onChange={(e) => setColor(e.target.value)}
              fullWidth
              InputProps={{
                startAdornment: <PaletteOutlinedIcon fontSize="small" sx={{ mr: 1, color: "action.active" }} />,
              }}
            />
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
                شماره پلاک
              </Typography>
              <IranianLicensePlateInput value={plate} onChange={setPlate} disabled={isSubmitting} />
            </Box>
            {error && <Alert severity="error">{error}</Alert>}
            <Button
              type="submit"
              variant="contained"
              startIcon={<AddOutlinedIcon />}
              disabled={!canSubmit}
              sx={{ alignSelf: "flex-start" }}
            >
              {isSubmitting ? "در حال ثبت..." : "ثبت خودرو"}
            </Button>
          </Stack>
        </Box>
      </Card>

      <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1.5 }}>
        خودروهای ثبت‌شده
      </Typography>
      {vehicles === null ? (
        <Typography variant="body2" color="text.secondary">
          در حال بارگذاری...
        </Typography>
      ) : vehicles.length === 0 ? (
        <Card variant="outlined" sx={{ p: 3, borderRadius: 2, textAlign: "center" }}>
          <Typography variant="body2" color="text.secondary">
            هنوز خودرویی ثبت نکرده‌اید.
          </Typography>
        </Card>
      ) : (
        <Stack spacing={1.5}>
          {vehicles.map((v) => (
            <Card
              key={v.id}
              variant="outlined"
              sx={{ borderRadius: 2, p: 2, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}
            >
              <Stack direction="row" spacing={2} alignItems="center" sx={{ minWidth: 0 }}>
                <PlateDisplay
                  digits1={v.plate_digits1}
                  letter={v.plate_letter}
                  digits2={v.plate_digits2}
                  iranCode={v.plate_iran_code}
                />
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="body2" fontWeight={700} noWrap>
                    {v.vehicle_type}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {v.color}
                  </Typography>
                </Box>
              </Stack>
              <IconButton
                size="small"
                color="error"
                disabled={deletingId === v.id}
                onClick={() => setVehicleToDelete(v)}
                aria-label="حذف خودرو"
              >
                <DeleteOutlineOutlinedIcon fontSize="small" />
              </IconButton>
            </Card>
          ))}
        </Stack>
      )}

      <Dialog open={Boolean(vehicleToDelete)} onClose={() => setVehicleToDelete(null)} maxWidth="xs" fullWidth>
        <DialogTitle>حذف خودرو</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            آیا از حذف این خودرو مطمئن هستید؟ این عمل قابل‌بازگشت نیست.
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
