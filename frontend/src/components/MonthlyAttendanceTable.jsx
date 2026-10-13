import { useEffect, useRef, useState } from "react";
import {
  Box,
  Chip,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";

/**
 * جدول گزارش تردد ماهانه (مشترک بین «گزارش تردد ماهانه» شخصی و «تردد پرسنل من» سرپرست).
 * ورودی: report = پاسخ سرور { days, max_transits_in_month }.
 * هر روز ماه یک ردیف است و ترددها با شماره‌ی ترتیبی («تردد ۱»، «تردد ۲»، ...) نمایش داده می‌شوند؛
 * تعداد ستون‌های تردد پویا و برابر بیشترین تعداد تردد در روزهای همان ماه است.
 * روزهای تعطیل قرمز، غیبت زرد و مرخصی/ماموریت روزانه و ساعتی با چیپ مشخص می‌شوند.
 * جدول یک اسکرول‌بار افقی بالای خود دارد که با اسکرول خود جدول همگام است.
 * راهنمای رنگ‌ها فقط وقتی نمایش داده می‌شود که در این ماه غیبت/مرخصی/تعطیلی وجود دارد.
 */
// رنگ چیپ هر نوع غیبت: مرخصی (سبز)، ماموریت (آبی)، سایر (زرد)
const KIND_COLOR = { leave: "success", mission: "info", other: "warning" };
// چیپ وضعیت روز: تعطیل (قرمز) و غیبت (زرد = روز کاری گذشته بدون تردد و بدون مرخصی/ماموریت)
const STATUS_CHIPS = {
  holiday: { label: "تعطیل", color: "error" },
  absent: { label: "غیبت", color: "warning" },
  not_employed: { label: "قبل از استخدام", color: "default" }, // روزهای پیش از تاریخ استخدام
};

// تعداد دقیقه را به رشته‌ی «ساعت:دقیقه» تبدیل می‌کند (مثلاً 103 -> 1:43)
function formatMinutes(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h}:${String(m).padStart(2, "0")}`;
}

// متن چیپ/تولتیپ یک غیبت ساعتی: عنوان به همراه مدت در پرانتز
function hourlyText(mark) {
  return mark.minutes
    ? `${mark.label} (${formatMinutes(mark.minutes)})`
    : mark.label;
}

// استایل چیپ فشرده با متن قابل‌شکستن در چند خط، تا جدول در موبایل جا شود
const compactChipSx = {
  height: "auto",
  fontSize: { xs: "0.62rem", sm: "0.7rem" },
  "& .MuiChip-label": {
    px: 0.75,
    py: 0.25,
    whiteSpace: "normal",
    lineHeight: 1.35,
  },
};

export default function MonthlyAttendanceTable({ report }) {
  const theme = useTheme();
  const topScrollRef = useRef(null); // ظرف اسکرول‌بار افقی بالای جدول
  const tableScrollRef = useRef(null); // ظرف خود جدول (TableContainer)
  const [tableScrollWidth, setTableScrollWidth] = useState(0); // عرض قابل‌اسکرول جدول
  const isSyncingScroll = useRef(false); // جلوگیری از حلقه بی‌نهایت بین دو onScroll

  const transitColumnCount = report?.max_transits_in_month || 1; // حداقل یک ستون
  // ستون «وضعیت» فقط وقتی نمایش داده می‌شود که در این ماه واقعاً موردی باشد
  const hasAbsences = Boolean(
    report?.days?.some(
      (d) => d.day_status || (d.hourly_absences && d.hourly_absences.length),
    ),
  );

  // رنگ پس‌زمینه‌ی ردیف یک روز
  function rowBackground(day) {
    if (day.day_status === "not_employed")
      return alpha(theme.palette.text.disabled, 0.08);
    if (day.is_holiday) return "rgba(211, 47, 47, 0.08)";
    if (day.daily_absence)
      return alpha(theme.palette[KIND_COLOR[day.daily_absence.kind]].main, 0.1);
    if (day.day_status === "absent")
      return alpha(theme.palette.warning.main, 0.14);
    return undefined;
  }

  // بعد از هر رندر جدول، عرض واقعی قابل‌اسکرول را برای اسکرول‌بار بالایی اندازه می‌گیریم
  useEffect(() => {
    if (tableScrollRef.current) {
      setTableScrollWidth(tableScrollRef.current.scrollWidth);
    }
  }, [report, transitColumnCount]);

  function handleTopScroll() {
    if (isSyncingScroll.current) return;
    isSyncingScroll.current = true;
    if (tableScrollRef.current && topScrollRef.current) {
      tableScrollRef.current.scrollLeft = topScrollRef.current.scrollLeft;
    }
    isSyncingScroll.current = false;
  }

  function handleTableScroll() {
    if (isSyncingScroll.current) return;
    isSyncingScroll.current = true;
    if (tableScrollRef.current && topScrollRef.current) {
      topScrollRef.current.scrollLeft = tableScrollRef.current.scrollLeft;
    }
    isSyncingScroll.current = false;
  }

  if (!report) return null;

  return (
    <>
      {hasAbsences && (
        <Stack
          direction="row"
          spacing={1}
          flexWrap="wrap"
          useFlexGap
          sx={{ mb: 1.5 }}
        >
          <Chip size="small" color="success" variant="outlined" label="مرخصی" />
          <Chip size="small" color="info" variant="outlined" label="ماموریت" />
          <Chip size="small" color="error" variant="outlined" label="تعطیل" />
          <Chip size="small" color="warning" variant="outlined" label="غیبت" />
        </Stack>
      )}

      {/* اسکرول‌بار افقی بالای جدول: یک Box خالی هم‌عرض جدول */}
      <Box
        ref={topScrollRef}
        onScroll={handleTopScroll}
        sx={{ overflowX: "auto", overflowY: "hidden", mb: 0.5 }}
      >
        <Box sx={{ width: tableScrollWidth, height: 1 }} />
      </Box>
      <TableContainer
        ref={tableScrollRef}
        onScroll={handleTableScroll}
        component={Paper}
        variant="outlined"
        sx={{ borderRadius: 2 }}
      >
        <Table
          size="small"
          sx={{
            "& .MuiTableCell-root": {
              px: { xs: 0.5, sm: 1 },
              py: { xs: 0.5, sm: 0.75 },
              fontSize: { xs: "0.7rem", sm: "0.8rem" },
              whiteSpace: "nowrap",
            },
          }}
        >
          <TableHead>
            <TableRow>
              <TableCell>روز</TableCell>
              <TableCell>تاریخ</TableCell>
              {hasAbsences && <TableCell>وضعیت</TableCell>}
              {Array.from({ length: transitColumnCount }, (_, i) => (
                <TableCell key={i} align="center">
                  {`تردد ${i + 1}`}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {report.days.map((day) => (
              <TableRow
                key={day.date}
                hover
                sx={{ bgcolor: rowBackground(day) }}
              >
                <TableCell
                  sx={{
                    color: day.is_holiday ? "error.main" : undefined,
                    fontWeight: day.is_holiday ? 700 : undefined,
                  }}
                >
                  {day.weekday}
                </TableCell>
                <TableCell
                  sx={{
                    fontFamily: "monospace",
                    color: day.is_holiday ? "error.main" : undefined,
                    fontWeight: day.is_holiday ? 700 : undefined,
                  }}
                >
                  {/* در موبایل بدون سال (۰۶/۲۱) تا ستون باریک‌تر شود */}
                  <Box
                    component="span"
                    sx={{ display: { xs: "none", sm: "inline" } }}
                  >
                    {day.date}
                  </Box>
                  <Box
                    component="span"
                    sx={{ display: { xs: "inline", sm: "none" } }}
                  >
                    {day.date.slice(5)}
                  </Box>
                </TableCell>
                {hasAbsences && (
                  <TableCell
                    sx={{
                      "&&": { whiteSpace: "normal" },
                      minWidth: { xs: 84, sm: 120 },
                      maxWidth: 220,
                    }}
                  >
                    <Stack
                      direction="column"
                      spacing={0.5}
                      alignItems="flex-start"
                    >
                      {day.daily_absence ? (
                        <Chip
                          size="small"
                          color={KIND_COLOR[day.daily_absence.kind]}
                          label={day.daily_absence.label}
                          sx={compactChipSx}
                        />
                      ) : (
                        STATUS_CHIPS[day.day_status] && (
                          <Chip
                            size="small"
                            color={STATUS_CHIPS[day.day_status].color}
                            label={STATUS_CHIPS[day.day_status].label}
                            sx={compactChipSx}
                          />
                        )
                      )}
                      {(day.hourly_absences || []).map((mark, idx) => (
                        <Chip
                          key={idx}
                          size="small"
                          variant="outlined"
                          color={KIND_COLOR[mark.kind]}
                          label={hourlyText(mark)}
                          sx={compactChipSx}
                        />
                      ))}
                    </Stack>
                  </TableCell>
                )}
                {Array.from({ length: transitColumnCount }, (_, i) => {
                  const mark = day.transit_marks?.[i];
                  const cell = (
                    <TableCell
                      key={i}
                      align="center"
                      sx={{
                        fontFamily: "monospace",
                        color: mark
                          ? `${KIND_COLOR[mark.kind]}.main`
                          : day.is_holiday
                            ? "error.main"
                            : undefined,
                        fontWeight: mark ? 700 : undefined,
                      }}
                    >
                      {day.transits[i] || "—"}
                    </TableCell>
                  );
                  return mark ? (
                    <Tooltip key={i} title={hourlyText(mark)} arrow>
                      {cell}
                    </Tooltip>
                  ) : (
                    cell
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}
