import { useEffect, useRef, useState } from "react";
import { Autocomplete, Stack, TextField, Typography } from "@mui/material";
import { fetchEmployees } from "../api/employees";
import { EMPLOYEE_SEARCH_PLACEHOLDER } from "./SearchField";

/**
 * انتخابگر پرسنل یک‌شکل با جست‌وجوی زنده‌ی سمت سرور (آجاکس، تأخیر ۳۰۰ms، نادیده‌گرفتن پاسخ دیررس).
 * همه‌ی جاهایی که پرسنل انتخاب می‌شود (اطلاعیه، واحدها، گزارش تردد/حضور، ساختارها، وام، مساعده) از همین استفاده می‌کنند.
 *
 * ورودی:
 * - fetcher(q) → Promise<[{id, label, disabled_reason?}]> (اختیاری؛ پیش‌فرض: GET /employees با siteId/departmentIds)
 * - siteId، departmentIds: فقط برای fetcher پیش‌فرض (جست‌وجو با نام، کد پرسنلی و — برای دارندگان مجوز — کد ملی)
 * - value / onChange: یک شیء {id, label, ...} یا null؛ با multiple=true آرایه
 * - label، placeholder (پیش‌فرض «جست‌وجوی نام یا کد پرسنلی…»)، excludeIds، size، sx، disabled، helperText، autoFocus
 * - clearOnSelect: بعد از انتخاب فیلد خالی شود (برای «افزودن به فهرست»)؛ در این حالت value لازم نیست
 * - minChars: حداقل حرف برای جست‌وجو (پیش‌فرض ۰ = با فیلد خالی هم ۲۰ نفر اول می‌آید)
 * - fetcherKey: هر مقداری که با تغییرش باید دوباره جست‌وجو شود (مثلاً وقتی فهرست پشت fetcher عوض می‌شود)
 * - onPasteText(text) → boolean: پیست متن؛ true = فراخوان متن را مصرف کرد (مثلاً افزودن یک‌جای چند کد پرسنلی)
 * سرور همیشه مرجع است؛ نتایج در کلاینت دوباره فیلتر نمی‌شوند (تا جست‌وجو با کد ملی که در برچسب نیست، گم نشود).
 */
export function employeeToOption(e) {
  return {
    id: e.id,
    // کد پرسنلی فقط برای فراخوان مجاز برمی‌گردد (نام کاربری پیش‌فرض)؛ برای بقیه فقط نام
    label: e.personnel_code
      ? `${e.first_name} ${e.last_name} (${e.personnel_code})`
      : `${e.first_name} ${e.last_name}`,
    employee: e,
  };
}

export default function EmployeeSearchField({
  fetcher,
  siteId,
  departmentIds,
  value,
  onChange,
  label,
  placeholder = EMPLOYEE_SEARCH_PLACEHOLDER,
  excludeIds = [],
  size = "small",
  sx,
  disabled = false,
  helperText,
  autoFocus = false,
  multiple = false,
  clearOnSelect = false,
  minChars = 0,
  limit = 20,
  fetcherKey,
  onPasteText,
}) {
  const [options, setOptions] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [inner, setInner] = useState(multiple ? [] : null); // فقط در حالت clearOnSelect
  const current = clearOnSelect ? inner : value;
  // همیشه آخرین fetcher صدا زده می‌شود (حتی اگر والد با هر رندر تابع جدید بسازد)؛ با تغییر fetcherKey دوباره جست‌وجو می‌شود
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const defaultFetcher = async (q) => {
    const data = await fetchEmployees({
      siteId,
      departmentIds,
      search: q,
      pageSize: limit,
    });
    return (data.items || []).map(employeeToOption);
  };

  useEffect(() => {
    if (disabled) return undefined;
    if (input.trim().length < minChars) {
      setOptions([]);
      return undefined;
    }
    let alive = true;
    setLoading(true);
    const t = setTimeout(() => {
      (fetcherRef.current || defaultFetcher)(input.trim())
        .then(
          (rows) =>
            alive &&
            setOptions((rows || []).filter((r) => !excludeIds.includes(r.id))),
        )
        .catch(() => alive && setOptions([]))
        .finally(() => alive && setLoading(false));
    }, 300);
    return () => {
      alive = false;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    input,
    siteId,
    JSON.stringify(departmentIds),
    JSON.stringify(excludeIds),
    disabled,
    minChars,
    fetcherKey,
  ]);

  // گزینه‌ی انتخاب‌شده همیشه در فهرست می‌ماند تا MUI هشدار «مقدار خارج از گزینه‌ها» ندهد
  const selectedList = multiple ? current || [] : current ? [current] : [];
  const merged = [
    ...selectedList.filter((v) => !options.some((o) => o.id === v.id)),
    ...options,
  ];

  return (
    <Autocomplete
      multiple={multiple}
      size={size}
      sx={sx}
      disabled={disabled}
      loading={loading}
      loadingText="در حال جست‌وجو…"
      options={merged}
      value={current ?? (multiple ? [] : null)}
      filterOptions={(x) => x}
      isOptionEqualToValue={(a, b) => a.id === b.id}
      getOptionLabel={(o) => o?.label || ""}
      getOptionDisabled={(o) => Boolean(o.disabled_reason)}
      renderOption={(props, o) => (
        <li {...props} key={o.id}>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
            sx={{ width: "100%" }}
            spacing={1}
          >
            <span>{o.label}</span>
            {o.disabled_reason && (
              <Typography variant="caption" color="error">
                {o.disabled_reason}
              </Typography>
            )}
          </Stack>
        </li>
      )}
      onChange={(_, next) => {
        if (clearOnSelect) {
          if (next) onChange(next);
          setInner(multiple ? [] : null);
          setInput("");
          return;
        }
        onChange(next);
      }}
      onInputChange={(_, text, reason) => {
        // بعد از انتخاب، MUI متن را به برچسب کامل برمی‌گرداند (reset)؛ آن را جست‌وجو نکن
        if (reason !== "reset") setInput(text);
      }}
      noOptionsText={
        input.trim().length < minChars
          ? "برای جست‌وجو تایپ کنید…"
          : "پرسنلی پیدا نشد"
      }
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          placeholder={placeholder}
          helperText={helperText}
          autoFocus={autoFocus}
          inputProps={{
            ...params.inputProps,
            // onPasteText(text) → true یعنی فراخوان خودش متن را مصرف کرده (مثلاً چند کد پرسنلی) و در فیلد نوشته نشود
            onPaste: (e) => {
              if (!onPasteText) return;
              const text = e.clipboardData?.getData("text") || "";
              if (onPasteText(text)) e.preventDefault();
            },
          }}
        />
      )}
    />
  );
}
