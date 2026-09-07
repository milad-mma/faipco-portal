import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Box, Button, Card, Chip, Stack, Tab, Tabs, Typography } from "@mui/material";
import {
  fetchMyEvaluationResults,
  fetchMyEvaluations,
  fetchMyYearlyAverage,
  reopenEvaluation,
} from "../api/evaluationProcess";

const STATUS_LABELS = { not_started: "شروع‌نشده", draft: "پیش‌نویس", submitted: "ثبت‌شده" };
const STATUS_COLORS = { not_started: "default", draft: "warning", submitted: "success" };

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
          color={
            yearlyAverage.average_score >= 70 ? "success" : yearlyAverage.average_score >= 50 ? "warning" : "error"
          }
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
          <Typography fontWeight={700}>{result.form_title_snapshot}</Typography>
          <Typography variant="caption" color="text.secondary">
            ارزیاب: {result.evaluator_name_snapshot} — {new Date(result.submitted_at).toLocaleDateString("fa-IR")}
            {result.was_edited && " (ویرایش‌شده)"}
          </Typography>
        </Box>
        <Chip
          label={`امتیاز: ${Math.round(result.total_score)}`}
          color={result.total_score >= 70 ? "success" : result.total_score >= 50 ? "warning" : "error"}
        />
      </Stack>
      {result.comment && (
        <Typography variant="body2" sx={{ mt: 1 }}>
          {result.comment}
        </Typography>
      )}
    </Card>
  );
}

function PendingEvaluationCard({ item, onStart, onEdit }) {
  return (
    <Card variant="outlined" sx={{ p: 2, mb: 1.5 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Box>
          <Typography fontWeight={700}>
            {item.target.first_name} {item.target.last_name} ({item.target.personnel_code})
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {item.period_title} — {item.form_title}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip size="small" color={STATUS_COLORS[item.status]} label={STATUS_LABELS[item.status]} />
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
        </Stack>
      </Stack>
    </Card>
  );
}

export default function MyPerformancePage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState(0);
  const [results, setResults] = useState(null);
  const [pending, setPending] = useState(null);
  const [yearlyAverage, setYearlyAverage] = useState(null);
  const [error, setError] = useState("");

  function loadPending() {
    fetchMyEvaluations()
      .then(setPending)
      .catch((err) => setError(err.response?.data?.detail || "دریافت ارزیابی‌های من با خطا مواجه شد."));
  }

  useEffect(() => {
    fetchMyEvaluationResults()
      .then(setResults)
      .catch((err) => setError(err.response?.data?.detail || "دریافت نتایج ارزیابی با خطا مواجه شد."));
    fetchMyYearlyAverage()
      .then(setYearlyAverage)
      .catch(() => setYearlyAverage(null));
    loadPending();
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

  const pendingCount = pending?.filter((p) => p.status !== "submitted").length || 0;

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
            pending.map((item) => (
              <PendingEvaluationCard key={item.assignment_id} item={item} onStart={handleStart} onEdit={handleEdit} />
            ))
          )}
        </Box>
      )}
    </Box>
  );
}
