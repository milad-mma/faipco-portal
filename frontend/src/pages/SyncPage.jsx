import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  MenuItem,
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
import SyncOutlinedIcon from "@mui/icons-material/SyncOutlined";
import WifiTetheringOutlinedIcon from "@mui/icons-material/WifiTetheringOutlined";
import { fetchSites } from "../api/sites";
import { fetchSyncLogs, runSiteSync, testSiteConnection } from "../api/sync";
import SyncStatusChip from "../components/SyncStatusChip";
import { monoFontSx } from "../theme";

export default function SyncPage() {
  const [sites, setSites] = useState([]);
  const [selectedSiteId, setSelectedSiteId] = useState("");
  const [logs, setLogs] = useState([]);
  const [testResult, setTestResult] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    fetchSites().then((data) => {
      setSites(data);
      if (data.length > 0) setSelectedSiteId(data[0].id);
    });
  }, []);

  useEffect(() => {
    if (!selectedSiteId) return;
    setTestResult(null);
    loadLogs();
  }, [selectedSiteId]);

  function loadLogs() {
    if (!selectedSiteId) return;
    fetchSyncLogs(selectedSiteId).then(setLogs);
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

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        مدیریت Sync
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        تست اتصال، اجرای دستی همگام‌سازی و مشاهده تاریخچه هر سایت
      </Typography>

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
