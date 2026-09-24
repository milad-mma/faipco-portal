import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { assignRoleToEmployee, fetchEmployeeRoles, fetchSupervisedDepartments } from "../api/employees";
import { fetchRoles, removeRoleAssignment } from "../api/users";
import { assignDepartmentSupervisor, fetchDepartments } from "../api/departments";
import { roleDisplayName } from "../utils/roleLabels";

/**
 * دیالوگ مدیریت دسترسی یک پرسنل: نقش‌های سازمانی (به تفکیک سایت) و سرپرستی واحدها.
 * ورودی: employee (پرسنل انتخاب‌شده؛ null = دیالوگ بسته)، sites (فهرست سایت‌ها) و onClose.
 * خروجی: Dialog شامل فهرست نقش‌های فعلی با امکان حذف، فرم اختصاص نقش جدید برای یک یا چند سایت،
 * و فهرست چک‌باکس واحدهای سازمانی برای تعیین سرپرستی.
 */
// مقدار ویژه‌ی گزینه‌ی «همه‌ی سایت‌ها» در انتخاب چندگانه (شناسه‌ی سایت‌ها عددی‌اند و تداخلی ندارد)
const ALL_SITES = "__all__";

export default function AssignAccessDialog({ employee, sites, onClose }) {
  const [roles, setRoles] = useState([]); // همه‌ی نقش‌های تعریف‌شده
  const [employeeRoles, setEmployeeRoles] = useState([]); // انتصاب‌های نقش این پرسنل (هر ردیف: role_id + site_id)
  const [allDepartments, setAllDepartments] = useState([]);
  const [supervisedDeptIds, setSupervisedDeptIds] = useState([]); // id واحدهایی که این پرسنل سرپرست آن‌هاست

  const [roleToAssign, setRoleToAssign] = useState(""); // id نقش انتخاب‌شده برای اختصاص
  const [sitesForRole, setSitesForRole] = useState([]); // سایت‌های انتخاب‌شده برای نقش (چندانتخابی)

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // با تغییر پرسنل، پیام‌ها پاک و نقش‌ها، انتصاب‌ها، واحدها و سرپرستی‌ها از سرور بارگذاری می‌شوند
  useEffect(() => {
    if (!employee) return;
    setError("");
    setSuccess("");
    fetchRoles().then(setRoles);
    fetchEmployeeRoles(employee.id).then(setEmployeeRoles);
    fetchDepartments().then(setAllDepartments);
    fetchSupervisedDepartments(employee.id).then(setSupervisedDeptIds);
  }, [employee]);

  if (!employee) return null;

  // نام سایت از روی id
  const siteLabel = (id) => sites.find((s) => s.id === id)?.name || "—";
  // نام نمایشی نقش از روی id (اگر نقش پیدا نشود، خود id)
  const roleLabel = (id) => {
    const found = roles.find((r) => r.id === id);
    return found ? roleDisplayName(found.name) : id;
  };

  // اختصاص نقش انتخاب‌شده برای همه‌ی سایت‌های انتخابی؛ سایت‌هایی که از قبل این نقش را داشتند شمرده و گزارش می‌شوند
  async function handleAssignRole() {
    setError("");
    setSuccess("");
    try {
      const created = await assignRoleToEmployee(employee.id, roleToAssign, sitesForRole);
      setEmployeeRoles(await fetchEmployeeRoles(employee.id));
      setRoleToAssign("");
      setSitesForRole([]);
      const skipped = sitesForRole.length - created.length;
      setSuccess(
        skipped > 0
          ? `نقش برای ${created.length} سایت اختصاص یافت (${skipped} مورد از قبل داشت).`
          : "نقش با موفقیت اختصاص یافت."
      );
    } catch (err) {
      setError(err.response?.data?.detail || "انتصاب نقش با خطا مواجه شد.");
    }
  }

  // حذف یک انتصاب نقش و بارگذاری مجدد فهرست
  async function handleRemoveRole(userRoleId) {
    await removeRoleAssignment(userRoleId);
    setEmployeeRoles(await fetchEmployeeRoles(employee.id));
  }

  // تعیین یا برداشتن این پرسنل به‌عنوان سرپرست یک واحد (برداشتن = سرپرست null)
  async function handleToggleDepartment(departmentId, isChecked) {
    setError("");
    try {
      await assignDepartmentSupervisor(departmentId, isChecked ? employee.id : null);
      setSupervisedDeptIds(await fetchSupervisedDepartments(employee.id));
    } catch (err) {
      setError(err.response?.data?.detail || "به‌روزرسانی سرپرستی با خطا مواجه شد.");
    }
  }

  return (
    <Dialog open={Boolean(employee)} onClose={onClose} fullWidth maxWidth="xs">
      {/* عنوان: نام، کد پرسنلی و سایت پرسنل */}
      <DialogTitle>
        دسترسی — {employee.first_name} {employee.last_name}
        <Typography variant="caption" color="text.secondary" display="block">
          کد پرسنلی: {employee.personnel_code} · سایت: {siteLabel(employee.site_id)}
        </Typography>
      </DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        {/* نقش‌های سازمانی فعلی؛ انتصاب بدون site_id به‌صورت «سراسری — قدیمی» نمایش داده می‌شود */}
        <Stack spacing={1}>
          <Typography variant="subtitle2" fontWeight={700}>
            نقش سازمانی
          </Typography>
          {employeeRoles.length === 0 && (
            <Typography variant="body2" color="text.secondary">
              هنوز نقشی اختصاص نیافته.
            </Typography>
          )}
          {employeeRoles.map((ur) => (
            <Stack
              key={ur.id}
              direction="row"
              alignItems="center"
              justifyContent="space-between"
              sx={{ p: 1, border: "1px solid", borderColor: "divider", borderRadius: 2 }}
            >
              <Chip
                size="small"
                label={`${roleLabel(ur.role_id)}${ur.site_id ? ` — ${siteLabel(ur.site_id)}` : " (سراسری — قدیمی)"}`}
              />
              <Button size="small" color="error" onClick={() => handleRemoveRole(ur.id)}>
                <DeleteOutlineIcon fontSize="small" />
              </Button>
            </Stack>
          ))}
        </Stack>

        {/* انتخاب نقش جدید؛ با تغییر نقش، سایت‌های انتخاب‌شده پاک می‌شوند */}
        <TextField
          select
          size="small"
          label="اختصاص نقش جدید"
          value={roleToAssign}
          onChange={(e) => {
            setRoleToAssign(e.target.value);
            setSitesForRole([]);
          }}
        >
          {roles.map((r) => (
            <MenuItem key={r.id} value={r.id}>
              {roleDisplayName(r.name)}
            </MenuItem>
          ))}
        </TextField>

        {/* انتخاب چندگانه‌ی سایت‌ها برای نقش انتخاب‌شده (برای همه‌ی نقش‌ها اجباری است)؛
            هر سایت یک ردیف انتصاب جدا در Backend می‌سازد ولی همه در یک اقدام ثبت می‌شوند. */}
        {roleToAssign && (
          <TextField
            select
            size="small"
            label="این نقش برای کدام سایت‌هاست؟"
            value={sitesForRole}
            onChange={(e) => {
              const { value } = e.target;
              const next = typeof value === "string" ? value.split(",") : value;
              // گزینه‌ی «همه‌ی سایت‌ها»: اگر همه انتخاب‌اند همه برداشته می‌شوند، وگرنه همه انتخاب می‌شوند
              if (next.includes(ALL_SITES)) {
                const allSelected = sites.every((s) => sitesForRole.includes(s.id));
                setSitesForRole(allSelected ? [] : sites.map((s) => s.id));
                return;
              }
              setSitesForRole(next);
            }}
            required
            helperText="برای دسترسی در همه‌جا «همه‌ی سایت‌ها» را بزنید؛ سایت‌هایی که بعداً ساخته شوند خودکار اضافه نمی‌شوند."
            SelectProps={{
              multiple: true,
              renderValue: (selected) =>
                sites.length > 1 && sites.every((s) => selected.includes(s.id))
                  ? "همه‌ی سایت‌ها"
                  : selected.map((id) => siteLabel(id)).join("، "),
            }}
          >
            {/* انتخاب/برداشتن یک‌جای همه‌ی سایت‌ها */}
            <MenuItem value={ALL_SITES}>
              <Checkbox size="small" checked={sites.length > 0 && sites.every((s) => sitesForRole.includes(s.id))} />
              <b>همه‌ی سایت‌ها</b>
            </MenuItem>
            {sites.map((s) => (
              <MenuItem key={s.id} value={s.id}>
                <Checkbox size="small" checked={sitesForRole.includes(s.id)} />
                {s.name}
              </MenuItem>
            ))}
          </TextField>
        )}

        {/* پیام‌ها و دکمه‌ی ثبت نقش (تا انتخاب نقش و حداقل یک سایت غیرفعال است) */}
        {error && <Alert severity="error">{error}</Alert>}
        {success && <Alert severity="success">{success}</Alert>}
        <Button
          variant="outlined"
          size="small"
          disabled={!roleToAssign || sitesForRole.length === 0}
          onClick={handleAssignRole}
        >
          اختصاص این نقش
        </Button>

        <Divider />

        {/* سرپرستی واحد(ها) — یک نفر می‌تواند سرپرست چند واحد باشد */}
        <Typography variant="subtitle2" fontWeight={700}>
          سرپرست کدام واحدهاست؟
        </Typography>
        <Typography variant="caption" color="text.secondary">
          می‌توانید همین شخص را هم‌زمان سرپرست چند واحد سازمانی کنید.
        </Typography>
        <Stack spacing={0.5} sx={{ maxHeight: 220, overflowY: "auto" }}>
          {allDepartments.length === 0 && (
            <Typography variant="body2" color="text.secondary">
              هنوز هیچ واحد سازمانی‌ای وجود ندارد.
            </Typography>
          )}
          {allDepartments.map((dept) => (
            <FormControlLabel
              key={dept.id}
              control={
                <Checkbox
                  size="small"
                  checked={supervisedDeptIds.includes(dept.id)}
                  onChange={(e) => handleToggleDepartment(dept.id, e.target.checked)}
                />
              }
              label={`${dept.name} — ${siteLabel(dept.site_id)}`}
            />
          ))}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ p: 2.5 }}>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}
