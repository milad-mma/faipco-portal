import { useState } from "react";
import { Alert, Box, Button, Card, CircularProgress, Stack, Typography } from "@mui/material";
import LoginOutlinedIcon from "@mui/icons-material/LoginOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import { clockIn, clockOut } from "../api/attendance";
import { getCurrentPosition } from "../utils/geolocation";

export default function AttendanceClockPage() {
  const [isWorking, setIsWorking] = useState(false); // در حال گرفتن موقعیت + ارسال
  const [result, setResult] = useState(null);

  async function handleClock(action) {
    setResult(null);
    setIsWorking(true);
    try {
      const position = await getCurrentPosition();
      const fn = action === "in" ? clockIn : clockOut;
      await fn({
        latitude: position.latitude,
        longitude: position.longitude,
        accuracyMeters: position.accuracyMeters,
      });
      setResult({ success: true, message: action === "in" ? "ورود شما ثبت شد." : "خروج شما ثبت شد." });
    } catch (err) {
      setResult({
        success: false,
        message: err.response?.data?.detail || err.message || "ثبت ناموفق بود.",
      });
    } finally {
      setIsWorking(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        ثبت ورود و خروج
      </Typography>

      <Alert severity="warning" icon={<ScienceOutlinedIcon />} sx={{ mb: 3 }}>
        <strong>این قابلیت آزمایشی است.</strong> ثبت ورود/خروج رسمی همچنان باید از طریق دستگاه‌های
        تعبیه‌شده در کارخانه انجام شود — این فقط یک ثبت مکمل و آزمایشی مبتنی بر موقعیت GPS گوشی شماست
        و جایگزین سامانه رسمی حضور و غیاب نیست.
      </Alert>

      {result && (
        <Alert severity={result.success ? "success" : "error"} sx={{ mb: 3 }}>
          {result.message}
        </Alert>
      )}

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          با زدن هرکدام از دکمه‌های زیر، موقعیت فعلی گوشی شما گرفته و بررسی می‌شود که داخل محدوده
          مجاز کارخانه باشد. اگر خارج از محدوده باشید، ثبت انجام نمی‌شود.
        </Typography>
        <Stack direction="row" spacing={2}>
          <Button
            fullWidth
            variant="contained"
            color="success"
            size="large"
            startIcon={isWorking ? <CircularProgress size={18} color="inherit" /> : <LoginOutlinedIcon />}
            onClick={() => handleClock("in")}
            disabled={isWorking}
          >
            ثبت ورود
          </Button>
          <Button
            fullWidth
            variant="outlined"
            size="large"
            startIcon={isWorking ? <CircularProgress size={18} /> : <LogoutOutlinedIcon />}
            onClick={() => handleClock("out")}
            disabled={isWorking}
          >
            ثبت خروج
          </Button>
        </Stack>
      </Card>
    </Box>
  );
}
