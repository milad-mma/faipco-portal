import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Box, Button, Card, Chip, Stack, Tab, Tabs, Typography } from "@mui/material";
import { fetchMyEvaluationResults, fetchMyEvaluations } from "../api/evaluationProcess";

const STATUS_LABELS = { not_started: "شروع‌نشده", draft: "پیش‌نویس", submitted: "ثبت‌شده" };
const STATUS_COLORS = { not_started: "default", draft: "warning", submitted: "success" };

function ResultCard({ result }) {
  return (
    <Card variant="outlined" sx={{ p: 2, mb: 1.5 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Box>
          <Typography fontWeight={700}>{result.form_title_snapshot}</Typography>
          <Typography variant="caption" color="text.secondary">
            ارزیاب: {result.evaluator_name_snapshot} — {new Date(result.submitted_at).toLocaleDateString("fa-IR")}
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

function PendingEvaluationCard({ item, onStart }) {
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
  const [error, setError] = useState("");

  useEffect(() => {
    fetchMyEvaluationResults()
      .then(setResults)
      .catch((err) => setError(err.response?.data?.detail || "دریافت نتایج ارزیابی با خطا مواجه شد."));
    fetchMyEvaluations()
      .then(setPending)
      .catch((err) => setError(err.response?.data?.detail || "دریافت ارزیابی‌های من با خطا مواجه شد."));
  }, []);

  function handleStart(item) {
    navigate(`/my-performance/evaluate/${item.assignment_id}`);
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
            pending.map((item) => <PendingEvaluationCard key={item.assignment_id} item={item} onStart={handleStart} />)
          )}
        </Box>
      )}
    </Box>
  );
}
