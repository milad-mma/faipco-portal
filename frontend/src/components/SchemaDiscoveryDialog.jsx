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
import { discoverSiteSchema } from "../api/sites";

/**
 * نمایش کامل ساختار دیتابیس این سایت (جدول‌ها، ستون‌ها، نوع‌داده‌ها،
 * کلیدهای خارجی رسماً تعریف‌شده) - فقط خواندن فراداده، بدون هیچ داده
 * واقعی یا نوشتن. هدف: مدیر بدون باز کردن ابزار جدا (SSMS/pgAdmin/...)
 * بتواند نام دقیق جدول/ستون‌ها را برای فرم‌های Mapping پیدا کند.
 */
export default function SchemaDiscoveryDialog({ open, onClose, siteId }) {
  const [schema, setSchema] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [search, setSearch] = useState("");

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

  const filteredTables = useMemo(() => {
    if (!schema) return [];
    const term = search.trim().toLowerCase();
    if (!term) return schema.tables;
    return schema.tables.filter(
      (t) => t.name.toLowerCase().includes(term) || t.columns.some((c) => c.name.toLowerCase().includes(term))
    );
  }, [schema, search]);

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>ساختار دیتابیس این سایت</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <Typography variant="body2" color="text.secondary">
          فهرست کامل جدول‌ها و ستون‌های این دیتابیس - فقط خواندن اطلاعات ساختاری، بدون خواندن هیچ داده
          واقعی. از این لیست برای پیدا کردن نام دقیق جدول/ستون‌ها هنگام تنظیم Mapping استفاده کنید.
        </Typography>

        {isLoading && (
          <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
            <CircularProgress size={28} />
          </Box>
        )}

        {error && <Alert severity="error">{error}</Alert>}

        {schema && (
          <>
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
