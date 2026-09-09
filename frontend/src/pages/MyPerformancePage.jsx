import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
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
import {
  fetchMyEvaluationResults,
  fetchMyEvaluations,
  fetchMyShiftLeadEvaluations,
  fetchMyYearlyAverage,
  reopenEvaluation,
} from "../api/evaluationProcess";

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

function ResultCard({ result }) {
  return (
    <Card variant="outlined" sx={{ p: 2, mb: 1.5 }}>
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
    </Card>
  );
}

function MyPersonnelTable({ items, periodFilter, setPeriodFilter, onStart, onEdit }) {
  const periodTitles = useMemo(() => [...new Set(items.map((i) => i.period_title))], [items]);
  const filteredItems = periodFilter ? items.filter((i) => i.period_title === periodFilter) : items;

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
            {filteredItems.map((item) => (
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

export default function MyPerformancePage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState(0);
  const [results, setResults] = useState(null);
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
      <Typography variant="h5" fontWeight={700} sx={{ mb: 2 }}>
        ارزیابی عملکرد من
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
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
            results.map((result) => <ResultCard key={result.id} result={result} />)
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
    </Box>
  );
}
