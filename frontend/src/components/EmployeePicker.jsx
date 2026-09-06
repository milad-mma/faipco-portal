import { useEffect, useState } from "react";
import { Autocomplete, TextField } from "@mui/material";
import { fetchEmployees } from "../api/employees";

/**
 * انتخابگر پرسنل با جست‌وجوی زنده - محدود به یک سایت و/یا یک واحد
 * سازمانی مشخص (طبق props). برای «ساختار ارزیابی» استفاده می‌شود -
 * مثلاً هنگام انتخاب سرپرست یک واحد، فقط پرسنل همان واحد پیشنهاد
 * می‌شوند.
 */
export default function EmployeePicker({ siteId, departmentIds, label, onSelect, excludeIds = [] }) {
  const [options, setOptions] = useState([]);
  const [search, setSearch] = useState("");
  const [value, setValue] = useState(null);

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
