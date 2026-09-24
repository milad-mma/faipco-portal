import { useEffect, useState } from "react";
import { MenuItem, TextField } from "@mui/material";
import { fetchMyAccessibleSites, fetchSites } from "../api/sites";

/**
 * دراپ‌داون فیلتر سایت برای گزارش‌های سایت‌محور پنل ادمین.
 * ورودی: value (شناسه‌ی سایت یا null/"" = همه‌ی سایت‌ها)، onChange (شناسه‌ی عددی یا null)،
 * permission (کد مجوز همان گزارش)، size و sx.
 * با داشتن permission فقط سایت‌هایی که کاربر جاری برایشان دسترسی دارد نمایش داده می‌شوند؛
 * کاربر با دسترسی سراسری (unrestricted) همه‌ی سایت‌ها را می‌بیند.
 * فیلتر واقعی داده همیشه در Endpointهای Backend انجام می‌شود.
 */
export default function SiteFilterSelect({ value, onChange, permission, size = "small", sx }) {
  const [sites, setSites] = useState([]);  // فهرست سایت‌های قابل انتخاب

  // فهرست سایت‌ها بر اساس مجوز داده‌شده بارگذاری می‌شود
  useEffect(() => {
    if (permission) {
      fetchMyAccessibleSites(permission).then(({ unrestricted, sites: accessibleSites }) => {
        if (unrestricted) {
          fetchSites().then(setSites);
        } else {
          setSites(accessibleSites);
        }
      });
    } else {
      // بدون permission، فهرست همه‌ی سایت‌ها نمایش داده می‌شود
      fetchSites().then(setSites);
    }
  }, [permission]);

  return (
    <TextField
      select
      label="سایت"
      size={size}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
      sx={{ minWidth: 180, ...sx }}
    >
      <MenuItem value="">همه سایت‌ها</MenuItem>
      {sites.map((site) => (
        <MenuItem key={site.id} value={site.id}>
          {site.name}
        </MenuItem>
      ))}
    </TextField>
  );
}
