// صفحه‌ی واحدهای سازمانی.
// فهرست همه‌ی واحدها (به همراه سایت و سرپرست فعلی) را در جدولی مرتب‌پذیر نشان می‌دهد
// و امکان جستجوی پرسنل و تعیین/تغییر سرپرست هر واحد را فراهم می‌کند.
import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Card,
  Chip,
  MenuItem,
  Snackbar,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TextField,
  Typography,
} from "@mui/material";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import {
  assignDepartmentSupervisor,
  fetchDepartments,
} from "../api/departments";
import { fetchSites } from "../api/sites";
import EmployeeSearchField from "../components/EmployeeSearchField";
import { monoFontSx } from "../theme";
import { sortRows } from "../utils/tableSort";

// ستون‌های مرتب‌پذیر جدول واحدها (key همان فیلد ردیف است)
const COLUMNS = [
  { key: "site_name", label: "سایت" },
  { key: "name", label: "واحد سازمانی" },
  { key: "code", label: "کد واحد" },
  { key: "supervisor_name", label: "سرپرست فعلی" },
];

// سلول تعیین سرپرست یک واحد: جستجوی پرسنل همان سایت با انتخابگر مشترک پرسنل و دکمه‌ی ذخیره.
// ورودی: واحد و تابع onSaved که پس از ذخیره با واحد به‌روزشده و پیام موفقیت صدا زده می‌شود.
function SupervisorCell({ department, onSaved }) {
  const [selected, setSelected] = useState(null); // گزینه‌ی انتخاب‌شده {id, label}؛ برای سرپرست فعلی یک placeholder با isPlaceholder
  const [isSaving, setIsSaving] = useState(false);

  // با تغییر واحد یا سرپرست، سرپرست فعلی به‌عنوان مقدار اولیه‌ی فیلد تنظیم می‌شود
  // (فقط برای نمایش نام؛ id آن یک مقدار نگهبان است و هرگز به سرور فرستاده نمی‌شود — ذخیره فقط با انتخاب شخص جدید فعال است)
  useEffect(() => {
    setSelected(
      department.supervisor_user_id
        ? {
            id: `current-supervisor-${department.id}`,
            label: department.supervisor_name || "—",
            isPlaceholder: true,
          }
        : null,
    );
  }, [
    department.id,
    department.supervisor_user_id,
    department.supervisor_name,
  ]);

  const hasPendingChange = selected && !selected.isPlaceholder; // فقط وقتی شخص جدیدی انتخاب شده ذخیره فعال است

  // سرپرست انتخاب‌شده را برای واحد ثبت می‌کند و نتیجه را به والد اطلاع می‌دهد
  async function handleSave() {
    if (!hasPendingChange) return;
    setIsSaving(true);
    try {
      const updated = await assignDepartmentSupervisor(
        department.id,
        selected.id,
      );
      onSaved(
        updated,
        `سرپرست واحد «${department.name}» با موفقیت به‌روزرسانی شد.`,
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 340 }}>
      {/* جست‌وجو فقط بین پرسنل سایتِ همین واحد؛ پاک‌کردن فیلد = بدون انتخاب (ذخیره غیرفعال) */}
      <EmployeeSearchField
        size="small"
        sx={{ flexGrow: 1, minWidth: 240 }}
        siteId={department.site_id}
        value={selected}
        onChange={(value) => setSelected(value)}
        placeholder={
          department.supervisor_user_id
            ? undefined
            : "بدون سرپرست — برای تعیین جستجو کنید"
        }
      />
      <Button
        size="small"
        variant="contained"
        startIcon={<SaveOutlinedIcon fontSize="small" />}
        disabled={!hasPendingChange || isSaving}
        onClick={handleSave}
      >
        {isSaving ? "..." : "ذخیره"}
      </Button>
    </Box>
  );
}

// کامپوننت صفحه‌ی واحدهای سازمانی؛ ورودی ندارد.
// واحدها و سایت‌ها را بارگذاری می‌کند و جدول مرتب‌پذیر را با سلول تعیین سرپرست رندر می‌کند.
export default function DepartmentsPage() {
  const [departments, setDepartments] = useState([]);
  const [sites, setSites] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [order, setOrder] = useState("asc");
  const [orderBy, setOrderBy] = useState(null); // کلید ستون مرتب‌سازی؛ null = بدون مرتب‌سازی
  const [snackbar, setSnackbar] = useState(""); // متن پیام Snackbar؛ خالی = بسته
  const [siteFilter, setSiteFilter] = useState(""); // فیلتر سایت؛ "" = همه‌ی سایت‌ها

  useEffect(() => {
    // بارگذاری اولیه‌ی سایت‌ها و واحدها
    fetchSites().then(setSites);
    loadDepartments();
  }, []);

  // فهرست واحدها را از سرور می‌گیرد و در state می‌گذارد
  function loadDepartments() {
    setIsLoading(true);
    return fetchDepartments()
      .then(setDepartments)
      .finally(() => setIsLoading(false));
  }

  // کلیک روی سرستون: جهت مرتب‌سازی همان ستون را برعکس می‌کند یا ستون جدید را صعودی مرتب می‌کند
  function handleSort(columnKey) {
    if (orderBy === columnKey) {
      setOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setOrderBy(columnKey);
      setOrder("asc");
    }
  }

  // واحد به‌روزشده را در فهرست جایگزین می‌کند و پیام موفقیت را نشان می‌دهد
  function handleSupervisorSaved(updatedDepartment, message) {
    setDepartments((prev) =>
      prev.map((d) => (d.id === updatedDepartment.id ? updatedDepartment : d)),
    );
    setSnackbar(message);
  }

  // نگاشت شناسه‌ی سایت به نام سایت
  const siteNameById = useMemo(
    () => Object.fromEntries(sites.map((s) => [s.id, s.name])),
    [sites],
  );

  // افزودن نام سایت به هر ردیف و مرتب‌سازی ردیف‌ها
  const rows = departments
    .filter((dept) => siteFilter === "" || dept.site_id === siteFilter)
    .map((dept) => ({
      ...dept,
      site_name: siteNameById[dept.site_id] || null,
    }));
  const sortedRows = sortRows(rows, order, orderBy);

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" fontWeight={700}>
          واحدهای سازمانی
        </Typography>
        <Typography variant="body2" color="text.secondary">
          فهرست همه‌ی واحدهای سازمانی به همراه سرپرست هر واحد. برای واحدهایی که
          هنوز سرپرست ندارند، از بین پرسنل جستجو کرده و انتخاب کنید؛ برای تغییر
          سرپرست فعلی نیز کافی است شخص جدید را انتخاب و ذخیره کنید.
        </Typography>
      </Box>

      {/* فیلتر سایت (فقط وقتی بیش از یک سایت هست) */}
      {sites.length > 1 && (
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ xs: "stretch", sm: "flex-end" }} sx={{ mb: 2 }}>
          <TextField
            select
            size="small"
            label="سایت"
            value={siteFilter}
            onChange={(e) => setSiteFilter(e.target.value === "" ? "" : Number(e.target.value))}
            sx={{ minWidth: 220 }}
          >
            <MenuItem value="">همه‌ی سایت‌ها</MenuItem>
            {sites.map((site) => (
              <MenuItem key={site.id} value={site.id}>
                {site.name}
              </MenuItem>
            ))}
          </TextField>
          <Typography variant="body2" color="text.secondary" sx={{ pb: { sm: 1 } }}>
            {rows.length.toLocaleString("fa-IR")} واحد
          </Typography>
        </Stack>
      )}

      {/* جدول واحدها */}
      <Card variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                {COLUMNS.map((col) => (
                  <TableCell key={col.key}>
                    <TableSortLabel
                      active={orderBy === col.key}
                      direction={orderBy === col.key ? order : "asc"}
                      onClick={() => handleSort(col.key)}
                    >
                      {col.label}
                    </TableSortLabel>
                  </TableCell>
                ))}
                <TableCell>تغییر سرپرست</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {/* ردیف خالی وقتی واحدی وجود ندارد */}
              {!isLoading && sortedRows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={COLUMNS.length + 1}>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ py: 3, textAlign: "center" }}
                    >
                      هیچ واحد سازمانی‌ای یافت نشد.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {sortedRows.map((dept) => (
                <TableRow key={dept.id} hover>
                  <TableCell>{dept.site_name || dept.site_id}</TableCell>
                  <TableCell>{dept.name}</TableCell>
                  <TableCell sx={monoFontSx}>{dept.code}</TableCell>
                  <TableCell>
                    {dept.supervisor_user_id ? (
                      <Chip
                        size="small"
                        color="success"
                        variant="outlined"
                        label={dept.supervisor_name || "—"}
                      />
                    ) : (
                      <Chip
                        size="small"
                        color="default"
                        variant="outlined"
                        label="بدون سرپرست"
                      />
                    )}
                  </TableCell>
                  <TableCell>
                    <SupervisorCell
                      department={dept}
                      onSaved={handleSupervisorSaved}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      <Snackbar
        open={Boolean(snackbar)}
        autoHideDuration={4000}
        onClose={() => setSnackbar("")}
        message={snackbar}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      />
    </Box>
  );
}
