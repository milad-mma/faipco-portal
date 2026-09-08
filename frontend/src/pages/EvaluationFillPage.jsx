import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  Checkbox,
  Chip,
  FormControlLabel,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { fetchEvaluationForm } from "../api/evaluationForms";
import { saveEvaluationAnswers, startEvaluation, submitEvaluation } from "../api/evaluationProcess";
import JalaliDateTimePicker from "../components/JalaliDateTimePicker";

function QuestionField({ question, value, onChange }) {
  const type = question.question_type;

  if (type === "single_choice" || type === "rating" || type === "yes_no") {
    return (
      <RadioGroup
        value={value.selected_option_ids?.[0] ?? ""}
        onChange={(e) => onChange({ ...value, selected_option_ids: [Number(e.target.value)] })}
      >
        {question.options.map((option) => (
          <FormControlLabel key={option.id} value={option.id} control={<Radio />} label={option.label} />
        ))}
      </RadioGroup>
    );
  }

  if (type === "multiple_choice") {
    const selected = value.selected_option_ids || [];
    function toggle(optionId) {
      const next = selected.includes(optionId) ? selected.filter((id) => id !== optionId) : [...selected, optionId];
      onChange({ ...value, selected_option_ids: next });
    }
    return (
      <Stack>
        {question.options.map((option) => (
          <FormControlLabel
            key={option.id}
            control={<Checkbox checked={selected.includes(option.id)} onChange={() => toggle(option.id)} />}
            label={option.label}
          />
        ))}
      </Stack>
    );
  }

  if (type === "number") {
    return (
      <TextField
        type="number"
        size="small"
        value={value.number_value ?? ""}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === "") {
            onChange({ ...value, number_value: null });
            return;
          }
          const clamped = Math.min(question.weight, Math.max(0, Number(raw)));
          onChange({ ...value, number_value: clamped });
        }}
        inputProps={{ min: 0, max: question.weight }}
        helperText={`بین ۰ تا ${question.weight} (این عدد مستقیماً امتیاز همین سوال است)`}
        sx={{ maxWidth: 220 }}
      />
    );
  }

  if (type === "date") {
    return (
      <JalaliDateTimePicker
        value={value.date_value ? new Date(value.date_value) : new Date()}
        onChange={(d) => onChange({ ...value, date_value: d.toISOString() })}
      />
    );
  }

  return (
    <TextField
      multiline
      minRows={2}
      fullWidth
      value={value.text_value ?? ""}
      onChange={(e) => onChange({ ...value, text_value: e.target.value })}
    />
  );
}

export default function EvaluationFillPage() {
  const { assignmentId } = useParams();
  const navigate = useNavigate();
  const [evaluation, setEvaluation] = useState(null);
  const [form, setForm] = useState(null);
  const [answers, setAnswers] = useState({});
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");

  useEffect(() => {
    startEvaluation(assignmentId)
      .then(async (evalData) => {
        setEvaluation(evalData);
        const formData = await fetchEvaluationForm(evalData.form_id);
        setForm(formData);

        const initialAnswers = {};
        for (const answer of evalData.answers) {
          initialAnswers[answer.question_id] = {
            selected_option_ids: answer.selected_option_ids,
            text_value: answer.text_value,
            number_value: answer.number_value,
            date_value: answer.date_value,
            comment: answer.comment,
          };
        }
        setAnswers(initialAnswers);
      })
      .catch((err) => setError(err.response?.data?.detail || "دریافت ارزیابی با خطا مواجه شد."));
  }, [assignmentId]);

  function updateAnswer(questionId, value) {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  }

  function buildAnswersPayload() {
    return Object.entries(answers)
      .filter(
        ([, v]) => v && (v.selected_option_ids?.length || v.text_value || v.number_value != null || v.date_value)
      )
      .map(([questionId, v]) => ({ question_id: Number(questionId), ...v }));
  }

  async function handleSaveDraft() {
    setError("");
    setSaveMessage("");
    setIsSaving(true);
    try {
      await saveEvaluationAnswers(evaluation.id, buildAnswersPayload());
      setSaveMessage("پیش‌نویس ذخیره شد.");
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره پیش‌نویس با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSubmit() {
    setError("");
    setSaveMessage("");
    setIsSaving(true);
    try {
      await saveEvaluationAnswers(evaluation.id, buildAnswersPayload());
      await submitEvaluation(evaluation.id);
      navigate("/my-performance");
    } catch (err) {
      setError(err.response?.data?.detail || "ثبت نهایی ارزیابی با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  if (error && !form) {
    return <Alert severity="error">{error}</Alert>;
  }
  if (!form || !evaluation) {
    return null;
  }

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        {form.title}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        ارزیابی‌شونده: {evaluation.target_name_snapshot}
      </Typography>

      {form.categories.map((category) => (
        <Card key={category.id} variant="outlined" sx={{ p: 2.5, mb: 2 }}>
          <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
            {category.title}
          </Typography>
          <Stack spacing={3}>
            {category.questions.map((question) => (
              <Box key={question.id}>
                <Typography variant="body1" sx={{ mb: 1 }}>
                  {question.text}
                  {question.required && (
                    <Chip label="اجباری" size="small" color="error" variant="outlined" sx={{ ml: 1 }} />
                  )}
                </Typography>
                {question.description && (
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
                    {question.description}
                  </Typography>
                )}
                <QuestionField
                  question={question}
                  value={answers[question.id] || {}}
                  onChange={(v) => updateAnswer(question.id, v)}
                />
              </Box>
            ))}
          </Stack>
        </Card>
      ))}

      {saveMessage && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {saveMessage}
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Stack direction="row" spacing={1.5}>
        <Button variant="outlined" onClick={handleSaveDraft} disabled={isSaving}>
          ذخیره پیش‌نویس
        </Button>
        <Button variant="contained" onClick={handleSubmit} disabled={isSaving}>
          ثبت نهایی
        </Button>
      </Stack>
    </Box>
  );
}
