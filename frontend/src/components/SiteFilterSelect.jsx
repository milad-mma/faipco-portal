import { useEffect, useState } from "react";
import { MenuItem, TextField } from "@mui/material";
import { fetchSites } from "../api/sites";

/**
 * دراپ‌داون فیلتر سایت — برای نمای «سایت-محور» گزارش‌های پنل Admin. مقدار
 * "" یعنی «همه سایت‌ها»؛ در غیر این صورت شناسه عددی همان سایت.
 *
 * لیست سایت‌ها را خودش می‌گیرد (از همان Endpoint باز /sites — فقط نام/کد،
 * داده حساسی نیست). اگر کاربر جاری فقط مدیر یک/چند سایت خاص باشد (نه
 * Admin واقعی)، Backend خودش هرگونه انتخاب خارج از محدوده را نادیده
 * می‌گیرد (نگاه کنید docs/rbac.md) — این کامپوننت صرفاً یک وسیله فیلتر
 * در UI است، نه لایه امنیتی.
 */
export default function SiteFilterSelect({ value, onChange, size = "small", sx }) {
  const [sites, setSites] = useState([]);

  useEffect(() => {
    fetchSites().then(setSites);
  }, []);

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
