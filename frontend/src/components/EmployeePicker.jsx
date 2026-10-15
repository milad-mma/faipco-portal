import EmployeeSearchField from "./EmployeeSearchField";

/**
 * انتخابگر «افزودن پرسنل» (بعد از هر انتخاب خالی می‌شود) — پوسته‌ای روی EmployeeSearchField مشترک.
 * ورودی: siteId، departmentIds، label، placeholder، onSelect(employee) با شیء کامل پرسنل، excludeIds، sx.
 */
export default function EmployeePicker({
  siteId,
  departmentIds,
  label,
  placeholder,
  onSelect,
  excludeIds = [],
  sx,
}) {
  return (
    <EmployeeSearchField
      siteId={siteId}
      departmentIds={departmentIds}
      label={label}
      placeholder={placeholder}
      excludeIds={excludeIds}
      clearOnSelect
      onChange={(opt) => opt && onSelect(opt.employee)}
      sx={{ minWidth: 260, ...sx }}
    />
  );
}
