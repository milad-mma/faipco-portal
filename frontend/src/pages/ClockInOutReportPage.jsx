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
import LoginOutlinedIcon from "@mui/icons-material/LoginOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import { fetchAllAttendanceLogs } from "../api/attendance";
import { fetchEmployees } from "../api/employees";
import { monoFontSx } from "../theme";

const LOG_TYPE_META = {
  check_in: { label: "ورود", color: "success", icon: <LoginOutlinedIcon fontSize="small" /> },
  check_out: { label: "خروج", color: "default", icon: <LogoutOutlinedIcon fontSize="small" /> },
};
const PAGE_SIZE = 50;

export default function ClockInOutReportPage() {
  const [logs, setLogs] = useState(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedEmployee, setSelectedEmployee] = useState(null);

  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [employeeSearch, setEmployeeSearch] = useState("");

  useEffect(() => {
    setLogs(null);
    // چون این گزارش هم «ورود» هم «خروج» را با هم می‌خواهد (نه فقط یکی)، دو
    // درخواست جدا می‌زنیم و نتیجه را با هم ترکیب می‌کنیم — سرور فقط یک
    // log_type در هر درخواست قبول می‌کند.
    Promise.all([
      fetchAllAttendanceLogs({ page: 1, pageSize: 500, employeeId: selectedEmployee?.id, logType: "check_in" }),
      fetchAllAttendanceLogs({ page: 1, pageSize: 500, employeeId: selectedEmployee?.id, logType: "check_out" }),
    ]).then(([inData, outData]) => {
      const combined = [...inData.items, ...outData.items].sort(
        (a, b) => new Date(b.created_at) - new Date(a.created_at)
      );
      const start = (page - 1) * PAGE_SIZE;
      setLogs(combined.slice(start, start + PAGE_SIZE));
      setTotal(inData.total + outData.total);
    });
  }, [page, selectedEmployee]);

  useEffect(() => {
    fetchEmployees({ search: employeeSearch, pageSize: 20 }).then((data) => setEmployeeOptions(data.items || []));
  }, [employeeSearch]);

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        گزارش ثبت ورود و خروج
      </Typography>
      <Alert severity="warning" icon={<ScienceOutlinedIcon />} sx={{ mb: 3 }}>
        این قابلیت آزمایشی است. ثبت ورود/خروج رسمی همچنان باید از طریق دستگاه‌های تعبیه‌شده در
        کارخانه انجام شود — این فقط ثبت‌های صریحی است که خودِ پرسنل از داخل اپ زده‌اند.
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
                  <TableCell>نوع</TableCell>
                  <TableCell>سایت مطابق</TableCell>
                  <TableCell>فاصله</TableCell>
                  <TableCell>زمان</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {logs.map((log) => {
                  const meta = LOG_TYPE_META[log.log_type] || { label: log.log_type, color: "default" };
                  return (
                    <TableRow key={log.id}>
                      <TableCell>
                        <Typography variant="body2">{log.employee_name}</Typography>
                        <Typography variant="caption" color="text.secondary" sx={monoFontSx}>
                          {log.personnel_code}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip size="small" color={meta.color} icon={meta.icon} label={meta.label} />
                      </TableCell>
                      <TableCell>{log.matched_site_name || "—"}</TableCell>
                      <TableCell sx={monoFontSx}>
                        {log.distance_meters != null ? `${Math.round(log.distance_meters)} متر` : "—"}
                      </TableCell>
                      <TableCell sx={monoFontSx}>{new Date(log.created_at).toLocaleString("fa-IR")}</TableCell>
                    </TableRow>
                  );
                })}
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
