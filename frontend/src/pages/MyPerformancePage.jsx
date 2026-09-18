import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
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
  TablePagination,
  TableRow,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import {
  fetchMyEvaluationResultAnswers,
  fetchMyEvaluationResults,
  fetchMyEvaluations,
  fetchMyShiftLeadEvaluations,
  fetchMyYearlyAverage,
  reopenEvaluation,
} from "../api/evaluationProcess";
import BackLink from "../components/BackLink";
import AccessGateDialog from "../components/AccessGateDialog";
import { fetchMyAccessGateStatus } from "../api/accessGate";

const STATUS_LABELS = { not_started: "شروع‌نشده", draft: "پیش‌نویس", submitted: "ثبت‌شده" };
const STATUS_COLORS = { not_started: "default", draft: "warning", submitted: "success" };

function scoreColor(score) {
  if (score == null) return "default";
  return score >= 70 ? "success" : score >= 50 ? "warning" : "error";
}

function YearlyAverageCard({ yearlyAverage }) {
  if (!yearlyAverage || yearlyAverage.count === 0) return null;
  return (
    <Card variant="outlined" sx={{ p: 2, mb: 2, backgroundColor: "action.hover" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Box>
          <Typography variant="body2" color="text.secondary">
            میانگین امتیاز من در سال {yearlyAverage.jalali_year}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            بر اساس {yearlyAverage.count} ارزیابی ثبت‌شده
          </Typography>
        </Box>
        <Chip
          label={Math.round(yearlyAverage.average_score)}
          color={scoreColor(yearlyAverage.average_score)}
          sx={{ fontSize: 18, height: 36, px: 1 }}
        />
      </Stack>
    </Card>
  );
}

// ⚠️ نمایش پاسخ ارزیاب به هر سوال - بسته به نوع سوال، مقدار در فیلد
// متفاوتی ذخیره شده (همان ساختار EvaluationAnswer در بک‌اند).
function formatAnswerValue(answer) {
  if (answer.text_value) return answer.text_value;
  if (answer.number_value != null) return String(answer.number_value);
  if (answer.date_value) return new Date(answer.date_value).toLocaleDateString("fa-IR");
  // ⚠️ قبلاً فقط تعداد گزینه‌ها نمایش داده می‌شد و معلوم نبود کدام
  // انتخاب شده - حالا برچسب واقعی گزینه(های) انتخاب‌شده نشان داده می‌شود.
  if (answer.selected_option_labels?.length) return answer.selected_option_labels.join("، ");
  if (answer.selected_option_ids?.length) return `${answer.selected_option_ids.length} گزینه انتخاب شده`;
  return "—";
}

/**
 * ⚠️ طبق گزارش کاربر: کاربر باید بفهمد «از بین چه گزینه‌هایی» انتخاب
 * شده - نه فقط کدام. همه گزینه‌های ممکن نمایش داده می‌شوند و انتخاب‌شده‌ها
 * برجسته‌اند. برای ارزیابی‌های قدیمی که گزینه‌هایشان دیگر موجود نیست،
 * فهرست خالی است و چیزی رندر نمی‌شود (بدون خطا).
 */
function AnswerOptionsList({ options }) {
  if (!options?.length) return null;
  return (
    <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 0.75 }}>
      {options.map((option) => (
        <Chip
          key={option.id}
          size="small"
          label={`${option.label} (${option.score})`}
          color={option.is_selected ? "primary" : "default"}
          variant={option.is_selected ? "filled" : "outlined"}
        />
      ))}
    </Stack>
  );
}

function ResultDetailsDialog({ result, onClose }) {
  const [answers, setAnswers] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchMyEvaluationResultAnswers(result.id)
      .then(setAnswers)
      .catch((err) => {
        setError(err.response?.data?.detail || "دریافت جزئیات با خطا مواجه شد.");
        setAnswers([]);
      });
  }, [result.id]);

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>
        <Typography fontWeight={700}>{result.period_title_snapshot}</Typography>
        <Typography variant="caption" color="text.secondary">
          ارزیاب: {result.evaluator_name_snapshot} — امتیاز کل: {Math.round(result.total_score)}
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
                <AnswerOptionsList options={answer.available_options} />
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

function ResultCard({ result, onClick }) {
  return (
    <Card
      variant="outlined"
      onClick={onClick}
      sx={{ p: 2, mb: 1.5, borderRadius: 2, cursor: "pointer", "&:hover": { bgcolor: "action.hover" } }}
    >
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Box>
          <Typography fontWeight={700}>{result.period_title_snapshot}</Typography>
          <Typography variant="caption" color="text.secondary">
            ارزیاب: {result.evaluator_name_snapshot} — {new Date(result.submitted_at).toLocaleDateString("fa-IR")}
          </Typography>
        </Box>
        <Chip label={`امتیاز: ${Math.round(result.total_score)}`} color={scoreColor(result.total_score)} />
      </Stack>
      {result.comment && (
        <Typography variant="body2" sx={{ mt: 1 }}>
          {result.comment}
        </Typography>
      )}
      <Typography variant="caption" color="primary" sx={{ mt: 1, display: "block" }}>
        برای دیدن جزئیات سوالات کلیک کنید
      </Typography>
    </Card>
  );
}

function MyPersonnelTable({ items, periodFilter, setPeriodFilter, onStart, onEdit }) {
  const periodTitles = useMemo(() => [...new Set(items.map((i) => i.period_title))], [items]);
  const filteredItems = periodFilter ? items.filter((i) => i.period_title === periodFilter) : items;
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);

  // ⚠️ با تغییر فیلتر دوره، به صفحه اول برگرد - وگرنه ممکن است کاربر
  // روی صفحه‌ای بماند که دیگر ردیفی ندارد و جدول خالی به‌نظر برسد.
  useEffect(() => {
    setPage(0);
  }, [periodFilter]);

  const visibleItems = filteredItems.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  return (
    <Box>
      <TextField
        select
        size="small"
        label="فیلتر بر اساس دوره ارزیابی"
        value={periodFilter}
        onChange={(e) => setPeriodFilter(e.target.value)}
        sx={{ minWidth: 240, mb: 2 }}
      >
        <MenuItem value="">همه دوره‌ها</MenuItem>
        {periodTitles.map((title) => (
          <MenuItem key={title} value={title}>
            {title}
          </MenuItem>
        ))}
      </TextField>

      <TableContainer component={Card} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>نام و نام خانوادگی</TableCell>
              <TableCell>کد پرسنلی</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>امتیاز</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {visibleItems.map((item) => (
              <TableRow key={item.assignment_id}>
                <TableCell>
                  {item.target.first_name} {item.target.last_name}
                </TableCell>
                <TableCell>{item.target.personnel_code}</TableCell>
                <TableCell>
                  <Chip size="small" color={STATUS_COLORS[item.status]} label={STATUS_LABELS[item.status]} />
                </TableCell>
                <TableCell>
                  {item.status === "submitted" && item.total_score != null ? (
                    <Chip size="small" color={scoreColor(item.total_score)} label={Math.round(item.total_score)} />
                  ) : (
                    "—"
                  )}
                </TableCell>
                <TableCell>
                  {item.status !== "submitted" && (
                    <Button size="small" variant="contained" onClick={() => onStart(item)}>
                      {item.status === "draft" ? "ادامه ارزیابی" : "شروع ارزیابی"}
                    </Button>
                  )}
                  {item.status === "submitted" && !item.was_edited && (
                    <Button size="small" variant="outlined" onClick={() => onEdit(item)}>
                      ویرایش
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={filteredItems.length}
          page={page}
          onPageChange={(_, newPage) => setPage(newPage)}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(parseInt(e.target.value, 10));
            setPage(0);
          }}
          rowsPerPageOptions={[10, 25, 50, 100]}
          labelRowsPerPage="تعداد در هر صفحه:"
          labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
        />
      </TableContainer>
    </Box>
  );
}

function ShiftLeadEvaluationsTable({ items, onEdit }) {
  return (
    <TableContainer component={Card} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>ارزیابی‌شده</TableCell>
            <TableCell>سرشیفت (ارزیاب)</TableCell>
            <TableCell>دوره ارزیابی</TableCell>
            <TableCell>امتیاز</TableCell>
            <TableCell>عملیات</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.evaluation_id}>
              <TableCell>{item.target_name}</TableCell>
              <TableCell>{item.shift_lead_name}</TableCell>
              <TableCell>{item.period_title}</TableCell>
              <TableCell>
                {item.total_score != null ? (
                  <Chip size="small" color={scoreColor(item.total_score)} label={Math.round(item.total_score)} />
                ) : (
                  "—"
                )}
              </TableCell>
              <TableCell>
                {!item.was_edited && (
                  <Button size="small" variant="outlined" onClick={() => onEdit(item)}>
                    ویرایش
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

const TAB_KEYS = ["results", "personnel", "shift-leads"];

export default function MyPerformancePage() {
  const navigate = useNavigate();
  // ⚠️ طبق اصل کلی بازگشت به مبدأ درست: تب فعال هم در آدرس صفحه ذخیره
  // می‌شود (?tab=personnel و...) - هم رفرش صفحه تب را گم نمی‌کند، هم
  // وقتی از صفحه ارزیابی برمی‌گردیم، دقیقاً همان تبی که رفته بودیم باز
  // می‌شود، نه همیشه تب پیش‌فرض.
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = TAB_KEYS.indexOf(searchParams.get("tab"));
  const [tab, setTab] = useState(tabFromUrl >= 0 ? tabFromUrl : 0);

  function handleTabChange(newIndex) {
    setTab(newIndex);
    setSearchParams({ tab: TAB_KEYS[newIndex] });
  }

  const [results, setResults] = useState(null);
  const [detailsResult, setDetailsResult] = useState(null);
  const [gateStatus, setGateStatus] = useState(null);
  const [gateOpen, setGateOpen] = useState(false);

  // دیالوگ فقط وقتی کاربر روی تب «نتایج» است باز می‌شود.
  useEffect(() => {
    if (tab === 0 && gateStatus?.blocked_features?.["evaluation_result"]) setGateOpen(true);
  }, [tab, gateStatus]);

  useEffect(() => {
    fetchMyAccessGateStatus()
      .then(setGateStatus)
      .catch(() => setGateStatus(null));
  }, []);
  const [pending, setPending] = useState(null);
  const [shiftLeadEvaluations, setShiftLeadEvaluations] = useState(null);
  const [periodFilter, setPeriodFilter] = useState("");
  const [yearlyAverage, setYearlyAverage] = useState(null);
  const [error, setError] = useState("");

  function loadPending() {
    fetchMyEvaluations()
      .then(setPending)
      .catch((err) => setError(err.response?.data?.detail || "دریافت ارزیابی‌های من با خطا مواجه شد."));
  }

  function loadShiftLeadEvaluations() {
    fetchMyShiftLeadEvaluations()
      .then(setShiftLeadEvaluations)
      .catch(() => setShiftLeadEvaluations([]));
  }

  useEffect(() => {
    fetchMyEvaluationResults()
      .then(setResults)
      .catch((err) => setError(err.response?.data?.detail || "دریافت نتایج ارزیابی با خطا مواجه شد."));
    fetchMyYearlyAverage()
      .then(setYearlyAverage)
      .catch(() => setYearlyAverage(null));
    loadPending();
    loadShiftLeadEvaluations();
  }, []);

  function handleStart(item) {
    navigate(`/my-performance/evaluate/${item.assignment_id}`);
  }

  async function handleEdit(item) {
    setError("");
    try {
      await reopenEvaluation(item.evaluation_id);
      navigate(`/my-performance/evaluate/${item.assignment_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "بازکردن ارزیابی برای ویرایش با خطا مواجه شد.");
      loadPending();
    }
  }

  async function handleEditShiftLeadEvaluation(item) {
    setError("");
    try {
      await reopenEvaluation(item.evaluation_id);
      navigate(`/my-performance/edit-evaluation/${item.evaluation_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "بازکردن ارزیابی برای ویرایش با خطا مواجه شد.");
      loadShiftLeadEvaluations();
    }
  }

  const pendingCount = pending?.filter((p) => p.status !== "submitted").length || 0;
  const hasShiftLeadEvaluations = shiftLeadEvaluations && shiftLeadEvaluations.length > 0;

  return (
    <Box>
      <BackLink to="/my-dashboard" />
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        ارزیابی عملکرد من
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Tabs value={tab} onChange={(_, v) => handleTabChange(v)} sx={{ mb: 2 }}>
        <Tab label="نتایج ارزیابی من" />
        <Tab label={pendingCount > 0 ? `ارزیابی پرسنل من (${pendingCount})` : "ارزیابی پرسنل من"} />
        {hasShiftLeadEvaluations && <Tab label="ارزیابی‌های سرشیفت‌های من" />}
      </Tabs>

      {tab === 0 && (
        <Box>
          <YearlyAverageCard yearlyAverage={yearlyAverage} />
          {results === null ? null : results.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              هنوز هیچ ارزیابی‌ای برای شما ثبت نشده است.
            </Typography>
          ) : (
            results.map((result) => (
              <ResultCard key={result.id} result={result} onClick={() => setDetailsResult(result)} />
            ))
          )}
        </Box>
      )}

      {tab === 1 && (
        <Box>
          {pending === null ? null : pending.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              فعلاً هیچ پرسنلی برای ارزیابی به شما اختصاص داده نشده است.
            </Typography>
          ) : (
            <MyPersonnelTable
              items={pending}
              periodFilter={periodFilter}
              setPeriodFilter={setPeriodFilter}
              onStart={handleStart}
              onEdit={handleEdit}
            />
          )}
        </Box>
      )}

      {tab === 2 && hasShiftLeadEvaluations && (
        <Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            ارزیابی‌هایی که سرشیفت‌های واحد شما انجام داده‌اند - در صورت نیاز می‌توانید آن‌ها را
            ویرایش کنید (هرکدام فقط یک‌بار قابل‌ویرایش است).
          </Typography>
          <ShiftLeadEvaluationsTable items={shiftLeadEvaluations} onEdit={handleEditShiftLeadEvaluation} />
        </Box>
      )}

      {detailsResult && <ResultDetailsDialog result={detailsResult} onClose={() => setDetailsResult(null)} />}

      {/* ⚠️ فقط تب «نتایج» مشروط است - تب «پرسنل من» (انجام ارزیابی)
          همیشه باز می‌ماند، وگرنه کاربری که به‌خاطر ارزیابی
          انجام‌نشده قفل شده، نمی‌توانست همان ارزیابی را انجام دهد
          و قفل خودش را باز کند. */}
      <AccessGateDialog
        open={gateOpen}
        gate={gateStatus?.blocked_features?.["evaluation_result"]}
        count={
          gateStatus?.blocked_features?.["evaluation_result"] === "pending_evaluations"
            ? gateStatus?.pending_evaluations
            : gateStatus?.unread_notices
        }
        byPeriod={gateStatus?.pending_by_period}
        onClose={() => setGateOpen(false)}
      />
    </Box>
  );
}
