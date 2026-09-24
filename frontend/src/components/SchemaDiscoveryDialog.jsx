/**
 * دیالوگ کشف ساختار دیتابیس یک سایت و پیشنهاد خودکار نگاشت (Mapping) ستون‌ها.
 * شامل ثابت‌های MAPPING_TYPES و CONCEPT_LABELS، کامپوننت داخلی TableSuggestionPanel و کامپوننت اصلی SchemaDiscoveryDialog.
 */
import { useEffect, useMemo, useState } from "react";
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
  TextField,
  Typography,
} from "@mui/material";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import AutoFixHighOutlinedIcon from "@mui/icons-material/AutoFixHighOutlined";
import { discoverSiteSchema, suggestMappingForSite } from "../api/sites";

/**
 * انواع نگاشت و مفاهیم (فیلدهای) موردنیاز هر کدام برای درخواست پیشنهاد (بر اساس نام ستون/نمونه داده).
 * این‌ها همان فیلدهای فرم‌های EmployeeMapping/AttendanceMapping در SiteSettingsPage.jsx هستند؛
 * شامل فیلدهای جدول اصلی پرسنل/تردد و فیلدهای جدول‌های جدا (مرجع، عکس، تقویم).
 * برای افزودن نوع نگاشت جدید کافی است یک ورودی اینجا اضافه شود (و اگر مفهوم کاملاً تازه است،
 * کلیدواژه‌هایش در app/services/mapping_suggestion_service.py).
 */
const MAPPING_TYPES = {
  employee: {
    label: "نگاشت پرسنل (فیلدهای اصلی همان جدول)",
    concepts: [
      "personnel_code", "national_code", "first_name", "last_name", "mobile", "email",
      "birth_date", "is_active", "department", "position",
    ],
  },
  attendance_single: {
    label: "نگاشت تردد - یک ستون تاریخ + یک ستون ساعت",
    concepts: ["personnel_code", "date", "time"],
  },
  attendance_enter_exit: {
    label: "نگاشت تردد - ستون‌های جدای ورود/خروج",
    concepts: ["personnel_code", "enter_date", "enter_time", "exit_date", "exit_time"],
  },
  department_lookup: {
    label: "جدول مرجع دپارتمان/واحد سازمانی (جدول جدا)",
    concepts: ["lookup_id", "lookup_name"],
  },
  position_lookup: {
    label: "جدول مرجع سمت شغلی (جدول جدا)",
    concepts: ["lookup_id", "lookup_name"],
  },
  photo: {
    label: "جدول عکس پرسنلی (جدول جدا)",
    concepts: ["photo_emp_no", "photo_thumbnail"],
  },
  calendar: {
    label: "جدول تقویم/تعطیلات - برای گزارش تردد (جدول جدا)",
    concepts: ["calendar_year", "calendar_month"],
  },
};

// برچسب فارسی هر مفهوم برای نمایش در فهرست پیشنهادها
const CONCEPT_LABELS = {
  personnel_code: "کد پرسنلی",
  national_code: "کد ملی",
  first_name: "نام",
  last_name: "نام خانوادگی",
  birth_date: "تاریخ تولد",
  is_active: "وضعیت فعال/غیرفعال",
  department: "واحد سازمانی (کد در جدول اصلی)",
  position: "سمت شغلی (کد در جدول اصلی)",
  lookup_id: "شناسه (در جدول مرجع)",
  lookup_name: "نام (در جدول مرجع)",
  photo_emp_no: "کد پرسنلی (در جدول عکس)",
  photo_thumbnail: "تصویر بندانگشتی",
  calendar_year: "سال شمسی",
  calendar_month: "ماه شمسی",
  email: "ایمیل",
  mobile: "موبایل",
  date: "تاریخ",
  time: "ساعت",
  enter_date: "تاریخ ورود",
  enter_time: "ساعت ورود",
  exit_date: "تاریخ خروج",
  exit_time: "ساعت خروج",
};

/**
 * پنل پیشنهاد نگاشت برای یک جدول مشخص.
 * ورودی: table (نام و ستون‌های جدول)، siteId و onApplySuggestion(mappingType, tableName, suggestions).
 * کاربر نوع نگاشت را انتخاب می‌کند، پیشنهاد هر مفهوم (ستون، میزان اطمینان، منبع) نمایش داده می‌شود و
 * اعمال روی فرم فقط با دکمه‌ی جداگانه و تأیید صریح مدیر انجام می‌شود؛ چیزی خودکار ذخیره نمی‌شود.
 */
function TableSuggestionPanel({ table, siteId, onApplySuggestion }) {
  const [mappingType, setMappingType] = useState("employee");  // کلید نوع نگاشت انتخاب‌شده از MAPPING_TYPES
  const [suggestions, setSuggestions] = useState(null);  // نتیجه‌ی پیشنهاد: { concept: {column, confidence, source} | null } یا null
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  // نام ستون‌های جدول و مفاهیم نوع نگاشت را برای سرور می‌فرستد و پیشنهادها را ذخیره می‌کند
  async function handleSuggest() {
    setError("");
    setSuggestions(null);
    setIsLoading(true);
    try {
      const columnNames = table.columns.map((c) => c.name);
      const result = await suggestMappingForSite(siteId, table.name, columnNames, MAPPING_TYPES[mappingType].concepts);
      setSuggestions(result);
    } catch (err) {
      setError(err.response?.data?.detail || "دریافت پیشنهاد با خطا مواجه شد.");
    } finally {
      setIsLoading(false);
    }
  }

  const hasAnySuggestion = suggestions && Object.values(suggestions).some((s) => s !== null);  // حداقل یک مفهوم پیشنهاد داشته باشد تا دکمه‌ی اعمال نمایش داده شود

  return (
    <Box sx={{ mt: 2, pt: 2, borderTop: "1px dashed", borderColor: "divider" }}>
      <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ display: "block", mb: 1 }}>
        پیشنهاد نگاشت برای این جدول (بر اساس نام ستون‌ها؛ برای مواردی که از نام مشخص نباشد، چند مقدار
        واقعی نمونه هم بررسی می‌شود - فقط پیشنهاد، نیاز به تأیید شما)
      </Typography>
      {/* انتخاب نوع نگاشت (با تغییرش پیشنهاد قبلی پاک می‌شود) و دکمه‌ی دریافت پیشنهاد */}
      <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
        <TextField
          select
          size="small"
          label="نوع نگاشت"
          value={mappingType}
          onChange={(e) => {
            setMappingType(e.target.value);
            setSuggestions(null);
          }}
          sx={{ minWidth: 280 }}
        >
          {Object.entries(MAPPING_TYPES).map(([value, { label }]) => (
            <MenuItem key={value} value={value}>
              {label}
            </MenuItem>
          ))}
        </TextField>
        <Button
          size="small"
          variant="outlined"
          startIcon={isLoading ? <CircularProgress size={14} /> : <AutoFixHighOutlinedIcon />}
          onClick={handleSuggest}
          disabled={isLoading}
        >
          دریافت پیشنهاد
        </Button>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mt: 1.5 }}>
          {error}
        </Alert>
      )}

      {/* فهرست پیشنهاد هر مفهوم و دکمه‌ی اعمال روی فرم */}
      {suggestions && (
        <Box sx={{ mt: 1.5 }}>
          <Stack spacing={0.5}>
            {Object.entries(suggestions).map(([concept, suggestion]) => (
              <Typography key={concept} variant="body2">
                {CONCEPT_LABELS[concept] || concept}:{" "}
                {suggestion ? (
                  <>
                    <Box component="span" sx={{ fontFamily: "monospace", fontWeight: 700 }}>
                      {suggestion.column}
                    </Box>{" "}
                    <Chip
                      size="small"
                      label={`اطمینان ${suggestion.confidence}`}
                      color={suggestion.confidence === "بالا" ? "success" : "warning"}
                    />
                    {suggestion.source === "نمونه داده" && (
                      <Chip size="small" variant="outlined" label="بر اساس نمونه داده" sx={{ mr: 0.5 }} />
                    )}
                  </>
                ) : (
                  <Typography component="span" variant="body2" color="text.secondary">
                    پیشنهادی پیدا نشد
                  </Typography>
                )}
              </Typography>
            ))}
          </Stack>
          {hasAnySuggestion && (
            <Button
              size="small"
              variant="contained"
              sx={{ mt: 1.5 }}
              onClick={() => onApplySuggestion(mappingType, table.name, suggestions)}
            >
              اعمال این پیشنهادها به فرم نگاشت
            </Button>
          )}
        </Box>
      )}
    </Box>
  );
}

/**
 * دیالوگ نمایش ساختار دیتابیس سایت (جدول‌ها، ستون‌ها، نوع داده‌ها و کلیدهای خارجی رسماً تعریف‌شده)؛
 * فقط فراداده خوانده می‌شود، نه داده‌ی واقعی. مدیر نام دقیق جدول/ستون‌ها را برای فرم‌های Mapping پیدا می‌کند
 * و می‌تواند با پیشنهاد خودکار فرم را پر کند.
 * ورودی: open، onClose، siteId و onApplySuggestion (پس از اعمال پیشنهاد، دیالوگ بسته می‌شود).
 */
export default function SchemaDiscoveryDialog({ open, onClose, siteId, onApplySuggestion }) {
  const [schema, setSchema] = useState(null);  // ساختار دریافتی: { tables: [{name, columns, foreign_keys}] } یا null
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [search, setSearch] = useState("");  // عبارت جست‌وجو در نام جدول/ستون

  // با هر بار باز شدن دیالوگ، وضعیت پاک و ساختار دیتابیس از سرور دریافت می‌شود
  useEffect(() => {
    if (!open) return;
    setSchema(null);
    setError("");
    setSearch("");
    setIsLoading(true);
    discoverSiteSchema(siteId)
      .then((data) => setSchema(data))
      .catch((err) => setError(err.response?.data?.detail || "کشف ساختار دیتابیس با خطا مواجه شد."))
      .finally(() => setIsLoading(false));
  }, [open, siteId]);

  // جدول‌هایی که نام خودشان یا یکی از ستون‌هایشان شامل عبارت جست‌وجو باشد
  const filteredTables = useMemo(() => {
    if (!schema) return [];
    const term = search.trim().toLowerCase();
    if (!term) return schema.tables;
    return schema.tables.filter(
      (t) => t.name.toLowerCase().includes(term) || t.columns.some((c) => c.name.toLowerCase().includes(term))
    );
  }, [schema, search]);

  // پیشنهاد را به والد می‌دهد و دیالوگ را می‌بندد
  function handleApplySuggestion(mappingType, tableName, suggestions) {
    onApplySuggestion(mappingType, tableName, suggestions);
    onClose();
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>ساختار دیتابیس این سایت</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <Typography variant="body2" color="text.secondary">
          فهرست کامل جدول‌ها و ستون‌های این دیتابیس - فقط خواندن اطلاعات ساختاری، بدون خواندن هیچ داده
          واقعی. از این لیست برای پیدا کردن نام دقیق جدول/ستون‌ها هنگام تنظیم Mapping استفاده کنید، یا از
          «دریافت پیشنهاد» برای پرشدن خودکار فرم (با تأیید خودتان) کمک بگیرید.
        </Typography>

        {/* وضعیت بارگذاری و خطا */}
        {isLoading && (
          <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
            <CircularProgress size={28} />
          </Box>
        )}

        {error && <Alert severity="error">{error}</Alert>}

        {schema && (
          <>
            {/* جست‌وجو، شمارش جدول‌ها و آکاردئون هر جدول */}
            <TextField
              size="small"
              label="جست‌وجوی نام جدول یا ستون"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              fullWidth
            />
            <Typography variant="caption" color="text.secondary">
              {filteredTables.length} از {schema.tables.length} جدول
            </Typography>

            {filteredTables.map((table) => (
              <Accordion key={table.name} disableGutters variant="outlined">
                {/* سربرگ آکاردئون: نام جدول، تعداد ستون‌ها و کلیدهای خارجی */}
                <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
                  <Stack direction="row" spacing={1.5} alignItems="center">
                    <Typography fontWeight={700} sx={{ fontFamily: "monospace" }}>
                      {table.name}
                    </Typography>
                    <Chip size="small" label={`${table.columns.length} ستون`} />
                    {table.foreign_keys.length > 0 && (
                      <Chip size="small" color="info" label={`${table.foreign_keys.length} کلید خارجی`} />
                    )}
                  </Stack>
                </AccordionSummary>
                <AccordionDetails>
                  {/* جدول ستون‌ها: نام، نوع داده (با طول) و Nullable */}
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell>ستون</TableCell>
                          <TableCell>نوع داده</TableCell>
                          <TableCell>Nullable</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {table.columns.map((col) => (
                          <TableRow key={col.name}>
                            <TableCell sx={{ fontFamily: "monospace" }}>{col.name}</TableCell>
                            <TableCell>
                              {col.data_type}
                              {col.max_length ? `(${col.max_length})` : ""}
                            </TableCell>
                            <TableCell>{col.nullable ? "بله" : "خیر"}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>

                  {/* فهرست کلیدهای خارجی رسمی جدول */}
                  {table.foreign_keys.length > 0 && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="caption" fontWeight={700} color="text.secondary">
                        کلیدهای خارجی (فقط روابط رسماً تعریف‌شده - ممکن است روابط منطقی دیگری هم وجود
                        داشته باشد که رسماً ثبت نشده‌اند)
                      </Typography>
                      <Stack spacing={0.5} sx={{ mt: 0.5 }}>
                        {table.foreign_keys.map((fk, idx) => (
                          <Typography key={idx} variant="caption" sx={{ fontFamily: "monospace" }}>
                            {fk.column} → {fk.references_table}.{fk.references_column}
                          </Typography>
                        ))}
                      </Stack>
                    </Box>
                  )}

                  {/* پنل پیشنهاد نگاشت برای همین جدول */}
                  <Divider sx={{ my: 1.5 }} />
                  <TableSuggestionPanel table={table} siteId={siteId} onApplySuggestion={handleApplySuggestion} />
                </AccordionDetails>
              </Accordion>
            ))}
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}
