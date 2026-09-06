import { useEffect, useState } from "react";
import {
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
  TextField,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import ContentCopyOutlinedIcon from "@mui/icons-material/ContentCopyOutlined";
import { useNavigate } from "react-router-dom";
import { fetchSites } from "../api/sites";
import {
  createEvaluationForm,
  deleteEvaluationForm,
  duplicateEvaluationForm,
  fetchEvaluationForms,
} from "../api/evaluationForms";

const STATUS_LABELS = { draft: "پیش‌نویس", active: "فعال", inactive: "غیرفعال", archived: "بایگانی‌شده" };
const STATUS_COLORS = { draft: "default", active: "success", inactive: "warning", archived: "default" };

function NewFormDialog({ open, onClose, onCreated, sites }) {
  const [siteId, setSiteId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const navigate = useNavigate();

  async function handleCreate() {
    setError("");
    setIsSaving(true);
    try {
      const form = await createEvaluationForm({
        site_id: siteId === "" ? null : siteId,
        title,
        description: description || null,
      });
      onCreated();
      onClose();
      navigate(`/performance/forms/${form.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "ساخت فرم با خطا مواجه شد.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>فرم ارزیابی جدید</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        <TextField
          select
          label="سایت (اختیاری - خالی یعنی همه سایت‌ها)"
          value={siteId}
          onChange={(e) => setSiteId(e.target.value)}
        >
          <MenuItem value="">همه سایت‌ها</MenuItem>
          {sites.map((site) => (
            <MenuItem key={site.id} value={site.id}>
              {site.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label="عنوان فرم"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="مثلاً فرم ارزیابی عملکرد پرسنل"
        />
        <TextField
          label="توضیحات (اختیاری)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          multiline
          minRows={2}
        />
        {error && <Alert severity="error">{error}</Alert>}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isSaving}>
          انصراف
        </Button>
        <Button variant="contained" onClick={handleCreate} disabled={isSaving || !title.trim()}>
          {isSaving ? "در حال ساخت..." : "ساخت و ادامه به فرم‌ساز"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function EvaluationFormsPage() {
  const [sites, setSites] = useState([]);
  const [forms, setForms] = useState([]);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchSites().then(setSites);
  }, []);

  function loadForms() {
    setError("");
    fetchEvaluationForms()
      .then(setForms)
      .catch((err) => setError(err.response?.data?.detail || "دریافت فرم‌های ارزیابی با خطا مواجه شد."));
  }

  useEffect(loadForms, []);

  function siteName(siteId) {
    if (siteId === null) return "همه سایت‌ها";
    return sites.find((s) => s.id === siteId)?.name || "—";
  }

  async function handleDuplicate(form) {
    try {
      const newForm = await duplicateEvaluationForm(form.id);
      loadForms();
      navigate(`/performance/forms/${newForm.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "ساخت نسخه جدید با خطا مواجه شد.");
    }
  }

  async function handleDelete(form) {
    try {
      await deleteEvaluationForm(form.id);
      loadForms();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف فرم با خطا مواجه شد.");
    }
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h5" fontWeight={700}>
          فرم‌های ارزیابی
        </Typography>
        <Button variant="contained" startIcon={<AddOutlinedIcon />} onClick={() => setDialogOpen(true)}>
          فرم جدید
        </Button>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>عنوان</TableCell>
              <TableCell>سایت</TableCell>
              <TableCell>نسخه</TableCell>
              <TableCell>وضعیت</TableCell>
              <TableCell>عملیات</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {forms.map((form) => (
              <TableRow key={form.id} hover sx={{ cursor: "pointer" }}>
                <TableCell onClick={() => navigate(`/performance/forms/${form.id}`)}>{form.title}</TableCell>
                <TableCell>{siteName(form.site_id)}</TableCell>
                <TableCell>نسخه {form.version}</TableCell>
                <TableCell>
                  <Chip size="small" color={STATUS_COLORS[form.status]} label={STATUS_LABELS[form.status]} />
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={1}>
                    <Button size="small" onClick={() => navigate(`/performance/forms/${form.id}`)}>
                      ویرایش
                    </Button>
                    <Button
                      size="small"
                      startIcon={<ContentCopyOutlinedIcon fontSize="small" />}
                      onClick={() => handleDuplicate(form)}
                    >
                      نسخه جدید
                    </Button>
                    {form.status === "draft" && (
                      <Button size="small" color="error" onClick={() => handleDelete(form)}>
                        حذف
                      </Button>
                    )}
                  </Stack>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <NewFormDialog open={dialogOpen} onClose={() => setDialogOpen(false)} onCreated={loadForms} sites={sites} />
    </Box>
  );
}
