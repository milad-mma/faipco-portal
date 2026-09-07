import { useEffect, useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import EmailOutlinedIcon from "@mui/icons-material/EmailOutlined";
import { fetchSites } from "../api/sites";
import { fetchEvaluationPeriods } from "../api/evaluationPeriods";
import {
  downloadPeriodComparison,
  downloadSitePeriodReport,
  emailPeriodComparison,
  emailSitePeriodReport,
  fetchPeriodComparison,
  fetchSitePeriodReport,
} from "../api/evaluationReports";

function scoreColor(score) {
  if (score == null) return "default";
  return score >= 70 ? "success" : score >= 50 ? "warning" : "error";
}

function EmailDialog({ open, onClose, onSend }) {
  const [email, setEmail] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  async function handleSend() {
    setError("");
    setIsSending(true);
    try {
      await onSend(email);
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.detail || "ارسال ایمیل با خطا مواجه شد.");
    } finally {
      setIsSending(false);
    }
  }

  function handleClose() {
    setSuccess(false);
    setEmail("");
    onClose();
  }

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="xs">
      <DialogTitle>ارسال گزارش به ایمیل</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        <TextField
          label="آدرس ایمیل"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={isSending}
        />
        {success && <Alert severity="success">ایمیل با موفقیت ارسال شد.</Alert>}
        {error && <Alert severity="error">{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>بستن</Button>
        <Button variant="contained" onClick={handleSend} disabled={isSending || !email}>
          {isSending ? "در حال ارسال..." : "ارسال"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function SinglePeriodReportTab({ siteId, periods }) {
  const [periodId, setPeriodId] = useState("");
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);

  useEffect(() => {
    setReport(null);
  }, [siteId]);

  async function handleLoad() {
    setError("");
    try {
      const data = await fetchSitePeriodReport(siteId, periodId);
      setReport(data);
    } catch (err) {
      setError(err.response?.data?.detail || "دریافت گزارش با خطا مواجه شد.");
    }
  }

  async function handleDownload() {
    try {
      await downloadSitePeriodReport(siteId, periodId);
    } catch (err) {
      setError(err.response?.data?.detail || "دانلود گزارش با خطا مواجه شد.");
    }
  }

  return (
    <Box>
      <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
        <TextField
          select
          size="small"
          label="دوره ارزیابی"
          value={periodId}
          onChange={(e) => setPeriodId(e.target.value)}
          sx={{ minWidth: 220 }}
        >
          {periods.map((p) => (
            <MenuItem key={p.id} value={p.id}>
              {p.title}
            </MenuItem>
          ))}
        </TextField>
        <Button variant="contained" onClick={handleLoad} disabled={!periodId}>
          نمایش گزارش
        </Button>
        {report && (
          <>
            <Button startIcon={<DownloadOutlinedIcon />} onClick={handleDownload}>
              دانلود اکسل
            </Button>
            <Button startIcon={<EmailOutlinedIcon />} onClick={() => setEmailDialogOpen(true)}>
              ارسال به ایمیل
            </Button>
          </>
        )}
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {report && (
        <Box>
          <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary">
              میانگین کل سایت:{" "}
              <b>{report.overall_average_score != null ? Math.round(report.overall_average_score) : "—"}</b>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              تعداد ارزیابی ثبت‌شده: <b>{report.overall_count}</b>
            </Typography>
          </Stack>

          {report.departments.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              هنوز هیچ ارزیابی ثبت‌نهایی‌شده‌ای برای این دوره وجود ندارد.
            </Typography>
          ) : (
            report.departments.map((dept) => (
              <Accordion key={dept.department_id} variant="outlined" disableGutters sx={{ mb: 1 }}>
                <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
                  <Stack direction="row" spacing={1.5} alignItems="center">
                    <Typography fontWeight={700}>{dept.department_name}</Typography>
                    <Chip
                      size="small"
                      color={scoreColor(dept.average_score)}
                      label={`میانگین: ${Math.round(dept.average_score)}`}
                    />
                    <Chip size="small" label={`${dept.count} نفر`} />
                  </Stack>
                </AccordionSummary>
                <AccordionDetails>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>نام</TableCell>
                          <TableCell>کد پرسنلی</TableCell>
                          <TableCell>امتیاز</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {dept.employees.map((emp) => (
                          <TableRow key={emp.personnel_code}>
                            <TableCell>
                              {emp.first_name} {emp.last_name}
                            </TableCell>
                            <TableCell>{emp.personnel_code}</TableCell>
                            <TableCell>
                              <Chip
                                size="small"
                                color={scoreColor(emp.score)}
                                label={emp.score != null ? Math.round(emp.score) : "—"}
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </AccordionDetails>
              </Accordion>
            ))
          )}
        </Box>
      )}

      <EmailDialog
        open={emailDialogOpen}
        onClose={() => setEmailDialogOpen(false)}
        onSend={(email) => emailSitePeriodReport(siteId, periodId, email)}
      />
    </Box>
  );
}

function ComparisonTab({ siteId, periods }) {
  const [periodIdA, setPeriodIdA] = useState("");
  const [periodIdB, setPeriodIdB] = useState("");
  const [comparison, setComparison] = useState(null);
  const [error, setError] = useState("");
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);

  useEffect(() => {
    setComparison(null);
  }, [siteId]);

  async function handleLoad() {
    setError("");
    try {
      const data = await fetchPeriodComparison(siteId, periodIdA, periodIdB);
      setComparison(data);
    } catch (err) {
      setError(err.response?.data?.detail || "دریافت مقایسه با خطا مواجه شد.");
    }
  }

  async function handleDownload() {
    try {
      await downloadPeriodComparison(siteId, periodIdA, periodIdB);
    } catch (err) {
      setError(err.response?.data?.detail || "دانلود مقایسه با خطا مواجه شد.");
    }
  }

  return (
    <Box>
      <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
        <TextField
          select
          size="small"
          label="دوره اول"
          value={periodIdA}
          onChange={(e) => setPeriodIdA(e.target.value)}
          sx={{ minWidth: 200 }}
        >
          {periods.map((p) => (
            <MenuItem key={p.id} value={p.id}>
              {p.title}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="دوره دوم"
          value={periodIdB}
          onChange={(e) => setPeriodIdB(e.target.value)}
          sx={{ minWidth: 200 }}
        >
          {periods.map((p) => (
            <MenuItem key={p.id} value={p.id}>
              {p.title}
            </MenuItem>
          ))}
        </TextField>
        <Button variant="contained" onClick={handleLoad} disabled={!periodIdA || !periodIdB}>
          مقایسه کن
        </Button>
        {comparison && (
          <>
            <Button startIcon={<DownloadOutlinedIcon />} onClick={handleDownload}>
              دانلود اکسل
            </Button>
            <Button startIcon={<EmailOutlinedIcon />} onClick={() => setEmailDialogOpen(true)}>
              ارسال به ایمیل
            </Button>
          </>
        )}
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {comparison && (
        <Box>
          <Stack direction="row" spacing={3} sx={{ mb: 2 }}>
            <Typography variant="body2">
              {comparison.period_a.title}:{" "}
              <b>{comparison.period_a.average_score != null ? Math.round(comparison.period_a.average_score) : "—"}</b>
            </Typography>
            <Typography variant="body2">
              {comparison.period_b.title}:{" "}
              <b>{comparison.period_b.average_score != null ? Math.round(comparison.period_b.average_score) : "—"}</b>
            </Typography>
          </Stack>

          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>واحد</TableCell>
                  <TableCell>{comparison.period_a.title}</TableCell>
                  <TableCell>{comparison.period_b.title}</TableCell>
                  <TableCell>تغییر</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {comparison.departments.map((dept) => {
                  const change =
                    dept.period_a_average != null && dept.period_b_average != null
                      ? Math.round(dept.period_b_average - dept.period_a_average)
                      : null;
                  return (
                    <TableRow key={dept.department_id}>
                      <TableCell>{dept.department_name}</TableCell>
                      <TableCell>{dept.period_a_average != null ? Math.round(dept.period_a_average) : "—"}</TableCell>
                      <TableCell>{dept.period_b_average != null ? Math.round(dept.period_b_average) : "—"}</TableCell>
                      <TableCell>
                        {change != null && (
                          <Chip
                            size="small"
                            color={change > 0 ? "success" : change < 0 ? "error" : "default"}
                            label={`${change > 0 ? "+" : ""}${change}`}
                          />
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      <EmailDialog
        open={emailDialogOpen}
        onClose={() => setEmailDialogOpen(false)}
        onSend={(email) => emailPeriodComparison(siteId, periodIdA, periodIdB, email)}
      />
    </Box>
  );
}

export default function EvaluationReportsPage() {
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState("");
  const [periods, setPeriods] = useState([]);
  const [tab, setTab] = useState(0);

  useEffect(() => {
    fetchSites().then((data) => {
      setSites(data);
      if (data.length > 0) setSiteId(data[0].id);
    });
  }, []);

  useEffect(() => {
    if (!siteId) return;
    fetchEvaluationPeriods(siteId).then(setPeriods);
  }, [siteId]);

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        گزارش‌های مدیریتی ارزیابی عملکرد
      </Typography>

      <TextField
        select
        label="سایت"
        value={siteId}
        onChange={(e) => setSiteId(e.target.value)}
        sx={{ minWidth: 240, mb: 2 }}
      >
        {sites.map((site) => (
          <MenuItem key={site.id} value={site.id}>
            {site.name}
          </MenuItem>
        ))}
      </TextField>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label="گزارش یک دوره" />
        <Tab label="مقایسه دوره‌ها" />
      </Tabs>

      {siteId && tab === 0 && <SinglePeriodReportTab siteId={siteId} periods={periods} />}
      {siteId && tab === 1 && <ComparisonTab siteId={siteId} periods={periods} />}
    </Box>
  );
}
