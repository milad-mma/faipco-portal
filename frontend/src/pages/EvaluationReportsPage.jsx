import { useEffect, useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
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
  fetchEvaluationAnswersForReport,
  fetchPeriodComparison,
  fetchSitePeriodReport,
} from "../api/evaluationReports";

function scoreColor(score) {
  if (score == null) return "default";
  return score >= 70 ? "success" : score >= 50 ? "warning" : "error";
}

// ⚠️ نمایش پاسخ ارزیاب به هر سوال - بسته به نوع سوال، مقدار در فیلد
// متفاوتی ذخیره شده (همان ساختار EvaluationAnswer در بک‌اند).
function formatAnswerValue(answer) {
  if (answer.text_value) return answer.text_value;
  if (answer.number_value != null) return String(answer.number_value);
  if (answer.date_value) return new Date(answer.date_value).toLocaleDateString("fa-IR");
  if (answer.selected_option_ids?.length) return `${answer.selected_option_ids.length} گزینه انتخاب شده`;
  return "—";
}

/**
 * ⚠️ طبق درخواست صریح کاربر: جزئیات سوال‌به‌سوال هر شخص در گزارش‌های
 * مدیریتی (هم «گزارش یک دوره»، هم «مقایسه دوره‌ها»).
 *
 * برخلاف نسخه‌ی پرسنلی (MyPerformancePage) که عمداً نظر ارزیاب را
 * نشان نمی‌دهد، اینجا امتیاز + متن کامل پاسخ + نظر ارزیاب هم نمایش
 * داده می‌شود - طبق تصمیم صریح کاربر برای گزارش‌گیری مدیریتی.
 */
/**
 * ⚠️ امتیاز یک دوره برای یک پرسنل - اگر آن دوره ارزیابی ثبت‌شده داشته
 * باشد، کلیک‌پذیر است و جزئیات سوال‌به‌سوال همان دوره را باز می‌کند؛
 * وگرنه فقط یک خط تیره ساده (بدون رفتار کلیک گمراه‌کننده).
 */
function ScoreCell({ score, evaluationId, onClick }) {
  if (score == null) return <Typography variant="body2">—</Typography>;
  return (
    <Chip
      size="small"
      color={scoreColor(score)}
      label={Math.round(score)}
      onClick={evaluationId ? onClick : undefined}
      sx={{ cursor: evaluationId ? "pointer" : "default" }}
    />
  );
}

function EmployeeAnswersDialog({ siteId, employee, onClose }) {
  const [answers, setAnswers] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!employee?.evaluation_id) {
      setAnswers([]);
      return;
    }
    fetchEvaluationAnswersForReport(siteId, employee.evaluation_id)
      .then(setAnswers)
      .catch((err) => {
        setError(err.response?.data?.detail || "دریافت جزئیات با خطا مواجه شد.");
        setAnswers([]);
      });
  }, [siteId, employee?.evaluation_id]);

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>
        <Typography fontWeight={700}>
          {employee.first_name} {employee.last_name}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          کد پرسنلی: {employee.personnel_code} — امتیاز کل:{" "}
          {employee.score != null ? Math.round(employee.score) : "—"}
        </Typography>
      </DialogTitle>
      <DialogContent dividers>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        {answers === null ? (
          <Stack alignItems="center" sx={{ py: 3 }}>
            <CircularProgress size={28} />
          </Stack>
        ) : answers.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            جزئیاتی برای این ارزیابی ثبت نشده است.
          </Typography>
        ) : (
          <Stack divider={<Divider flexItem />} spacing={1.5}>
            {answers.map((answer) => (
              <Box key={answer.id}>
                <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={2}>
                  <Typography variant="body2" fontWeight={700} sx={{ flex: 1 }}>
                    {answer.question_text_snapshot}
                  </Typography>
                  {answer.score != null && (
                    <Chip size="small" label={`${Math.round(answer.score)}`} color={scoreColor(answer.score)} />
                  )}
                </Stack>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  پاسخ: {formatAnswerValue(answer)}
                </Typography>
                {answer.comment && (
                  <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: "block" }}>
                    نظر ارزیاب: {answer.comment}
                  </Typography>
                )}
              </Box>
            ))}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
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
  const [detailsEmployee, setDetailsEmployee] = useState(null);

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
                          <TableRow
                            key={emp.personnel_code}
                            hover
                            onClick={() => emp.evaluation_id && setDetailsEmployee(emp)}
                            sx={{ cursor: emp.evaluation_id ? "pointer" : "default" }}
                          >
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

      {detailsEmployee && (
        <EmployeeAnswersDialog
          siteId={siteId}
          employee={detailsEmployee}
          onClose={() => setDetailsEmployee(null)}
        />
      )}
    </Box>
  );
}

function ComparisonTab({ siteId, periods }) {
  const [periodIdA, setPeriodIdA] = useState("");
  const [periodIdB, setPeriodIdB] = useState("");
  const [comparison, setComparison] = useState(null);
  const [error, setError] = useState("");
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);
  const [detailsEmployee, setDetailsEmployee] = useState(null);

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

          {/* ⚠️ طبق درخواست صریح کاربر: زیر هر واحد، لیست پرسنل با امتیاز
              هر دو دوره و میزان تغییر - با کلیک روی هر ردیف، جزئیات
              سوال‌به‌سوال همان دوره باز می‌شود. */}
          {comparison.departments.map((dept) => {
            const deptChange =
              dept.period_a_average != null && dept.period_b_average != null
                ? Math.round(dept.period_b_average - dept.period_a_average)
                : null;
            return (
              <Accordion key={dept.department_id} variant="outlined" disableGutters sx={{ mb: 1 }}>
                <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
                  <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
                    <Typography fontWeight={700}>{dept.department_name}</Typography>
                    <Chip
                      size="small"
                      label={`${comparison.period_a.title}: ${
                        dept.period_a_average != null ? Math.round(dept.period_a_average) : "—"
                      }`}
                    />
                    <Chip
                      size="small"
                      label={`${comparison.period_b.title}: ${
                        dept.period_b_average != null ? Math.round(dept.period_b_average) : "—"
                      }`}
                    />
                    {deptChange != null && (
                      <Chip
                        size="small"
                        color={deptChange > 0 ? "success" : deptChange < 0 ? "error" : "default"}
                        label={`${deptChange > 0 ? "+" : ""}${deptChange}`}
                      />
                    )}
                  </Stack>
                </AccordionSummary>
                <AccordionDetails>
                  {dept.employees?.length ? (
                    <TableContainer>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>نام</TableCell>
                            <TableCell>کد پرسنلی</TableCell>
                            <TableCell>{comparison.period_a.title}</TableCell>
                            <TableCell>{comparison.period_b.title}</TableCell>
                            <TableCell>تغییر</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {dept.employees.map((emp) => {
                            const empChange =
                              emp.period_a_score != null && emp.period_b_score != null
                                ? Math.round(emp.period_b_score - emp.period_a_score)
                                : null;
                            return (
                              <TableRow key={emp.personnel_code}>
                                <TableCell>
                                  {emp.first_name} {emp.last_name}
                                </TableCell>
                                <TableCell>{emp.personnel_code}</TableCell>
                                <TableCell>
                                  <ScoreCell
                                    score={emp.period_a_score}
                                    evaluationId={emp.period_a_evaluation_id}
                                    onClick={() =>
                                      setDetailsEmployee({
                                        first_name: emp.first_name,
                                        last_name: emp.last_name,
                                        personnel_code: emp.personnel_code,
                                        score: emp.period_a_score,
                                        evaluation_id: emp.period_a_evaluation_id,
                                      })
                                    }
                                  />
                                </TableCell>
                                <TableCell>
                                  <ScoreCell
                                    score={emp.period_b_score}
                                    evaluationId={emp.period_b_evaluation_id}
                                    onClick={() =>
                                      setDetailsEmployee({
                                        first_name: emp.first_name,
                                        last_name: emp.last_name,
                                        personnel_code: emp.personnel_code,
                                        score: emp.period_b_score,
                                        evaluation_id: emp.period_b_evaluation_id,
                                      })
                                    }
                                  />
                                </TableCell>
                                <TableCell>
                                  {empChange != null && (
                                    <Chip
                                      size="small"
                                      color={empChange > 0 ? "success" : empChange < 0 ? "error" : "default"}
                                      label={`${empChange > 0 ? "+" : ""}${empChange}`}
                                    />
                                  )}
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      هیچ ارزیابی ثبت‌نهایی‌شده‌ای برای این واحد در این دو دوره وجود ندارد.
                    </Typography>
                  )}
                </AccordionDetails>
              </Accordion>
            );
          })}
        </Box>
      )}

      <EmailDialog
        open={emailDialogOpen}
        onClose={() => setEmailDialogOpen(false)}
        onSend={(email) => emailPeriodComparison(siteId, periodIdA, periodIdB, email)}
      />

      {detailsEmployee && (
        <EmployeeAnswersDialog
          siteId={siteId}
          employee={detailsEmployee}
          onClose={() => setDetailsEmployee(null)}
        />
      )}
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
