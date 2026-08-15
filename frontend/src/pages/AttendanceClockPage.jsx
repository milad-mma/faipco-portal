import { useEffect, useState } from "react";
import { Alert, Box, Button, Card, Chip, CircularProgress, Divider, Stack, Typography } from "@mui/material";
import LoginOutlinedIcon from "@mui/icons-material/LoginOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import { clockIn, clockOut, fetchMyAttendanceLogs } from "../api/attendance";
import { getCurrentPosition } from "../utils/geolocation";
import JalaliMonthYearFilter from "../components/JalaliMonthYearFilter";
import { groupLogsByDay } from "../utils/attendanceGrouping";
import { monoFontSx } from "../theme";

export default function AttendanceClockPage() {
  const [logs, setLogs] = useState(null);
  const [period, setPeriod] = useState({ year: null, month: null }); // null یعنی هنوز از سرور نگرفتیم (ماه جاری پیش‌فرض)
  const [isWorking, setIsWorking] = useState(false); // در حال گرفتن موقعیت + ارسال
  const [result, setResult] = useState(null);

  function loadLogs(overridePeriod) {
    const params = overridePeriod || period;
    fetchMyAttendanceLogs({ year: params.year, month: params.month }).then((data) => {
      setLogs(data.items);
      setPeriod({ year: data.year, month: data.month });
    });
  }

  useEffect(() => {
    loadLogs({ year: null, month: null }); // اولین بار: بدون فیلتر -> سرور خودش ماه جاری را برمی‌گرداند
  }, []);

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
      loadLogs();
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

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
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

      <Card variant="outlined" sx={{ borderRadius: 3 }}>
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          flexWrap="wrap"
          rowGap={1.5}
          sx={{ p: 2.5, pb: 1.5 }}
        >
          <Typography variant="subtitle2" fontWeight={700}>
            تاریخچه من
          </Typography>
          <JalaliMonthYearFilter
            year={period.year}
            month={period.month}
            onChange={(next) => loadLogs(next)}
            disabled={logs === null}
          />
        </Stack>
        {logs === null ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
            <CircularProgress size={24} />
          </Box>
        ) : logs.length === 0 ? (
          <Box sx={{ px: 2.5, pb: 3 }}>
            <Typography variant="body2" color="text.secondary">
              برای این ماه هیچ ثبتی ندارید.
            </Typography>
          </Box>
        ) : (
          groupLogsByDay(logs).map((row, index) => (
            <Box key={row.key}>
              {index > 0 && <Divider />}
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 2.5, py: 1.5 }} flexWrap="wrap" rowGap={1}>
                <Typography variant="body2" sx={monoFontSx}>
                  {row.dateLabel}
                </Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap justifyContent="flex-end">
                  {row.sessions.map((session, sessionIndex) => (
                    <Stack key={sessionIndex} direction="row" spacing={0.5}>
                      {session.checkIn ? (
                        <Chip
                          size="small"
                          color="success"
                          icon={<LoginOutlinedIcon fontSize="small" />}
                          label={new Date(session.checkIn.created_at).toLocaleTimeString("fa-IR", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        />
                      ) : (
                        <Chip size="small" variant="outlined" label="بدون ورود" />
                      )}
                      {session.checkOut ? (
                        <Chip
                          size="small"
                          icon={<LogoutOutlinedIcon fontSize="small" />}
                          label={new Date(session.checkOut.created_at).toLocaleTimeString("fa-IR", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        />
                      ) : (
                        <Chip size="small" variant="outlined" label="بدون خروج" />
                      )}
                    </Stack>
                  ))}
                </Stack>
              </Stack>
            </Box>
          ))
        )}
      </Card>
    </Box>
  );
}
