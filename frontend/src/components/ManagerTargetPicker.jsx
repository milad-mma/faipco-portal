import { useEffect, useMemo, useState } from "react";
import { Autocomplete, Box, Chip, Stack, TextField, Typography } from "@mui/material";
import { fetchManagerCandidates } from "../api/evaluationStructure";

/**
 * انتخابگر افزودن فرد به فهرست ارزیابی یک مدیر.
 * ورودی: siteId (سایت)، managerEmployeeId (خودِ مدیر، از فهرست حذف می‌شود)، excludeIds (افراد از قبل افزوده‌شده)
 * و onSelect (با فرد انتخاب‌شده صدا زده می‌شود).
 * خروجی: چیپ‌های «سرپرستان بدون مدیر» برای افزودن سریع + Autocomplete جست‌وجو در کل پرسنل سایت.
 * فردی که از قبل تحت ارزیابی مدیر دیگری است، در جست‌وجو غیرفعال و با برچسب «تحت ارزیابی [نام مدیر]» نمایش داده می‌شود.
 */
export default function ManagerTargetPicker({ siteId, managerEmployeeId, excludeIds = [], onSelect }) {
  const [candidates, setCandidates] = useState(null);  // فهرست نامزدها از سرور؛ null = هنوز بارگذاری نشده

  // با تغییر سایت، فهرست نامزدها دوباره دریافت می‌شود
  useEffect(() => {
    fetchManagerCandidates(siteId).then(setCandidates);
  }, [siteId]);

  // نامزدها بدون خودِ مدیر و بدون افراد از قبل افزوده‌شده
  const availableCandidates = useMemo(() => {
    if (!candidates) return [];
    return candidates.filter((c) => c.id !== managerEmployeeId && !excludeIds.includes(c.id));
  }, [candidates, managerEmployeeId, excludeIds]);

  // سرپرستانی که هنوز زیر هیچ مدیری نیستند و خودشان مدیر نیستند
  const unassignedSupervisors = useMemo(
    () => availableCandidates.filter((c) => c.supervisor_department_name && !c.evaluated_by_name && !c.is_manager),
    [availableCandidates]
  );

  if (!candidates) return null;

  return (
    <Box>
      {/* بخش افزودن سریع سرپرستان بدون مدیر */}
      {unassignedSupervisors.length > 0 && (
        <Box sx={{ mb: 1.5 }}>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
            سرپرستان بدون مدیر (افزودن سریع):
          </Typography>
          <Stack direction="row" flexWrap="wrap" useFlexGap>
            {unassignedSupervisors.map((c) => (
              <Chip
                key={c.id}
                size="small"
                label={`${c.first_name} ${c.last_name} — سرپرست ${c.supervisor_department_name}`}
                onClick={() => onSelect(c)}
                sx={{ mb: 0.5, cursor: "pointer" }}
                color="primary"
                variant="outlined"
              />
            ))}
          </Stack>
        </Box>
      )}

      {/* جست‌وجو در کل پرسنل؛ افراد تحت ارزیابی مدیر دیگر غیرفعال‌اند. value همیشه null است تا بعد از انتخاب خالی شود */}
      <Autocomplete
        options={availableCandidates}
        getOptionLabel={(c) => `${c.first_name} ${c.last_name} (${c.personnel_code})`}
        getOptionDisabled={(c) => Boolean(c.evaluated_by_name)}
        renderOption={(props, c) => (
          <Box component="li" {...props} key={c.id}>
            <Stack>
              <Typography variant="body2">
                {c.first_name} {c.last_name} ({c.personnel_code})
              </Typography>
              {c.evaluated_by_name && (
                <Typography variant="caption" color="error">
                  تحت ارزیابی {c.evaluated_by_name}
                </Typography>
              )}
            </Stack>
          </Box>
        )}
        onChange={(_, value) => {
          if (value) onSelect(value);
        }}
        value={null}
        renderInput={(params) => <TextField {...params} label="جست‌وجو در کل پرسنل سایت" size="small" />}
      />
    </Box>
  );
}
