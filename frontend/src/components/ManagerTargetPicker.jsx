import { useEffect, useMemo, useState } from "react";
import { Autocomplete, Box, Chip, Stack, TextField, Typography } from "@mui/material";
import { fetchManagerCandidates } from "../api/evaluationStructure";

/**
 * انتخابگر «افزودن به فهرست ارزیابی یک مدیر» - طبق درخواست صریح:
 *   ۱. علاوه بر جست‌وجوی کل پرسنل، یک بخش «سرپرستان بدون مدیر» هم دارد -
 *      برای افزودن سریع سرپرستانی که هنوز زیر هیچ مدیری نیستند.
 *   ۲. اگر فردی از قبل تحت ارزیابی یک مدیر دیگر است، در جست‌وجو نشان داده
 *      می‌شود ولی غیرفعال است، با برچسب «تحت ارزیابی [نام آن مدیر]» -
 *      نه اینکه کاملاً پنهان شود؛ یعنی کاربر می‌فهمد چرا نمی‌تواند
 *      انتخابش کند، به‌جای اینکه فکر کند اصلاً وجود ندارد.
 */
export default function ManagerTargetPicker({ siteId, managerEmployeeId, excludeIds = [], onSelect }) {
  const [candidates, setCandidates] = useState(null);

  useEffect(() => {
    fetchManagerCandidates(siteId).then(setCandidates);
  }, [siteId]);

  const availableCandidates = useMemo(() => {
    if (!candidates) return [];
    return candidates.filter((c) => c.id !== managerEmployeeId && !excludeIds.includes(c.id));
  }, [candidates, managerEmployeeId, excludeIds]);

  const unassignedSupervisors = useMemo(
    () => availableCandidates.filter((c) => c.supervisor_department_name && !c.evaluated_by_name && !c.is_manager),
    [availableCandidates]
  );

  if (!candidates) return null;

  return (
    <Box>
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
