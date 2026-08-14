import { useEffect, useState } from "react";
import {
  Alert,
  Autocomplete,
  Box,
  Chip,
  CircularProgress,
  Pagination,
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
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import { fetchAllAttendanceLogs } from "../api/attendance";
import { fetchEmployees } from "../api/employees";
import { monoFontSx } from "../theme";

const PAGE_SIZE = 50;

export default function PresenceReportPage() {
  const [logs, setLogs] = useState(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedEmployee, setSelectedEmployee] = useState(null);

  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [employeeSearch, setEmployeeSearch] = useState("");

  useEffect(() => {
    setLogs(null);
    fetchAllAttendanceLogs({
      page,
      pageSize: PAGE_SIZE,
      employeeId: selectedEmployee?.id,
      logType: "presence",
    }).then((data) => {
      setLogs(data.items);
      setTotal(data.total);
    });
  }, [page, selectedEmployee]);

  useEffect(() => {
    fetchEmployees({ search: employeeSearch, pageSize: 20 }).then((data) => setEmployeeOptions(data.items || []));
  }, [employeeSearch]);

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        گزارش پرسنل آنلاین در محدوده کارخانه
      </Typography>
      <Alert severity="warning" icon={<ScienceOutlinedIcon />} sx={{ mb: 1.5 }}>
        این گزارش «آزمایشی» است — پایین همین صفحه، توضیح کامل نحوه کار این مانیتورینگ آمده.
      </Alert>
      <Alert severity="info" sx={{ mb: 3 }}>
        هر ردیف یعنی: «این پرسنل، در این لحظه، اپ را باز داشته و موقعیتش چک شده» — نه اینکه پیوسته
        آنلاین بوده. فقط شامل پرسنلی می‌شود که در آزمایش «ثبت ورود/خروج GPS» شرکت دارند.
      </Alert>

      <Stack direction="row" spacing={2} sx={{ mb: 3 }} flexWrap="wrap" rowGap={2}>
        <Autocomplete
          sx={{ minWidth: 260 }}
          options={employeeOptions}
          getOptionLabel={(o) => `${o.first_name} ${o.last_name} (${o.personnel_code})`}
          value={selectedEmployee}
          onChange={(_, value) => {
            setSelectedEmployee(value);
            setPage(1);
          }}
          onInputChange={(_, value) => setEmployeeSearch(value)}
          renderInput={(params) => <TextField {...params} label="فیلتر بر اساس پرسنل" size="small" />}
          isOptionEqualToValue={(o, v) => o.id === v.id}
        />
      </Stack>

      {logs === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : logs.length === 0 ? (
        <Alert severity="info">هیچ رکوردی پیدا نشد.</Alert>
      ) : (
        <>
          <TableContainer sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>پرسنل</TableCell>
                  <TableCell>سایت مطابق</TableCell>
                  <TableCell>فاصله</TableCell>
                  <TableCell>دقت GPS</TableCell>
                  <TableCell>داخل محدوده؟</TableCell>
                  <TableCell>زمان چک</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell>
                      <Typography variant="body2">{log.employee_name}</Typography>
                      <Typography variant="caption" color="text.secondary" sx={monoFontSx}>
                        {log.personnel_code}
                      </Typography>
                    </TableCell>
                    <TableCell>{log.matched_site_name || "—"}</TableCell>
                    <TableCell sx={monoFontSx}>
                      {log.distance_meters != null ? `${Math.round(log.distance_meters)} متر` : "—"}
                    </TableCell>
                    <TableCell sx={monoFontSx}>
                      {log.accuracy_meters != null ? `±${Math.round(log.accuracy_meters)} متر` : "—"}
                    </TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        color={log.is_within_geofence ? "success" : "error"}
                        label={log.is_within_geofence ? "بله" : "خیر"}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell sx={monoFontSx}>{new Date(log.created_at).toLocaleString("fa-IR")}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {total > PAGE_SIZE && (
            <Stack alignItems="center" sx={{ mt: 3 }}>
              <Pagination
                count={Math.ceil(total / PAGE_SIZE)}
                page={page}
                onChange={(_, value) => setPage(value)}
                color="primary"
              />
            </Stack>
          )}
        </>
      )}

      <Box sx={{ mt: 4, p: 2.5, border: "1px dashed", borderColor: "divider", borderRadius: 2 }}>
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
          دقیقاً چطور «آنلاین‌بودن» چک می‌شود؟
        </Typography>
        <Typography variant="body2" color="text.secondary" component="div">
          <ul style={{ margin: 0, paddingInlineStart: 20 }}>
            <li>فقط وقتی مرورگر/اپ پرسنل واقعاً باز باشد (نه در پس‌زمینه کامل بسته)</li>
            <li>فقط برای پرسنلی که در آزمایش شرکت دارند (نه همه)</li>
            <li>هر ۱۰ دقیقه یک‌بار، یک عکس لحظه‌ای از موقعیت گرفته و اینجا ثبت می‌شود</li>
            <li>هیچ راهی برای تشخیص «همین الان آنلاینه یا نه» به‌صورت زنده وجود ندارد — این یک لاگ تاریخچه‌ای است، نه یک صفحه Real-time</li>
          </ul>
        </Typography>
      </Box>
    </Box>
  );
}
