import { useEffect, useMemo, useState } from "react";
import { MenuItem, Stack, TextField } from "@mui/material";
import { gregorianToJalali, jalaliMonthLength, jalaliToGregorian, JALALI_MONTH_NAMES } from "../utils/jalaliDate";

/**
 * انتخاب‌گر تاریخ (شمسی) + ساعت — سه Dropdown برای روز/ماه/سال شمسی، به‌علاوه
 * یک فیلد ساعت:دقیقه. value و onChange با شیء Date میلادی کار می‌کنند (تا
 * بقیه کد، مثل ارسال به سرور، تغییری نکند) — فقط نمایش برای کاربر شمسی است.
 *
 * clearable: برای فیلترها - وقتی value خالی (null) است، فیلدها خالی نمایش
 * داده می‌شوند و هیچ تاریخی (مثلاً امروز) خودکار انتخاب/ارسال نمی‌شود؛ فقط
 * وقتی روز، ماه و سال هر سه انتخاب شدند onChange صدا زده می‌شود. اگر والد
 * value را null کند (حذف فیلتر)، فیلدها هم خالی می‌شوند.
 */
export default function JalaliDateTimePicker(props) {
  if (props.clearable) return <ClearableJalaliDatePicker {...props} />;
  return <FilledJalaliDateTimePicker {...props} />;
}

function ClearableJalaliDatePicker({ value, onChange, label, align }) {
  const todayJalali = useMemo(() => gregorianToJalali(new Date()), []);
  const fromValue = (v) => (v ? gregorianToJalali(v) : { jy: "", jm: "", jd: "" });

  const [year, setYear] = useState(() => fromValue(value).jy);
  const [month, setMonth] = useState(() => fromValue(value).jm);
  const [day, setDay] = useState(() => fromValue(value).jd);

  // والد فیلتر را پاک کرد ← فیلدها خالی شوند
  useEffect(() => {
    if (!value) {
      setYear("");
      setMonth("");
      setDay("");
    }
  }, [value]);

  const dayCount = year && month ? jalaliMonthLength(year, month) : 31;
  const dayOptions = Array.from({ length: dayCount }, (_, i) => i + 1);

  function emit(nextYear, nextMonth, nextDay) {
    if (!nextYear || !nextMonth || !nextDay) return;
    const safeDay = Math.min(nextDay, jalaliMonthLength(nextYear, nextMonth));
    if (safeDay !== nextDay) setDay(safeDay);
    onChange(jalaliToGregorian(nextYear, nextMonth, safeDay, 0, 0));
  }

  const centered = align === "center";
  const yearOptions = Array.from({ length: 11 }, (_, i) => todayJalali.jy - 5 + i);
  if (year && !yearOptions.includes(year)) yearOptions.push(year);
  return (
    <Stack
      spacing={1.5}
      alignItems={centered ? "center" : undefined}
      sx={centered ? { "& .MuiSelect-select": { textAlign: "center" } } : undefined}
    >
      {label && (
        <Stack direction="row" sx={{ color: "text.secondary", fontSize: 13 }}>
          {label}
        </Stack>
      )}
      <Stack direction="row" spacing={1}>
        <TextField
          select
          label="روز"
          size="small"
          value={day}
          onChange={(e) => {
            const v = Number(e.target.value);
            setDay(v);
            emit(year, month, v);
          }}
          sx={{ minWidth: 80 }}
        >
          {dayOptions.map((d) => (
            <MenuItem key={d} value={d}>
              {d}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          label="ماه"
          size="small"
          value={month}
          onChange={(e) => {
            const v = Number(e.target.value);
            setMonth(v);
            emit(year, v, day);
          }}
          sx={{ minWidth: 130 }}
        >
          {JALALI_MONTH_NAMES.map((name, i) => (
            <MenuItem key={name} value={i + 1}>
              {name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          label="سال"
          size="small"
          value={year}
          onChange={(e) => {
            const v = Number(e.target.value);
            setYear(v);
            emit(v, month, day);
          }}
          sx={{ minWidth: 100 }}
        >
          {yearOptions.map((y) => (
            <MenuItem key={y} value={y}>
              {y}
            </MenuItem>
          ))}
        </TextField>
      </Stack>
    </Stack>
  );
}

function FilledJalaliDateTimePicker({ value, onChange, label, showTime = true, align }) {
  const initialJalali = useMemo(() => gregorianToJalali(value || new Date()), []); // eslint-disable-line react-hooks/exhaustive-deps

  const [year, setYear] = useState(initialJalali.jy);
  const [month, setMonth] = useState(initialJalali.jm);
  const [day, setDay] = useState(initialJalali.jd);
  const [time, setTime] = useState(() => {
    if (!showTime) return "00:00";
    const d = value || new Date();
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  });

  const dayCount = jalaliMonthLength(year, month);
  const dayOptions = Array.from({ length: dayCount }, (_, i) => i + 1);

  useEffect(() => {
    // اگر روز انتخاب‌شده از تعداد روزهای ماه جدید بیشتر شد (مثلاً از اسفند
    // کبیسه به غیرکبیسه)، به آخرین روز معتبر برگرد
    if (day > dayCount) setDay(dayCount);
  }, [dayCount, day]);

  useEffect(() => {
    const [hourStr, minuteStr] = time.split(":");
    const hour = Number(hourStr) || 0;
    const minute = Number(minuteStr) || 0;
    const safeDay = Math.min(day, dayCount);
    onChange(jalaliToGregorian(year, month, safeDay, hour, minute));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, month, day, time, dayCount]);

  // align="center": برچسب و فیلدها وسط‌چین (پیش‌فرض همان چینش قبلی)
  const centered = align === "center";
  return (
    <Stack
      spacing={1.5}
      alignItems={centered ? "center" : undefined}
      sx={centered ? { "& .MuiSelect-select": { textAlign: "center" } } : undefined}
    >
      {label && (
        <Stack direction="row" sx={{ color: "text.secondary", fontSize: 13 }}>
          {label}
        </Stack>
      )}
      <Stack direction="row" spacing={1}>
        <TextField select label="روز" size="small" value={day} onChange={(e) => setDay(Number(e.target.value))} sx={{ minWidth: 80 }}>
          {dayOptions.map((d) => (
            <MenuItem key={d} value={d}>
              {d}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          label="ماه"
          size="small"
          value={month}
          onChange={(e) => setMonth(Number(e.target.value))}
          sx={{ minWidth: 130 }}
        >
          {JALALI_MONTH_NAMES.map((name, i) => (
            <MenuItem key={name} value={i + 1}>
              {name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          label="سال"
          size="small"
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
          sx={{ minWidth: 100 }}
        >
          {Array.from({ length: 11 }, (_, i) => initialJalali.jy - 5 + i).map((y) => (
            <MenuItem key={y} value={y}>
              {y}
            </MenuItem>
          ))}
        </TextField>
        {showTime && (
          <TextField
            label="ساعت"
            size="small"
            type="time"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            sx={{ minWidth: 110 }}
            InputLabelProps={{ shrink: true }}
          />
        )}
      </Stack>
    </Stack>
  );
}
