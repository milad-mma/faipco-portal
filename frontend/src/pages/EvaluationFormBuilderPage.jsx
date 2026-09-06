import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  FormControlLabel,
  IconButton,
  MenuItem,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import {
  addEvaluationCategory,
  addEvaluationQuestion,
  deleteEvaluationCategory,
  deleteEvaluationQuestion,
  fetchEvaluationForm,
  updateEvaluationCategory,
  updateEvaluationFormStatus,
  updateEvaluationQuestion,
} from "../api/evaluationForms";

const QUESTION_TYPE_LABELS = {
  single_choice: "تک‌انتخابی",
  multiple_choice: "چندانتخابی",
  rating: "امتیازی (Rating)",
  yes_no: "بله/خیر",
  text: "متن آزاد",
  number: "عدد",
  date: "تاریخ",
};

const OPTION_REQUIRED_TYPES = ["single_choice", "multiple_choice", "rating", "yes_no"];

const STATUS_LABELS = { draft: "پیش‌نویس", active: "فعال", inactive: "غیرفعال", archived: "بایگانی‌شده" };
const STATUS_COLORS = { draft: "default", active: "success", inactive: "warning", archived: "default" };

function QuestionEditor({ question, categoryId, onSaved, onDeleted, disabled }) {
  const [text, setText] = useState(question.text);
  const [description, setDescription] = useState(question.description || "");
  const [questionType, setQuestionType] = useState(question.question_type);
  const [weight, setWeight] = useState(question.weight);
  const [required, setRequired] = useState(question.required);
  const [isActive, setIsActive] = useState(question.is_active);
  const [options, setOptions] = useState(question.options.map((o) => ({ label: o.label, score: o.score })));
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const needsOptions = OPTION_REQUIRED_TYPES.includes(questionType);

  function addOption() {
    setOptions([...options, { label: "", score: 0 }]);
  }

  function updateOption(index, field, value) {
    const next = [...options];
    next[index] = { ...next[index], [field]: value };
    setOptions(next);
  }

  function removeOption(index) {
    setOptions(options.filter((_, i) => i !== index));
  }

  async function handleSave() {
    setError("");
    setIsSaving(true);
    try {
      const payload = {
        text,
        description: description || null,
        question_type: questionType,
        weight: Number(weight),
        required,
        sort_order: question.sort_order,
        is_active: isActive,
        options: needsOptions
          ? options.map((o, i) => ({ label: o.label, score: Number(o.score), sort_order: i }))
          : [],
      };
      if (question.id) {
        await updateEvaluationQuestion(question.id, payload);
      } else {
        await addEvaluationQuestion(categoryId, payload);
      }
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره سوال با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Box sx={{ p: 2, border: "1px solid", borderColor: "divider", borderRadius: 2, mb: 1.5 }}>
      <Stack spacing={1.5}>
        <TextField
          label="متن سوال"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={disabled}
          multiline
        />
        <TextField
          label="توضیح تکمیلی (اختیاری)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={disabled}
          size="small"
        />
        <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
          <TextField
            select
            label="نوع سوال"
            size="small"
            value={questionType}
            onChange={(e) => setQuestionType(e.target.value)}
            disabled={disabled}
            sx={{ minWidth: 180 }}
          >
            {Object.entries(QUESTION_TYPE_LABELS).map(([value, label]) => (
              <MenuItem key={value} value={value}>
                {label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="وزن (٪ از دسته‌بندی)"
            type="number"
            size="small"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            disabled={disabled}
            sx={{ width: 160 }}
          />
          <FormControlLabel
            control={<Switch checked={required} onChange={(e) => setRequired(e.target.checked)} disabled={disabled} />}
            label="اجباری"
          />
          <FormControlLabel
            control={<Switch checked={isActive} onChange={(e) => setIsActive(e.target.checked)} disabled={disabled} />}
            label="فعال"
          />
        </Stack>

        {needsOptions && (
          <Box>
            <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ display: "block", mb: 1 }}>
              گزینه‌های پاسخ
            </Typography>
            <Stack spacing={1}>
              {options.map((option, index) => (
                <Stack direction="row" spacing={1} key={index} alignItems="center">
                  <TextField
                    size="small"
                    label="متن گزینه"
                    value={option.label}
                    onChange={(e) => updateOption(index, "label", e.target.value)}
                    disabled={disabled}
                    sx={{ flexGrow: 1 }}
                  />
                  <TextField
                    size="small"
                    label="امتیاز"
                    type="number"
                    value={option.score}
                    onChange={(e) => updateOption(index, "score", e.target.value)}
                    disabled={disabled}
                    sx={{ width: 100 }}
                  />
                  {!disabled && (
                    <IconButton size="small" onClick={() => removeOption(index)}>
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  )}
                </Stack>
              ))}
              {!disabled && (
                <Button size="small" startIcon={<AddOutlinedIcon />} onClick={addOption} sx={{ alignSelf: "start" }}>
                  افزودن گزینه
                </Button>
              )}
            </Stack>
          </Box>
        )}

        {error && <Alert severity="error">{error}</Alert>}

        {!disabled && (
          <Stack direction="row" spacing={1}>
            <Button size="small" variant="contained" onClick={handleSave} disabled={isSaving || !text.trim()}>
              {isSaving ? "در حال ذخیره..." : "ذخیره سوال"}
            </Button>
            {question.id && (
              <Button size="small" color="error" onClick={() => onDeleted(question.id)}>
                حذف سوال
              </Button>
            )}
          </Stack>
        )}
      </Stack>
    </Box>
  );
}

function CategoryEditor({ category, onChanged, disabled }) {
  const [title, setTitle] = useState(category.title);
  const [weight, setWeight] = useState(category.weight);
  const [isActive, setIsActive] = useState(category.is_active);
  const [error, setError] = useState("");
  const [addingQuestion, setAddingQuestion] = useState(false);

  async function handleSaveCategory() {
    setError("");
    try {
      await updateEvaluationCategory(category.id, {
        title,
        weight: Number(weight),
        sort_order: category.sort_order,
        is_active: isActive,
      });
      onChanged();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره دسته‌بندی با خطا مواجه شد.");
    }
  }

  async function handleDeleteCategory() {
    try {
      await deleteEvaluationCategory(category.id);
      onChanged();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف دسته‌بندی با خطا مواجه شد.");
    }
  }

  async function handleDeleteQuestion(questionId) {
    try {
      await deleteEvaluationQuestion(questionId);
      onChanged();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف سوال با خطا مواجه شد.");
    }
  }

  return (
    <Accordion disableGutters variant="outlined" sx={{ mb: 1.5 }}>
      <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Typography fontWeight={700}>{category.title}</Typography>
          <Chip size="small" label={`وزن: ${category.weight}٪`} />
          <Chip size="small" label={`${category.questions.length} سوال`} />
          {!category.is_active && <Chip size="small" color="warning" label="غیرفعال" />}
        </Stack>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={2}>
          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap alignItems="center">
            <TextField
              label="عنوان دسته‌بندی"
              size="small"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={disabled}
            />
            <TextField
              label="وزن (٪ از فرم)"
              type="number"
              size="small"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              disabled={disabled}
              sx={{ width: 160 }}
            />
            <FormControlLabel
              control={<Switch checked={isActive} onChange={(e) => setIsActive(e.target.checked)} disabled={disabled} />}
              label="فعال"
            />
            {!disabled && (
              <>
                <Button size="small" variant="outlined" onClick={handleSaveCategory}>
                  ذخیره دسته‌بندی
                </Button>
                <Button size="small" color="error" onClick={handleDeleteCategory}>
                  حذف دسته‌بندی
                </Button>
              </>
            )}
          </Stack>

          {error && <Alert severity="error">{error}</Alert>}

          <Divider />

          {category.questions.map((question) => (
            <QuestionEditor
              key={question.id}
              question={question}
              categoryId={category.id}
              onSaved={onChanged}
              onDeleted={handleDeleteQuestion}
              disabled={disabled}
            />
          ))}

          {addingQuestion ? (
            <QuestionEditor
              question={{
                id: null,
                text: "",
                description: "",
                question_type: "single_choice",
                weight: 0,
                required: true,
                sort_order: category.questions.length,
                is_active: true,
                options: [],
              }}
              categoryId={category.id}
              onSaved={() => {
                setAddingQuestion(false);
                onChanged();
              }}
              onDeleted={() => setAddingQuestion(false)}
              disabled={disabled}
            />
          ) : (
            !disabled && (
              <Button size="small" startIcon={<AddOutlinedIcon />} onClick={() => setAddingQuestion(true)}>
                افزودن سوال
              </Button>
            )
          )}
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
}

export default function EvaluationFormBuilderPage() {
  const { formId } = useParams();
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [newCategoryTitle, setNewCategoryTitle] = useState("");

  function loadForm() {
    setError("");
    fetchEvaluationForm(formId)
      .then(setForm)
      .catch((err) => setError(err.response?.data?.detail || "دریافت فرم ارزیابی با خطا مواجه شد."));
  }

  useEffect(loadForm, [formId]);

  const disabled = form && form.status !== "draft";

  async function handleAddCategory() {
    setError("");
    try {
      await addEvaluationCategory(formId, {
        title: newCategoryTitle,
        weight: 0,
        sort_order: form.categories.length,
        is_active: true,
      });
      setNewCategoryTitle("");
      loadForm();
    } catch (err) {
      setError(err.response?.data?.detail || "افزودن دسته‌بندی با خطا مواجه شد.");
    }
  }

  async function handleActivate() {
    setError("");
    setStatusMessage("");
    try {
      await updateEvaluationFormStatus(formId, "active");
      setStatusMessage("فرم با موفقیت فعال شد.");
      loadForm();
    } catch (err) {
      setError(err.response?.data?.detail || "فعال‌سازی فرم با خطا مواجه شد.");
    }
  }

  if (!form) {
    return error ? <Alert severity="error">{error}</Alert> : null;
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            {form.title}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            نسخه {form.version}
          </Typography>
        </Box>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip color={STATUS_COLORS[form.status]} label={STATUS_LABELS[form.status]} />
          {form.status === "draft" && (
            <Button variant="contained" onClick={handleActivate}>
              فعال‌سازی فرم
            </Button>
          )}
        </Stack>
      </Stack>

      {disabled && (
        <Alert severity="info" sx={{ mb: 2 }}>
          این فرم دیگر در وضعیت پیش‌نویس نیست - برای حفظ یکپارچگی تاریخچه ارزیابی‌ها، قابل‌ویرایش نیست.
          برای تغییر محتوا، از دکمه «نسخه جدید» در فهرست فرم‌ها استفاده کنید.
        </Alert>
      )}

      {statusMessage && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {statusMessage}
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {form.categories.map((category) => (
        <CategoryEditor key={category.id} category={category} onChanged={loadForm} disabled={disabled} />
      ))}

      {!disabled && (
        <Stack direction="row" spacing={1.5} sx={{ mt: 2 }}>
          <TextField
            size="small"
            label="عنوان دسته‌بندی جدید"
            value={newCategoryTitle}
            onChange={(e) => setNewCategoryTitle(e.target.value)}
          />
          <Button
            variant="outlined"
            startIcon={<AddOutlinedIcon />}
            onClick={handleAddCategory}
            disabled={!newCategoryTitle.trim()}
          >
            افزودن دسته‌بندی
          </Button>
        </Stack>
      )}
    </Box>
  );
}
