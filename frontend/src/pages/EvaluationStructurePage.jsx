import { useEffect, useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Chip,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import SupervisorAccountOutlinedIcon from "@mui/icons-material/SupervisorAccountOutlined";
import { fetchSites } from "../api/sites";
import { fetchEmployees } from "../api/employees";
import EmployeePicker from "../components/EmployeePicker";
import {
  addOtherManager,
  addShiftLead,
  addSiteManager,
  fetchEvaluationSiteStructure,
  removeDepartmentSupervisor,
  removeOtherManager,
  removeShiftAssignment,
  removeShiftLead,
  removeSiteManager,
  setDepartmentSupervisor,
  setShiftAssignment,
} from "../api/evaluationStructure";

function PersonChip({ employee, onRemove }) {
  return (
    <Chip
      label={`${employee.first_name} ${employee.last_name} (${employee.personnel_code})`}
      onDelete={onRemove}
      sx={{ mb: 0.5 }}
    />
  );
}

function DepartmentShiftAssignmentTable({ siteId, department, onAssign }) {
  const [employees, setEmployees] = useState(null);
  const shiftLeadEmployeeIds = department.shift_leads.map((sl) => sl.employee.id);
  const supervisorId = department.supervisor?.id;

  useEffect(() => {
    fetchEmployees({ siteId, departmentIds: [department.id], pageSize: 200 }).then((data) =>
      setEmployees(
        (data.items || []).filter((e) => !shiftLeadEmployeeIds.includes(e.id) && e.id !== supervisorId)
      )
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [siteId, department.id]);

  function currentShiftLeadFor(employeeId) {
    const assignment = department.shift_assignments.find((a) => a.employee.id === employeeId);
    return assignment ? assignment.shift_lead_id : "";
  }

  if (employees === null) return null;

  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>پرسنل</TableCell>
            <TableCell>سرشیفت</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {employees.map((employee) => (
            <TableRow key={employee.id}>
              <TableCell>
                {employee.first_name} {employee.last_name} ({employee.personnel_code})
              </TableCell>
              <TableCell>
                <TextField
                  select
                  size="small"
                  value={currentShiftLeadFor(employee.id)}
                  onChange={(e) => onAssign(employee.id, e.target.value)}
                  sx={{ minWidth: 180 }}
                >
                  <MenuItem value="">— تخصیص‌نیافته —</MenuItem>
                  {department.shift_leads.map((sl) => (
                    <MenuItem key={sl.id} value={sl.id}>
                      {sl.employee.first_name} {sl.employee.last_name}
                    </MenuItem>
                  ))}
                </TextField>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

function DepartmentCard({ siteId, department, onChanged, onError }) {
  const hasShiftLeads = department.shift_leads.length > 0;
  const assignedEmployeeIds = department.shift_leads.map((sl) => sl.employee.id);

  async function handleSetSupervisor(employee) {
    try {
      await setDepartmentSupervisor(department.id, employee.id);
      onChanged();
    } catch (err) {
      onError(err.response?.data?.detail || "تعیین سرپرست با خطا مواجه شد.");
    }
  }

  async function handleRemoveSupervisor() {
    try {
      await removeDepartmentSupervisor(department.id);
      onChanged();
    } catch (err) {
      onError(err.response?.data?.detail || "حذف سرپرست با خطا مواجه شد.");
    }
  }

  async function handleAddShiftLead(employee) {
    try {
      await addShiftLead(department.id, employee.id);
      onChanged();
    } catch (err) {
      onError(err.response?.data?.detail || "افزودن سرشیفت با خطا مواجه شد.");
    }
  }

  async function handleRemoveShiftLead(shiftLeadId) {
    try {
      await removeShiftLead(shiftLeadId);
      onChanged();
    } catch (err) {
      onError(err.response?.data?.detail || "حذف سرشیفت با خطا مواجه شد.");
    }
  }

  async function handleAssignShift(employeeId, shiftLeadId) {
    try {
      if (shiftLeadId === "") {
        await removeShiftAssignment(employeeId);
      } else {
        await setShiftAssignment(employeeId, shiftLeadId);
      }
      onChanged();
    } catch (err) {
      onError(err.response?.data?.detail || "تخصیص سرشیفت با خطا مواجه شد.");
    }
  }

  return (
    <Accordion disableGutters variant="outlined">
      <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Typography fontWeight={700}>{department.name}</Typography>
          {department.supervisor && (
            <Chip
              size="small"
              color="primary"
              icon={<SupervisorAccountOutlinedIcon />}
              label={`سرپرست: ${department.supervisor.first_name} ${department.supervisor.last_name}`}
            />
          )}
          {hasShiftLeads && <Chip size="small" label={`${department.shift_leads.length} سرشیفت`} />}
        </Stack>
      </AccordionSummary>
      <AccordionDetails>
        <Stack spacing={3}>
          <Box>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
              سرپرست واحد
            </Typography>
            {department.supervisor ? (
              <PersonChip employee={department.supervisor} onRemove={handleRemoveSupervisor} />
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                هنوز سرپرستی برای این واحد تعیین نشده است.
              </Typography>
            )}
            <EmployeePicker
              siteId={siteId}
              label="تعیین/تغییر سرپرست (جست‌وجو در کل پرسنل سایت)"
              onSelect={handleSetSupervisor}
            />
          </Box>

          <Box>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
              سرشیفت‌های واحد (اختیاری)
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
              اگر حداقل یک سرشیفت اضافه کنید، سرپرست دیگر مستقیم پرسنل را ارزیابی نمی‌کند - فقط
              سرشیفت‌ها را ارزیابی می‌کند، و هر سرشیفت فقط زیرمجموعه اختصاصی خودش را.
            </Typography>
            <Stack direction="row" flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
              {department.shift_leads.map((sl) => (
                <PersonChip key={sl.id} employee={sl.employee} onRemove={() => handleRemoveShiftLead(sl.id)} />
              ))}
            </Stack>
            <EmployeePicker
              siteId={siteId}
              departmentIds={[department.id]}
              label="افزودن سرشیفت (از پرسنل همین واحد)"
              onSelect={handleAddShiftLead}
              excludeIds={assignedEmployeeIds}
            />
          </Box>

          {hasShiftLeads && (
            <Box>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
                تخصیص پرسنل به سرشیفت‌ها
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
                هر پرسنل باید زیرمجموعه دقیقاً یک سرشیفت باشد - پرسنلی که به هیچ سرشیفتی تخصیص داده
                نشود، توسط کسی ارزیابی نمی‌شود.
              </Typography>
              <DepartmentShiftAssignmentTable siteId={siteId} department={department} onAssign={handleAssignShift} />
            </Box>
          )}
        </Stack>
      </AccordionDetails>
    </Accordion>
  );
}

export default function EvaluationStructurePage() {
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState("");
  const [structure, setStructure] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchSites().then((data) => {
      setSites(data);
      if (data.length > 0) setSiteId(data[0].id);
    });
  }, []);

  function loadStructure() {
    if (!siteId) return;
    setError("");
    fetchEvaluationSiteStructure(siteId)
      .then(setStructure)
      .catch((err) => setError(err.response?.data?.detail || "دریافت ساختار ارزیابی با خطا مواجه شد."));
  }

  useEffect(loadStructure, [siteId]);

  async function handleAddSiteManager(employee) {
    try {
      await addSiteManager(siteId, employee.id);
      loadStructure();
    } catch (err) {
      setError(err.response?.data?.detail || "افزودن مدیر سایت با خطا مواجه شد.");
    }
  }

  async function handleRemoveSiteManager(managerId) {
    try {
      await removeSiteManager(managerId);
      loadStructure();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف مدیر سایت با خطا مواجه شد.");
    }
  }

  async function handleAddOtherManager(employee) {
    try {
      await addOtherManager(siteId, employee.id);
      loadStructure();
    } catch (err) {
      setError(err.response?.data?.detail || "افزودن مدیر با خطا مواجه شد.");
    }
  }

  async function handleRemoveOtherManager(managerId) {
    try {
      await removeOtherManager(managerId);
      loadStructure();
    } catch (err) {
      setError(err.response?.data?.detail || "حذف مدیر با خطا مواجه شد.");
    }
  }

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 1 }}>
        ساختار ارزیابی عملکرد
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        مشخص می‌کند چه کسی مجاز به ارزیابی چه کسی است - مستقل از نقش‌ها و مجوزهای عمومی سیستم؛ این
        انتساب‌ها مخصوص همین قابلیت ارزیابی هستند.
      </Typography>

      <TextField
        select
        label="سایت"
        value={siteId}
        onChange={(e) => setSiteId(e.target.value)}
        sx={{ minWidth: 240, mb: 3 }}
      >
        {sites.map((site) => (
          <MenuItem key={site.id} value={site.id}>
            {site.name}
          </MenuItem>
        ))}
      </TextField>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {structure && (
        <Stack spacing={3}>
          <Box>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>
              مدیران سایت
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
              مدیر سایت به‌طور خودکار همه سرپرست‌های واحدها را ارزیابی می‌کند - به‌علاوه هر مدیری که
              پایین‌تر جداگانه اضافه شود.
            </Typography>
            <Stack direction="row" flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
              {structure.site_managers.map((m) => (
                <PersonChip key={m.id} employee={m.employee} onRemove={() => handleRemoveSiteManager(m.id)} />
              ))}
            </Stack>
            <EmployeePicker
              siteId={siteId}
              label="افزودن مدیر سایت (از پرسنل همین سایت)"
              onSelect={handleAddSiteManager}
            />
          </Box>

          <Box>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>
              سایر مدیران (که مدیر سایت ارزیابی می‌کند)
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
              اگر فردی که اینجا اضافه می‌کنید، هم‌زمان سرپرست یک واحد هم باشد، مشکلی نیست - فقط
              یک‌بار در فهرست ارزیابی مدیر سایت ظاهر می‌شود.
            </Typography>
            <Stack direction="row" flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
              {structure.other_managers.map((m) => (
                <PersonChip key={m.id} employee={m.employee} onRemove={() => handleRemoveOtherManager(m.id)} />
              ))}
            </Stack>
            <EmployeePicker
              siteId={siteId}
              label="افزودن مدیر (از پرسنل همین سایت)"
              onSelect={handleAddOtherManager}
            />
          </Box>

          <Box>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1.5 }}>
              واحدهای سازمانی
            </Typography>
            <Stack spacing={1.5}>
              {structure.departments.map((department) => (
                <DepartmentCard
                  key={department.id}
                  siteId={siteId}
                  department={department}
                  onChanged={loadStructure}
                  onError={setError}
                />
              ))}
            </Stack>
          </Box>
        </Stack>
      )}
    </Box>
  );
}
