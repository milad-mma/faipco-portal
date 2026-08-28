import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
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
import HistoryOutlinedIcon from "@mui/icons-material/HistoryOutlined";
import PowerSettingsNewOutlinedIcon from "@mui/icons-material/PowerSettingsNewOutlined";
import { fetchSiteConnection, fetchSites, setSiteConnectionActive } from "../api/sites";
import { fetchSyncLogs, fetchSyncSettings, runSiteSync, testSiteConnection, updateSyncSettings } from "../api/sync";
import SyncStatusChip from "../components/SyncStatusChip";
import { monoFontSx } from "../theme";
import { useAuth } from "../context/AuthContext";

export default function SyncPage() {
  const { user } = useAuth();
  // ⚠️ برخلاف اکثر مجوزهای دیگر پروژه، sync.manage به‌طور خودکار شامل
  // sync.view/sync.run نمی‌شود — این سه، سه Permission کاملاً مستقل‌اند
  // (خودِ Backend هم دقیقاً همین‌طور، سه require_permission جدا دارد).
  // پس هرکدام از دکمه‌ها/بخش‌های این صفحه دقیقاً بر همان مجوز خاص خودش
  // نمایش داده می‌شود، نه یک فرض کلی «manage یعنی همه‌کاره».
  const canManageSync = Boolean(user?.can_manage_sync);
  const canViewSync = Boolean(user?.can_view_sync);
  const canRunSync = Boolean(user?.can_run_sync);
  const [sites, setSites] = useState([]);
  const [selectedSiteId, setSelectedSiteId] = useState("");
  const [logs, setLogs] = useState([]);
  const [testResult, setTestResult] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  const [intervalMinutes, setIntervalMinutes] = useState("");
  const [savedIntervalMinutes, setSavedIntervalMinutes] = useState(null);
  const [lastAutoSyncAt, setLastAutoSyncAt] = useState(null);
  const [isSavingInterval, setIsSavingInterval] = useState(false);
  const [intervalMessage, setIntervalMessage] = useState(null);

  const [connectionStatus, setConnectionStatus] = useState(null); // SiteConnectionOut | null
  const [isTogglingSync, setIsTogglingSync] = useState(false);

  useEffect(() => {
    fetchSites().then((data) => {
      setSites(data);
      if (data.length > 0) setSelectedSiteId(data[0].id);
    });
    // fetchSyncSettings مستلزم sync.manage است — بدون این مجوز، این
    // درخواست همیشه ۴۰۳ می‌گرفت (حتی اگر خودِ کارت تنظیمات فاصله زمانی
    // پایین‌تر اصلاً برای این کاربر نمایش داده نمی‌شد).
    if (canManageSync) {
      fetchSyncSettings().then((data) => {
        setIntervalMinutes(String(data.interval_minutes));
        setSavedIntervalMinutes(data.interval_minutes);
        setLastAutoSyncAt(data.last_auto_sync_at);
      });
    }
  }, [canManageSync]);

  useEffect(() => {
    if (!selectedSiteId) return;
    setTestResult(null);
    loadLogs();
    fetchSiteConnection(selectedSiteId)
      .then(setConnectionStatus)
      .catch(() => setConnectionStatus(null));
  }, [selectedSiteId]);

  function loadLogs() {
    if (!selectedSiteId || !canViewSync) return;
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
      setIntervalMessage({
        severity: "success",
        text: "فاصله زمانی ذخیره شد — حداکثر تا ۱ دقیقه دیگر روی سیستم اعمال می‌شود.",
      });
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

  const intervalPresets = [
    { label: "۱۵ دقیقه", value: 15 },
    { label: "۳۰ دقیقه", value: 30 },
    { label: "۱ ساعت", value: 60 },
    { label: "۳ ساعت", value: 180 },
    { label: "۶ ساعت", value: 360 },
    { label: "۱۲ ساعت", value: 720 },
    { label: "۱ شبانه‌روز", value: 1440 },
  ];

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        همگام‌سازی دیتابیس
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        تست اتصال، اجرای دستی همگام‌سازی و مشاهده تاریخچه هر سایت
      </Typography>

      {canManageSync && (
      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
          <SettingsOutlinedIcon fontSize="small" color="action" />
          <Typography variant="subtitle1" fontWeight={700}>
            فاصله زمانی Sync خودکار
          </Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          هر چند دقیقه یک‌بار، پرسنل همه سایت‌های فعال به‌صورت خودکار همگام‌سازی شوند. سیستم هر
          دقیقه یک‌بار چک می‌کند که آیا وقتش رسیده — یعنی زمان واقعی اجرا حداکثر تا ۱ دقیقه با این
          مقدار فاصله دارد، نه دقیقاً لحظه‌به‌لحظه.
        </Typography>

        <Stack direction="row" spacing={1} flexWrap="wrap" rowGap={1} sx={{ mb: 2 }}>
          {intervalPresets.map((preset) => (
            <Chip
              key={preset.value}
              label={preset.label}
              size="small"
              variant={Number(intervalMinutes) === preset.value ? "filled" : "outlined"}
              color={Number(intervalMinutes) === preset.value ? "primary" : "default"}
              clickable
              onClick={() => {
                setIntervalMessage(null);
                setIntervalMinutes(String(preset.value));
              }}
            />
          ))}
        </Stack>

        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
          <TextField
            type="number"
            label="فاصله زمانی دلخواه (دقیقه)"
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

        <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 2.5, opacity: 0.8 }}>
          <HistoryOutlinedIcon sx={{ fontSize: 18 }} color="action" />
          <Typography variant="caption" color="text.secondary">
            آخرین Sync خودکار:{" "}
            <span style={monoFontSx}>
              {lastAutoSyncAt ? new Date(lastAutoSyncAt).toLocaleString("fa-IR") : "هنوز اجرا نشده"}
            </span>
          </Typography>
        </Stack>

        {intervalMessage && (
          <Alert severity={intervalMessage.severity} sx={{ mt: 2 }}>
            {intervalMessage.text}
          </Alert>
        )}
      </Card>
      )}

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

          {canViewSync && (
            <Button
              variant="outlined"
              startIcon={<WifiTetheringOutlinedIcon />}
              onClick={handleTestConnection}
              disabled={!selectedSiteId || isTesting}
            >
              {isTesting ? "در حال تست..." : "تست اتصال"}
            </Button>
          )}

          {canRunSync && (
            <Button
              variant="contained"
              startIcon={<SyncOutlinedIcon />}
              onClick={handleRunSync}
              disabled={!selectedSiteId || isRunning}
            >
              {isRunning ? "در حال اجرا..." : "اجرای دستی Sync"}
            </Button>
          )}
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
                  disabled={isTogglingSync || !canManageSync}
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

      {canViewSync && (
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
                <TableCell>رد‌شده (غیرفعال در منبع)</TableCell>
                <TableCell>خطا</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {logs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8}>
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
                  <TableCell sx={monoFontSx}>{log.skipped_inactive_count ?? 0}</TableCell>
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
      )}
    </Box>
  );
}
