import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  FormControlLabel,
  MenuItem,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import SyncOutlinedIcon from "@mui/icons-material/SyncOutlined";
import WifiTetheringOutlinedIcon from "@mui/icons-material/WifiTetheringOutlined";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import PowerSettingsNewOutlinedIcon from "@mui/icons-material/PowerSettingsNewOutlined";
import { fetchSiteConnection, fetchSites, setSiteConnectionActive } from "../api/sites";
import { fetchSyncLogs, fetchSyncSettings, runSiteSync, testSiteConnection, updateSyncSettings } from "../api/sync";
import SyncStatusChip from "../components/SyncStatusChip";
import { monoFontSx } from "../theme";

export default function SyncPage() {
  const [sites, setSites] = useState([]);
  const [selectedSiteId, setSelectedSiteId] = useState("");
  const [logs, setLogs] = useState([]);
  const [testResult, setTestResult] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  const [intervalMinutes, setIntervalMinutes] = useState("");
  const [savedIntervalMinutes, setSavedIntervalMinutes] = useState(null);
  const [isSavingInterval, setIsSavingInterval] = useState(false);
  const [intervalMessage, setIntervalMessage] = useState(null);

  const [connectionStatus, setConnectionStatus] = useState(null); // SiteConnectionOut | null
  const [isTogglingSync, setIsTogglingSync] = useState(false);

  useEffect(() => {
    fetchSites().then((data) => {
      setSites(data);
      if (data.length > 0) setSelectedSiteId(data[0].id);
    });
    fetchSyncSettings().then((data) => {
      setIntervalMinutes(String(data.interval_minutes));
      setSavedIntervalMinutes(data.interval_minutes);
    });
  }, []);

  useEffect(() => {
    if (!selectedSiteId) return;
    setTestResult(null);
    loadLogs();
    fetchSiteConnection(selectedSiteId)
      .then(setConnectionStatus)
      .catch(() => setConnectionStatus(null));
  }, [selectedSiteId]);

  function loadLogs() {
    if (!selectedSiteId) return;
    fetchSyncLogs(selectedSiteId).then(setLogs);
  }

  async function handleToggleSyncEnabled() {
    if (!connectionStatus) return;
    const nextActive = !connectionStatus.is_active;
    setIsTogglingSync(true);
    try {
      const updated = await setSiteConnectionActive(selectedSiteId, nextActive);
      setConnectionStatus(updated);
    } finally {
      setIsTogglingSync(false);
    }
  }

  async function handleTestConnection() {
    setIsTesting(true);
    setTestResult(null);
    try {
      const result = await testSiteConnection(selectedSiteId);
      setTestResult(result);
    } finally {
      setIsTesting(false);
    }
  }

  async function handleRunSync() {
    setIsRunning(true);
    try {
      await runSiteSync(selectedSiteId);
      loadLogs();
    } finally {
      setIsRunning(false);
    }
  }

  async function handleSaveInterval() {
    setIntervalMessage(null);
    const value = Number(intervalMinutes);
    if (!Number.isInteger(value) || value < 1 || value > 1440) {
      setIntervalMessage({ severity: "error", text: "فاصله زمانی باید عددی صحیح بین ۱ تا ۱۴۴۰ دقیقه باشد." });
      return;
    }
    setIsSavingInterval(true);
    try {
      const result = await updateSyncSettings(value);
      setSavedIntervalMinutes(result.interval_minutes);
      setIntervalMessage({ severity: "success", text: "فاصله زمانی Sync خودکار ذخیره شد و بلافاصله اعمال شد." });
    } catch (err) {
      setIntervalMessage({
        severity: "error",
        text: err.response?.data?.detail || "ذخیره فاصله زمانی ناموفق بود.",
      });
    } finally {
      setIsSavingInterval(false);
    }
  }

  const intervalChanged = savedIntervalMinutes !== null && Number(intervalMinutes) !== savedIntervalMinutes;

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        همگام‌سازی دیتابیس
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        تست اتصال، اجرای دستی همگام‌سازی و مشاهده تاریخچه هر سایت
      </Typography>

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
          <SettingsOutlinedIcon fontSize="small" color="action" />
          <Typography variant="subtitle1" fontWeight={700}>
            فاصله زمانی Sync خودکار
          </Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          هر چند دقیقه یک‌بار، پرسنل همه سایت‌های فعال به‌صورت خودکار همگام‌سازی شوند.
          تغییر این مقدار فوراً اعمال می‌شود — نیازی به Restart سرور نیست.
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
          <TextField
            type="number"
            label="فاصله زمانی (دقیقه)"
            value={intervalMinutes}
            onChange={(e) => {
              setIntervalMessage(null);
              setIntervalMinutes(e.target.value);
            }}
            inputProps={{ min: 1, max: 1440, step: 1 }}
            sx={{ maxWidth: 220 }}
            disabled={savedIntervalMinutes === null}
          />
          <Button
            variant="contained"
            onClick={handleSaveInterval}
            disabled={isSavingInterval || savedIntervalMinutes === null || !intervalChanged}
          >
            {isSavingInterval ? "در حال ذخیره..." : "ذخیره"}
          </Button>
        </Stack>
        {intervalMessage && (
          <Alert severity={intervalMessage.severity} sx={{ mt: 2 }}>
            {intervalMessage.text}
          </Alert>
        )}
      </Card>

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
          <TextField
            select
            label="انتخاب سایت"
            value={selectedSiteId}
            onChange={(e) => setSelectedSiteId(e.target.value)}
            sx={{ minWidth: 240 }}
          >
            {sites.map((site) => (
              <MenuItem key={site.id} value={site.id}>
                {site.name}
              </MenuItem>
            ))}
          </TextField>

          <Button
            variant="outlined"
            startIcon={<WifiTetheringOutlinedIcon />}
            onClick={handleTestConnection}
            disabled={!selectedSiteId || isTesting}
          >
            {isTesting ? "در حال تست..." : "تست اتصال"}
          </Button>

          <Button
            variant="contained"
            startIcon={<SyncOutlinedIcon />}
            onClick={handleRunSync}
            disabled={!selectedSiteId || isRunning}
          >
            {isRunning ? "در حال اجرا..." : "اجرای دستی Sync"}
          </Button>
        </Stack>

        {connectionStatus && (
          <Stack
            direction="row"
            spacing={1.5}
            alignItems="center"
            sx={{ mt: 2.5, pt: 2, borderTop: "1px solid", borderColor: "divider" }}
          >
            <PowerSettingsNewOutlinedIcon fontSize="small" color={connectionStatus.is_active ? "success" : "disabled"} />
            <FormControlLabel
              sx={{ flexGrow: 1, mr: 0 }}
              control={
                <Switch
                  checked={connectionStatus.is_active}
                  disabled={isTogglingSync}
                  onChange={handleToggleSyncEnabled}
                />
              }
              label={
                <Box>
                  <Typography variant="body2" fontWeight={600}>
                    همگام‌سازی خودکار این سایت {connectionStatus.is_active ? "روشن" : "خاموش"} است
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    با خاموش‌کردن، این سایت دیگر در چرخه Sync خودکار دوره‌ای شرکت نمی‌کند —
                    ولی اتصال دیتابیس قطع نمی‌شود و همچنان می‌توانید از همین صفحه به‌صورت
                    دستی Sync را اجرا کنید.
                  </Typography>
                </Box>
              }
            />
          </Stack>
        )}
        {!connectionStatus && selectedSiteId && (
          <Alert severity="info" sx={{ mt: 2.5 }}>
            برای این سایت هنوز اتصال دیتابیسی از صفحه «سایت‌ها» تعریف نشده است.
          </Alert>
        )}

        {testResult && (
          <Alert severity={testResult.success ? "success" : "error"} sx={{ mt: 2 }}>
            {testResult.success ? "اتصال با موفقیت برقرار شد." : testResult.message}
          </Alert>
        )}
      </Card>

      <Card variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>شروع</TableCell>
                <TableCell>پایان</TableCell>
                <TableCell>وضعیت</TableCell>
                <TableCell>افزوده‌شده</TableCell>
                <TableCell>به‌روزشده</TableCell>
                <TableCell>غیرفعال‌شده</TableCell>
                <TableCell>خطا</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {logs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7}>
                    <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
                      هنوز هیچ اجرایی برای این سایت ثبت نشده است.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {logs.map((log) => (
                <TableRow key={log.id} hover>
                  <TableCell sx={monoFontSx}>{new Date(log.started_at).toLocaleString("fa-IR")}</TableCell>
                  <TableCell sx={monoFontSx}>
                    {log.finished_at ? new Date(log.finished_at).toLocaleString("fa-IR") : "—"}
                  </TableCell>
                  <TableCell>
                    <SyncStatusChip status={log.status} />
                  </TableCell>
                  <TableCell sx={monoFontSx}>{log.inserted_count}</TableCell>
                  <TableCell sx={monoFontSx}>{log.updated_count}</TableCell>
                  <TableCell sx={monoFontSx}>{log.deactivated_count}</TableCell>
                  <TableCell sx={{ maxWidth: 240 }}>
                    <Typography variant="caption" color="error.main" noWrap>
                      {log.error_message || "—"}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>
    </Box>
  );
}
