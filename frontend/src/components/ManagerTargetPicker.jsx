import { useCallback, useEffect, useMemo, useState } from "react";
import { Box, Chip, Stack, Typography } from "@mui/material";
import { fetchManagerCandidates } from "../api/evaluationStructure";
import { searchKey } from "../utils/searchText";
import EmployeeSearchField from "./EmployeeSearchField";

/**
 * انتخابگر افزودن فرد به فهرست ارزیابی یک مدیر.
 * ورودی: siteId (سایت)، managerEmployeeId (خودِ مدیر، از فهرست حذف می‌شود)، excludeIds (افراد از قبل افزوده‌شده)
 * و onSelect (با فرد انتخاب‌شده — شیء خام نامزد از سرور — صدا زده می‌شود).
 * خروجی: چیپ‌های «سرپرستان بدون مدیر» برای افزودن سریع + انتخابگر مشترک پرسنل (EmployeeSearchField) که
 * فهرست نامزدهای از قبل بارگذاری‌شده را در کلاینت فیلتر می‌کند؛ ظاهر و رفتار همان بقیه‌ی انتخابگرهاست.
 * فردی که از قبل تحت ارزیابی مدیر دیگری است، در جست‌وجو غیرفعال و با برچسب «تحت ارزیابی [نام مدیر]» نمایش داده می‌شود.
 * refreshKey: با هر تغییر ساختار (افزودن/حذف فرد، سرپرست، مدیر) عوض می‌شود تا وضعیت نامزدها بدون رفرش صفحه تازه شود.
 */
export default function ManagerTargetPicker({
  siteId,
  managerEmployeeId,
  excludeIds = [],
  onSelect,
  refreshKey = 0,
}) {
  const [candidates, setCandidates] = useState(null); // فهرست نامزدها از سرور؛ null = هنوز بارگذاری نشده

  // با تغییر سایت یا ساختار، فهرست نامزدها دوباره دریافت می‌شود (فهرست قبلی تا رسیدن پاسخ نمایش داده می‌ماند)
  useEffect(() => {
    let cancelled = false;
    fetchManagerCandidates(siteId)
      .then((data) => {
        if (!cancelled) setCandidates(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [siteId, refreshKey]);

  // نامزدها بدون خودِ مدیر و بدون افراد از قبل افزوده‌شده
  const availableCandidates = useMemo(() => {
    if (!candidates) return [];
    return candidates.filter(
      (c) => c.id !== managerEmployeeId && !excludeIds.includes(c.id),
    );
  }, [candidates, managerEmployeeId, excludeIds]);

  // سرپرستانی که هنوز زیر هیچ مدیری نیستند و خودشان مدیر نیستند
  const unassignedSupervisors = useMemo(
    () =>
      availableCandidates.filter(
        (c) =>
          c.supervisor_department_name && !c.evaluated_by_name && !c.is_manager,
      ),
    [availableCandidates],
  );

  // fetcher محلی برای EmployeeSearchField: به‌جای سرور، همان فهرست بارگذاری‌شده را با searchKey فیلتر می‌کند
  // (نام، کد پرسنلی)؛ افراد تحت ارزیابی مدیر دیگر با disabled_reason غیرفعال می‌شوند
  const localFetcher = useCallback(
    async (q) => {
      const key = searchKey(q);
      return availableCandidates
        .filter(
          (c) =>
            !key ||
            searchKey(
              `${c.first_name} ${c.last_name} ${c.personnel_code}`,
            ).includes(key),
        )
        .map((c) => ({
          id: c.id,
          label: `${c.first_name} ${c.last_name} (${c.personnel_code})`,
          employee: c,
          disabled_reason: c.evaluated_by_name
            ? `تحت ارزیابی ${c.evaluated_by_name}`
            : undefined,
        }));
    },
    [availableCandidates],
  );

  if (!candidates) return null;

  return (
    <Box>
      {/* بخش افزودن سریع سرپرستان بدون مدیر */}
      {unassignedSupervisors.length > 0 && (
        <Box sx={{ mb: 1.5 }}>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: "block", mb: 0.5 }}
          >
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

      {/* جست‌وجو در کل پرسنل سایت؛ بعد از انتخاب فیلد خالی می‌شود (clearOnSelect).
          excludeIds هم به فیلد داده می‌شود تا با تغییر فهرست، نتایج دوباره ساخته شوند */}
      <EmployeeSearchField
        fetcher={localFetcher}
        fetcherKey={candidates}
        excludeIds={[managerEmployeeId, ...excludeIds]}
        clearOnSelect
        onChange={(opt) => {
          if (opt?.employee) onSelect(opt.employee);
        }}
        label="جست‌وجو در کل پرسنل سایت"
      />
    </Box>
  );
}
