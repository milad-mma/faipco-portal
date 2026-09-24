import { useEffect, useMemo, useState } from "react";
import { MenuItem, Stack, TextField } from "@mui/material";
import { gregorianToJalali, jalaliMonthLength, jalaliToGregorian, JALALI_MONTH_NAMES } from "../utils/jalaliDate";

/**
 * انتخاب‌گر تاریخ شمسی + ساعت: سه Dropdown برای روز/ماه/سال شمسی و یک فیلد ساعت:دقیقه.
 * value و onChange با شیء Date میلادی کار می‌کنند و فقط نمایش برای کاربر شمسی است.
 * ورودی: value، onChange، label، align ("center" = وسط‌چین)، showTime (فقط حالت عادی) و clearable.
 *
 * clearable: برای فیلترها؛ وقتی value خالی (null) است فیلدها خالی نمایش داده می‌شوند و هیچ تاریخی
 * خودکار انتخاب/ارسال نمی‌شود؛ onChange فقط وقتی روز، ماه و سال هر سه انتخاب شدند صدا زده می‌شود
 * و با null شدن value از طرف والد (حذف فیلتر) فیلدها هم خالی می‌شوند.
 * این کامپوننت فقط بین دو پیاده‌سازی ClearableJalaliDatePicker و FilledJalaliDateTimePicker انتخاب می‌کند.
 */
export default function JalaliDateTimePicker(props) {
  if (props.clearable) return <ClearableJalaliDatePicker {...props} />;
  return <FilledJalaliDateTimePicker {...props} />;
}

/**
 * حالت قابل‌پاک‌شدن (فیلتر): فقط تاریخ، بدون ساعت؛ فیلدها می‌توانند خالی باشند.
 * خروجی onChange: Date میلادی ساعت 00:00 روز انتخاب‌شده.
 */
function ClearableJalaliDatePicker({ value, onChange, label, align }) {
  const todayJalali = useMemo(() => gregorianToJalali(new Date()), []); // امروز شمسی برای بازه‌ی سال‌ها
  // تبدیل Date به اجزای شمسی؛ مقدار خالی = اجزای خالی
  const fromValue = (v) => (v ? gregorianToJalali(v) : { jy: "", jm: "", jd: "" });

  const [year, setYear] = useState(() => fromValue(value).jy);
  const [month, setMonth] = useState(() => fromValue(value).jm);
  const [day, setDay] = useState(() => fromValue(value).jd);

  // وقتی والد value را null کند (پاک کردن فیلتر)، فیلدها خالی می‌شوند
  useEffect(() => {
    if (!value) {
      setYear("");
      setMonth("");
      setDay("");
    }
  }, [value]);

  const dayCount = year && month ? jalaliMonthLength(year, month) : 31;
  const dayOptions = Array.from({ length: dayCount }, (_, i) => i + 1);

  // فقط وقتی هر سه بخش پر باشند، تاریخ میلادی را به والد می‌فرستد؛ روزِ بیش از طول ماه به آخرین روز ماه محدود می‌شود
  function emit(nextYear, nextMonth, nextDay) {
    if (!nextYear || !nextMonth || !nextDay) return;
    const safeDay = Math.min(nextDay, jalaliMonthLength(nextYear, nextMonth));
    if (safeDay !== nextDay) setDay(safeDay);
    onChange(jalaliToGregorian(nextYear, nextMonth, safeDay, 0, 0));
  }

  const centered = align === "center";
  const yearOptions = Array.from({ length: 11 }, (_, i) => todayJalali.jy - 5 + i); // ۵ سال قبل تا ۵ سال بعد از امسال
  if (year && !yearOptions.includes(year)) yearOptions.push(year); // سال مقدار فعلی اگر خارج از بازه باشد اضافه می‌شود
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
      {/* فیلدها با flex کش می‌آیند و در عرض کم (موبایل) به خط بعد می‌شکنند؛ useFlexGap فاصله را
            پس از شکستن خط هم درست نگه می‌دارد */}
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ width: "100%", maxWidth: 460 }}>
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
          sx={{ flex: "1 1 72px", minWidth: 72 }}
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
          sx={{ flex: "2 1 110px", minWidth: 110 }}
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
          sx={{ flex: "1 1 88px", minWidth: 88 }}
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

/**
 * حالت عادی: همیشه یک تاریخ معتبر دارد (مقدار اولیه value یا اکنون) و هر تغییر را فوراً گزارش می‌کند.
 * showTime=false فیلد ساعت را پنهان و ساعت را 00:00 می‌کند. خروجی onChange: Date میلادی.
 */
function FilledJalaliDateTimePicker({ value, onChange, label, showTime = true, align }) {
  // اجزای شمسی مقدار اولیه؛ فقط یک‌بار محاسبه می‌شود و تغییرات بعدی value نادیده گرفته می‌شوند
  const initialJalali = useMemo(() => gregorianToJalali(value || new Date()), []); // eslint-disable-line react-hooks/exhaustive-deps

  const [year, setYear] = useState(initialJalali.jy);
  const [month, setMonth] = useState(initialJalali.jm);
  const [day, setDay] = useState(initialJalali.jd);
  // ساعت به شکل "HH:MM"؛ مقدار اولیه از value یا زمان فعلی
  const [time, setTime] = useState(() => {
    if (!showTime) return "00:00";
    const d = value || new Date();
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  });

  const dayCount = jalaliMonthLength(year, month);
  const dayOptions = Array.from({ length: dayCount }, (_, i) => i + 1);

  // اگر روز انتخاب‌شده از تعداد روزهای ماه جدید بیشتر شد (مثلاً از اسفند
  // کبیسه به غیرکبیسه)، به آخرین روز معتبر برمی‌گردد
  useEffect(() => {
    if (day > dayCount) setDay(dayCount);
  }, [dayCount, day]);

  // با هر تغییر تاریخ یا ساعت، Date میلادی معادل به والد فرستاده می‌شود (شامل مقدار اولیه هنگام mount)
  useEffect(() => {
    const [hourStr, minuteStr] = time.split(":");
    const hour = Number(hourStr) || 0;
    const minute = Number(minuteStr) || 0;
    const safeDay = Math.min(day, dayCount);
    onChange(jalaliToGregorian(year, month, safeDay, hour, minute));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, month, day, time, dayCount]);

  // align="center": برچسب و فیلدها وسط‌چین می‌شوند؛ در غیر این صورت چینش پیش‌فرض
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
      {/* فیلدها با flex کش می‌آیند و در عرض کم (موبایل) به خط بعد می‌شکنند؛ useFlexGap فاصله را
            پس از شکستن خط هم درست نگه می‌دارد */}
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ width: "100%", maxWidth: 460 }}>
        <TextField select label="روز" size="small" value={day} onChange={(e) => setDay(Number(e.target.value))} sx={{ flex: "1 1 72px", minWidth: 72 }}>
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
          sx={{ flex: "2 1 110px", minWidth: 110 }}
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
          sx={{ flex: "1 1 88px", minWidth: 88 }}
        >
          {Array.from({ length: 11 }, (_, i) => initialJalali.jy - 5 + i).map((y) => (
            <MenuItem key={y} value={y}>
              {y}
            </MenuItem>
          ))}
        </TextField>
        {/* فیلد ساعت:دقیقه */}
        {showTime && (
          <TextField
            label="ساعت"
            size="small"
            type="time"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            sx={{ flex: "1 1 100px", minWidth: 100 }}
            InputLabelProps={{ shrink: true }}
          />
        )}
      </Stack>
    </Stack>
  );
}
