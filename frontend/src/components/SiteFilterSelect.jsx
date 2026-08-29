import { useEffect, useState } from "react";
import { MenuItem, TextField } from "@mui/material";
import { fetchMyAccessibleSites, fetchSites } from "../api/sites";

/**
 * دراپ‌داون فیلتر سایت — برای نمای «سایت-محور» گزارش‌های پنل Admin. مقدار
 * "" یعنی «همه سایت‌ها»؛ در غیر این صورت شناسه عددی همان سایت.
 *
 * ⚠️ رفع یک نقص واقعی UX (نه خطای امنیتی — خودِ Endpoint های داده همیشه
 * درست فیلتر می‌کردند): قبلاً فهرست سایت‌ها را از GET /sites (همه
 * سایت‌های سیستم، بدون فیلتر) می‌گرفت — یعنی کاربری با دسترسی فقط به یک
 * سایت، همه سایت‌های دیگر را هم در دراپ‌داون می‌دید (که انتخابشان فقط
 * یک نتیجه خالی می‌داد، بدون هیچ توضیحی) — به‌اشتباه به‌نظر می‌رسید
 * فیلتر سایتی اصلاً کار نمی‌کند. حالا با `permission` (Permission Code
 * همان گزارش)، فقط سایت‌هایی که کاربر جاری واقعاً برایشان دسترسی دارد
 * نشان داده می‌شود — مگر Admin واقعی/انتصاب سراسری باشد، که همچنان همه
 * سایت‌ها را می‌بیند.
 */
export default function SiteFilterSelect({ value, onChange, permission, size = "small", sx }) {
  const [sites, setSites] = useState([]);

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
      // اگر permission داده نشود (برای سازگاری با فراخوانی‌های قدیمی‌تر)، همان رفتار قبلی
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
