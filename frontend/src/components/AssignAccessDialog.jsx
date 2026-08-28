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

export default function AssignAccessDialog({ employee, sites, onClose }) {
  const [roles, setRoles] = useState([]);
  const [employeeRoles, setEmployeeRoles] = useState([]);
  const [allDepartments, setAllDepartments] = useState([]);
  const [supervisedDeptIds, setSupervisedDeptIds] = useState([]);

  const [roleToAssign, setRoleToAssign] = useState("");
  const [sitesForRole, setSitesForRole] = useState([]); // چند سایت هم‌زمان — طبق درخواست صریح

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

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

  const siteLabel = (id) => sites.find((s) => s.id === id)?.name || "—";
  const roleLabel = (id) => {
    const found = roles.find((r) => r.id === id);
    return found ? roleDisplayName(found.name) : id;
  };

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
      setError(err.response?.data?.detail || "انتصاب نقش ناموفق بود");
    }
  }

  async function handleRemoveRole(userRoleId) {
    await removeRoleAssignment(userRoleId);
    setEmployeeRoles(await fetchEmployeeRoles(employee.id));
  }

  async function handleToggleDepartment(departmentId, isChecked) {
    setError("");
    try {
      await assignDepartmentSupervisor(departmentId, isChecked ? employee.id : null);
      setSupervisedDeptIds(await fetchSupervisedDepartments(employee.id));
    } catch (err) {
      setError(err.response?.data?.detail || "به‌روزرسانی سرپرستی ناموفق بود");
    }
  }

  return (
    <Dialog open={Boolean(employee)} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>
        دسترسی — {employee.first_name} {employee.last_name}
        <Typography variant="caption" color="text.secondary" display="block">
          کد پرسنلی: {employee.personnel_code} · سایت: {siteLabel(employee.site_id)}
        </Typography>
      </DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
        {error && <Alert severity="error">{error}</Alert>}
        {success && <Alert severity="success">{success}</Alert>}

        {/* نقش‌های سازمانی فعلی */}
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

        {/* ⚠️ رفع یک باگ واقعی: قبلاً این فیلد فقط برای نقش «site_manager»
            نمایش داده می‌شد؛ برای هر نقش دیگری (مثل «حراست»)، هرگز امکان
            انتخاب سایت نبود و در نتیجه انتصاب همیشه بی‌صدا سراسری
            (site_id=null) می‌شد — حتی وقتی این ابداً قصد Admin نبود. طبق
            درخواست صریح، هر انتصاب نقشی حتماً باید به یک سایت مشخص محدود
            باشد؛ این فیلد برای همه نقش‌ها نمایش داده می‌شود.
            ⚠️ به‌روزرسانی بعدی: طبق درخواست صریح، حالا چندانتخابی است —
            یک نقش می‌تواند هم‌زمان برای چند سایت اختصاص یابد (هرکدام یک
            ردیف جدا در پس‌زمینه، ولی همه در یک اقدام). */}
        {roleToAssign && (
          <TextField
            select
            size="small"
            label="این نقش برای کدام سایت‌هاست؟"
            value={sitesForRole}
            onChange={(e) => {
              const { value } = e.target;
              setSitesForRole(typeof value === "string" ? value.split(",") : value);
            }}
            required
            SelectProps={{
              multiple: true,
              renderValue: (selected) => selected.map((id) => siteLabel(id)).join("، "),
            }}
          >
            {sites.map((s) => (
              <MenuItem key={s.id} value={s.id}>
                <Checkbox size="small" checked={sitesForRole.includes(s.id)} />
                {s.name}
              </MenuItem>
            ))}
          </TextField>
        )}

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
