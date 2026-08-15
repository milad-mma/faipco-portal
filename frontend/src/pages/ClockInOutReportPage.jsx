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
import JalaliMonthYearFilter from "../components/JalaliMonthYearFilter";
import { groupLogsByDay } from "../utils/attendanceGrouping";
import { monoFontSx } from "../theme";

const PAGE_SIZE = 50;

export default function ClockInOutReportPage() {
  const [groupedRows, setGroupedRows] = useState(null);
  const [page, setPage] = useState(1);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [period, setPeriod] = useState({ year: null, month: null }); // null یعنی هنوز از سرور نگرفتیم (ماه جاری پیش‌فرض)

  const [employeeOptions, setEmployeeOptions] = useState([]);
  const [employeeSearch, setEmployeeSearch] = useState("");

  useEffect(() => {
    setGroupedRows(null);
    // چون این گزارش هم «ورود» هم «خروج» را با هم می‌خواهد (نه فقط یکی)، دو
    // درخواست جدا می‌زنیم و نتیجه را با هم ترکیب می‌کنیم — سرور فقط یک
    // log_type در هر درخواست قبول می‌کند. بعد، ورود/خروج هر پرسنل در هر
    // روز در یک ردیف واحد ترکیب می‌شود.
    Promise.all([
      fetchAllAttendanceLogs({
        page: 1,
        pageSize: 1000,
        employeeId: selectedEmployee?.id,
        logType: "check_in",
        year: period.year,
        month: period.month,
      }),
      fetchAllAttendanceLogs({
        page: 1,
        pageSize: 1000,
        employeeId: selectedEmployee?.id,
        logType: "check_out",
        year: period.year,
        month: period.month,
      }),
    ]).then(([inData, outData]) => {
      const combined = groupLogsByDay([...inData.items, ...outData.items]);
      setGroupedRows(combined);
      // اولین بار (بدون year/month)، مقدار پیش‌فرضِ ماه جاری را از سرور می‌گیریم
      setPeriod({ year: inData.year, month: inData.month });
    });
  }, [page, selectedEmployee, period.year, period.month]);

  useEffect(() => {
    fetchEmployees({ search: employeeSearch, pageSize: 20 }).then((data) => setEmployeeOptions(data.items || []));
  }, [employeeSearch]);

  const pageRows = groupedRows ? groupedRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE) : null;

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        گزارش ثبت ورود و خروج
      </Typography>
      <Alert severity="warning" icon={<ScienceOutlinedIcon />} sx={{ mb: 3 }}>
        این قابلیت آزمایشی است. ثبت ورود/خروج رسمی همچنان باید از طریق دستگاه‌های تعبیه‌شده در
        کارخانه انجام شود — این فقط ثبت‌های صریحی است که خودِ پرسنل از داخل اپ زده‌اند.
      </Alert>

      <Stack direction="row" spacing={2} sx={{ mb: 3 }} flexWrap="wrap" rowGap={2} alignItems="center">
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
        <JalaliMonthYearFilter
          year={period.year}
          month={period.month}
          onChange={(next) => {
            setPeriod(next);
            setPage(1);
          }}
          disabled={groupedRows === null}
        />
      </Stack>

      {groupedRows === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : groupedRows.length === 0 ? (
        <Alert severity="info">هیچ رکوردی پیدا نشد.</Alert>
      ) : (
        <>
          <TableContainer sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>پرسنل</TableCell>
                  <TableCell>تاریخ</TableCell>
                  <TableCell>ورود/خروج‌ها</TableCell>
                  <TableCell>سایت مطابق</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {pageRows.map((row) => (
                  <TableRow key={row.key}>
                    <TableCell>
                      <Typography variant="body2">{row.employeeName}</Typography>
                      <Typography variant="caption" color="text.secondary" sx={monoFontSx}>
                        {row.personnelCode}
                      </Typography>
                    </TableCell>
                    <TableCell sx={monoFontSx}>{row.dateLabel}</TableCell>
                    <TableCell>
                      <Stack spacing={0.75}>
                        {row.sessions.map((session, sessionIndex) => (
                          <Stack key={sessionIndex} direction="row" spacing={0.5}>
                            {session.checkIn ? (
                              <Chip
                                size="small"
                                color="success"
                                icon={<LoginOutlinedIcon fontSize="small" />}
                                label={new Date(session.checkIn.created_at).toLocaleTimeString("fa-IR", {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              />
                            ) : (
                              <Chip size="small" variant="outlined" label="بدون ورود" />
                            )}
                            {session.checkOut ? (
                              <Chip
                                size="small"
                                icon={<LogoutOutlinedIcon fontSize="small" />}
                                label={new Date(session.checkOut.created_at).toLocaleTimeString("fa-IR", {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}
                              />
                            ) : (
                              <Chip size="small" variant="outlined" label="بدون خروج" />
                            )}
                          </Stack>
                        ))}
                      </Stack>
                    </TableCell>
                    <TableCell>
                      {row.sessions[0]?.checkIn?.matched_site_name || row.sessions[0]?.checkOut?.matched_site_name || "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {groupedRows.length > PAGE_SIZE && (
            <Stack alignItems="center" sx={{ mt: 3 }}>
              <Pagination
                count={Math.ceil(groupedRows.length / PAGE_SIZE)}
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
