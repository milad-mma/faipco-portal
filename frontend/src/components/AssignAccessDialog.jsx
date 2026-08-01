import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { assignRoleToEmployee, fetchEmployeeRoles } from "../api/employees";
import { fetchRoles, removeRoleAssignment } from "../api/users";
import { assignDepartmentSupervisor, fetchDepartments } from "../api/departments";

export default function AssignAccessDialog({ employee, sites, onClose }) {
  const [roles, setRoles] = useState([]);
  const [employeeRoles, setEmployeeRoles] = useState([]);
  const [departments, setDepartments] = useState([]);

  const [roleToAssign, setRoleToAssign] = useState("");
  const [siteForRole, setSiteForRole] = useState("");
  const [departmentToSupervise, setDepartmentToSupervise] = useState("");

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (!employee) return;
    fetchRoles().then(setRoles);
    fetchEmployeeRoles(employee.id).then(setEmployeeRoles);
    fetchDepartments(employee.site_id).then(setDepartments);
  }, [employee]);

  if (!employee) return null;

  const siteLabel = (id) => sites.find((s) => s.id === id)?.name || "—";
  const roleLabel = (id) => roles.find((r) => r.id === id)?.name || id;

  async function handleAssignRole() {
    setError("");
    setSuccess("");
    try {
      await assignRoleToEmployee(employee.id, roleToAssign, siteForRole || null);
      setEmployeeRoles(await fetchEmployeeRoles(employee.id));
      setRoleToAssign("");
      setSiteForRole("");
      setSuccess("نقش با موفقیت اختصاص یافت.");
    } catch (err) {
      setError(err.response?.data?.detail || "انتصاب نقش ناموفق بود");
    }
  }

  async function handleRemoveRole(userRoleId) {
    await removeRoleAssignment(userRoleId);
    setEmployeeRoles(await fetchEmployeeRoles(employee.id));
  }

  async function handleAssignSupervisor() {
    setError("");
    setSuccess("");
    try {
      await assignDepartmentSupervisor(departmentToSupervise, employee.id);
      setSuccess(`${employee.first_name} ${employee.last_name} به‌عنوان سرپرست این واحد تعیین شد.`);
      setDepartmentToSupervise("");
    } catch (err) {
      setError(err.response?.data?.detail || "انتصاب سرپرست ناموفق بود");
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

        {/* نقش‌های فعلی این پرسنل */}
        <Stack spacing={1}>
          <Typography variant="subtitle2" fontWeight={700}>
            نقش‌های فعلی
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
                label={`${roleLabel(ur.role_id)}${ur.site_id ? ` — ${siteLabel(ur.site_id)}` : " (سراسری)"}`}
              />
              <Button size="small" color="error" onClick={() => handleRemoveRole(ur.id)}>
                <DeleteOutlineIcon fontSize="small" />
              </Button>
            </Stack>
          ))}
        </Stack>

        <Divider />

        {/* انتصاب نقش جدید */}
        <Typography variant="subtitle2" fontWeight={700}>
          اختصاص نقش جدید
        </Typography>
        <TextField
          select
          size="small"
          label="نقش"
          value={roleToAssign}
          onChange={(e) => setRoleToAssign(e.target.value)}
        >
          {roles.map((r) => (
            <MenuItem key={r.id} value={r.id}>
              {r.name}
              {r.description ? ` — ${r.description}` : ""}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="محدود به سایت (اختیاری — خالی یعنی سراسری)"
          value={siteForRole}
          onChange={(e) => setSiteForRole(e.target.value)}
        >
          <MenuItem value="">— سراسری —</MenuItem>
          {sites.map((s) => (
            <MenuItem key={s.id} value={s.id}>
              {s.name}
            </MenuItem>
          ))}
        </TextField>
        <Button variant="outlined" size="small" disabled={!roleToAssign} onClick={handleAssignRole}>
          اختصاص این نقش
        </Button>

        <Divider />

        {/* انتصاب به‌عنوان سرپرست واحد */}
        <Typography variant="subtitle2" fontWeight={700}>
          سرپرست یک واحد سازمانی
        </Typography>
        <TextField
          select
          size="small"
          label="واحد سازمانی (از همین سایت)"
          value={departmentToSupervise}
          onChange={(e) => setDepartmentToSupervise(e.target.value)}
        >
          {departments.length === 0 && (
            <MenuItem value="" disabled>
              هیچ واحدی برای این سایت تعریف نشده
            </MenuItem>
          )}
          {departments.map((d) => (
            <MenuItem key={d.id} value={d.id}>
              {d.name}
            </MenuItem>
          ))}
        </TextField>
        <Button
          variant="outlined"
          size="small"
          disabled={!departmentToSupervise}
          onClick={handleAssignSupervisor}
        >
          تعیین به‌عنوان سرپرست این واحد
        </Button>
      </DialogContent>
      <DialogActions sx={{ p: 2.5 }}>
        <Button onClick={onClose}>بستن</Button>
      </DialogActions>
    </Dialog>
  );
}
