import { useEffect, useState } from "react";
import { Autocomplete, TextField } from "@mui/material";
import { fetchEmployees } from "../api/employees";

/**
 * انتخابگر پرسنل با جست‌وجوی زنده (Autocomplete)، محدود به یک سایت و/یا واحدهای سازمانی مشخص.
 * ورودی: siteId، departmentIds، label، onSelect (با شیء پرسنل انتخاب‌شده صدا زده می‌شود)
 * و excludeIds (id پرسنلی که نباید پیشنهاد شوند).
 * پس از هر انتخاب، فیلد خالی می‌شود تا انتخاب بعدی انجام شود (مثلاً در «ساختار ارزیابی»).
 */
export default function EmployeePicker({ siteId, departmentIds, label, onSelect, excludeIds = [] }) {
  const [options, setOptions] = useState([]);
  const [search, setSearch] = useState(""); // متن تایپ‌شده برای جست‌وجو
  const [value, setValue] = useState(null);

  // جست‌وجوی پرسنل (حداکثر ۲۰ نتیجه) با تغییر سایت، واحدها یا متن جست‌وجو و حذف excludeIds از نتایج؛
  // departmentIds با JSON.stringify مقایسه می‌شود تا آرایه‌ی جدید با محتوای یکسان باعث درخواست مجدد نشود
  useEffect(() => {
    fetchEmployees({ siteId, departmentIds, search, pageSize: 20 }).then((data) => {
      const items = (data.items || []).filter((e) => !excludeIds.includes(e.id));
      setOptions(items);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [siteId, JSON.stringify(departmentIds), search]);

  return (
    <Autocomplete
      size="small"
      options={options}
      getOptionLabel={(o) => `${o.first_name} ${o.last_name} (${o.personnel_code})`}
      value={value}
      onChange={(_, next) => {
        // گزارش انتخاب به والد و خالی کردن فیلد
        setValue(next);
        if (next) {
          onSelect(next);
          setValue(null);
          setSearch("");
        }
      }}
      onInputChange={(_, next) => setSearch(next)}
      isOptionEqualToValue={(o, v) => o.id === v.id}
      renderInput={(params) => <TextField {...params} label={label} />}
      noOptionsText="پرسنلی با این مشخصات پیدا نشد"
      sx={{ minWidth: 260 }}
    />
  );
}
