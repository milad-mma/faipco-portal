import { useMemo, useState } from "react";
import { Box, Button, IconButton, InputAdornment, MenuItem, Popover, Stack, TextField, Typography } from "@mui/material";
import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import { gregorianToJalali, jalaliMonthLength, jalaliToGregorian, JALALI_MONTH_NAMES } from "../utils/jalaliDate";
import { toPersianDigits } from "../utils/searchText";

/**
 * فیلد تاریخ شمسی با تقویم: کاربر تاریخ را فقط از تقویم انتخاب می‌کند (تایپ دستی ممکن نیست).
 * value و onChange با رشته‌ی «YYYY/MM/DD» (ارقام انگلیسی، همان قالب سرور) کار می‌کنند؛ پاک کردن → null.
 * ورودی: label، required، disableFuture (روزهای بعد از امروز غیرفعال)، minYear، clearable، size، helperText، error.
 */
const WEEKDAYS = ["ش", "ی", "د", "س", "چ", "پ", "ج"]; // شنبه تا جمعه

const pad = (n) => String(n).padStart(2, "0");
const fmt = (y, m, d) => `${y}/${pad(m)}/${pad(d)}`;

function parse(value) {
  const m = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/.exec(String(value || ""));
  return m ? { jy: Number(m[1]), jm: Number(m[2]), jd: Number(m[3]) } : null;
}

export default function JalaliCalendarField({
  value,
  onChange,
  label,
  required,
  disableFuture = false,
  minYear = 1300,
  clearable = true,
  size = "small",
  helperText,
  error,
  fullWidth = true,
}) {
  const today = useMemo(() => gregorianToJalali(new Date()), []);
  const selected = parse(value);
  const [anchor, setAnchor] = useState(null);
  const [view, setView] = useState(() => selected || today); // ماه/سال در حال نمایش

  function open(e) {
    setView(parse(value) || today);
    setAnchor(e.currentTarget);
  }

  function shiftMonth(delta) {
    let jm = view.jm + delta;
    let jy = view.jy;
    if (jm < 1) {
      jm = 12;
      jy -= 1;
    } else if (jm > 12) {
      jm = 1;
      jy += 1;
    }
    setView({ jy, jm });
  }

  const maxYear = disableFuture ? today.jy : today.jy + 10;
  const years = [];
  for (let y = maxYear; y >= minYear; y--) years.push(y);

  const daysInMonth = jalaliMonthLength(view.jy, view.jm);
  // روز هفته‌ی اول ماه؛ getDay: یکشنبه=۰ ← ستون شنبه=۰
  const firstCol = (jalaliToGregorian(view.jy, view.jm, 1).getDay() + 1) % 7;
  const cells = [...Array(firstCol).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)];
  const isFuture = (d) => view.jy > today.jy || (view.jy === today.jy && (view.jm > today.jm || (view.jm === today.jm && d > today.jd)));
  const canNext = !disableFuture || view.jy < today.jy || (view.jy === today.jy && view.jm < today.jm);

  return (
    <>
      <TextField
        fullWidth={fullWidth}
        size={size}
        label={label ? label + (required ? " *" : "") : undefined}
        value={selected ? toPersianDigits(fmt(selected.jy, selected.jm, selected.jd)) : ""}
        onClick={open}
        placeholder="انتخاب از تقویم"
        helperText={helperText}
        error={error}
        InputProps={{
          readOnly: true,
          sx: { cursor: "pointer", "& input": { cursor: "pointer" } },
          endAdornment: (
            <InputAdornment position="end">
              <CalendarMonthOutlinedIcon fontSize="small" color="action" />
            </InputAdornment>
          ),
        }}
      />
      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
        transformOrigin={{ vertical: "top", horizontal: "center" }}
      >
        <Box sx={{ p: 1.5, width: 300 }}>
          {/* سربرگ: ماه قبل/بعد و انتخاب سریع ماه و سال (برای تاریخ تولدهای دور) */}
          <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mb: 1 }}>
            <IconButton size="small" onClick={() => shiftMonth(-1)} disabled={view.jy <= minYear && view.jm === 1} aria-label="ماه قبل">
              <ChevronRightIcon />
            </IconButton>
            <TextField
              select
              size="small"
              value={view.jm}
              onChange={(e) => setView({ ...view, jm: Number(e.target.value) })}
              sx={{ flex: 1 }}
              SelectProps={{ MenuProps: { PaperProps: { sx: { maxHeight: 300 } } } }}
            >
              {JALALI_MONTH_NAMES.map((name, i) => (
                <MenuItem key={name} value={i + 1} disabled={disableFuture && view.jy === today.jy && i + 1 > today.jm}>
                  {name}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              size="small"
              value={view.jy}
              onChange={(e) => {
                const jy = Number(e.target.value);
                setView({ jy, jm: disableFuture && jy === today.jy ? Math.min(view.jm, today.jm) : view.jm });
              }}
              sx={{ width: 90 }}
              SelectProps={{ MenuProps: { PaperProps: { sx: { maxHeight: 300 } } } }}
            >
              {years.map((y) => (
                <MenuItem key={y} value={y}>
                  {toPersianDigits(y)}
                </MenuItem>
              ))}
            </TextField>
            <IconButton size="small" onClick={() => shiftMonth(1)} disabled={!canNext} aria-label="ماه بعد">
              <ChevronLeftIcon />
            </IconButton>
          </Stack>
          <Box sx={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 0.5, textAlign: "center" }}>
            {WEEKDAYS.map((w) => (
              <Typography key={w} variant="caption" color="text.secondary" fontWeight={700}>
                {w}
              </Typography>
            ))}
            {cells.map((d, i) => {
              if (d === null) return <Box key={`e${i}`} />;
              const isSelected = selected && selected.jy === view.jy && selected.jm === view.jm && selected.jd === d;
              const isToday = today.jy === view.jy && today.jm === view.jm && today.jd === d;
              const disabled = disableFuture && isFuture(d);
              return (
                <Button
                  key={d}
                  size="small"
                  disabled={disabled}
                  variant={isSelected ? "contained" : isToday ? "outlined" : "text"}
                  onClick={() => {
                    onChange(fmt(view.jy, view.jm, d));
                    setAnchor(null);
                  }}
                  sx={{ minWidth: 0, p: 0.5, borderRadius: "50%", aspectRatio: "1", fontWeight: isSelected ? 800 : 400 }}
                >
                  {toPersianDigits(d)}
                </Button>
              );
            })}
          </Box>
          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
            <Button
              size="small"
              onClick={() => {
                onChange(fmt(today.jy, today.jm, today.jd));
                setAnchor(null);
              }}
            >
              امروز
            </Button>
            <Box sx={{ flex: 1 }} />
            {clearable && selected && (
              <Button
                size="small"
                color="error"
                onClick={() => {
                  onChange(null);
                  setAnchor(null);
                }}
              >
                پاک کردن
              </Button>
            )}
          </Stack>
        </Box>
      </Popover>
    </>
  );
}
