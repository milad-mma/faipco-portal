import { useEffect, useState } from "react";
import {
  Alert,
  Autocomplete,
  Box,
  Chip,
  CircularProgress,
  MenuItem,
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

const LOG_TYPE_LABELS = {
  presence: "حضور دوره‌ای",
  check_in: "ورود",
  check_out: "خروج",
};
const PAGE_SIZE = 50;

export default function AttendanceReportsPage() {
  const [logs, setLogs] = useState(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [logType, setLogType] = useState("");
  const [selectedEmployee, setSelectedEmployee] = useState(null);

  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [employeeSearch, setEmployeeSearch] = useState("");

  useEffect(() => {
    setLogs(null);
    fetchAllAttendanceLogs({
      page,
      pageSize: PAGE_SIZE,
      employeeId: selectedEmployee?.id,
      logType: logType || undefined,
    }).then((data) => {
      setLogs(data.items);
      setTotal(data.total);
    });
  }, [page, logType, selectedEmployee]);

  useEffect(() => {
    fetchEmployees({ search: employeeSearch, pageSize: 20 }).then((data) => setEmployeeOptions(data.items || []));
  }, [employeeSearch]);

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        گزارش حضور و ورود/خروج GPS
      </Typography>
      <Alert severity="warning" icon={<ScienceOutlinedIcon />} sx={{ mb: 3 }}>
        این گزارش مربوط به قابلیت آزمایشی «حضور مبتنی بر GPS» است — فقط شامل پرسنلی می‌شود که در این
        آزمایش شرکت دارند، و جایگزین گزارش رسمی حضور و غیاب نیست.
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
        <TextField
          select
          label="نوع"
          size="small"
          value={logType}
          onChange={(e) => {
            setLogType(e.target.value);
            setPage(1);
          }}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value="">همه</MenuItem>
          <MenuItem value="presence">حضور دوره‌ای</MenuItem>
          <MenuItem value="check_in">ورود</MenuItem>
          <MenuItem value="check_out">خروج</MenuItem>
        </TextField>
      </Stack>

      {logs === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : logs.length === 0 ? (
        <Alert severity="info">هیچ رکوردی با این فیلترها پیدا نشد.</Alert>
      ) : (
        <>
          <TableContainer sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>پرسنل</TableCell>
                  <TableCell>نوع</TableCell>
                  <TableCell>سایت مطابق</TableCell>
                  <TableCell>فاصله</TableCell>
                  <TableCell>دقت GPS</TableCell>
                  <TableCell>داخل محدوده؟</TableCell>
                  <TableCell>زمان</TableCell>
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
                    <TableCell>
                      <Chip size="small" label={LOG_TYPE_LABELS[log.log_type] || log.log_type} />
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
    </Box>
  );
}
