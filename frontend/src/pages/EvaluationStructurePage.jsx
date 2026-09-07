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
import HelpOutlineOutlinedIcon from "@mui/icons-material/HelpOutlineOutlined";
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
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        مشخص می‌کند چه کسی مجاز به ارزیابی چه کسی است - مستقل از نقش‌ها و مجوزهای عمومی سیستم؛ این
        انتساب‌ها مخصوص همین قابلیت ارزیابی هستند.
      </Typography>

      <Accordion variant="outlined" sx={{ mb: 3 }}>
        <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
          <Stack direction="row" spacing={1} alignItems="center">
            <HelpOutlineOutlinedIcon fontSize="small" color="primary" />
            <Typography fontWeight={700}>راهنما - این صفحه چیکار می‌کنه؟</Typography>
          </Stack>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" sx={{ mb: 1.5 }}>
            این صفحه فقط یه چیز رو مشخص می‌کنه: <b>کی مجاز به ارزیابی‌کردن کیه</b>. سوال‌ها و فرم‌ها
            جای دیگه‌ای (صفحه «فرم‌های ارزیابی») ساخته می‌شن؛ اینجا فقط سلسله‌مراتب سازمانی رو مشخص
            می‌کنید.
          </Typography>
          <Typography variant="body2" fontWeight={700} sx={{ mb: 0.5 }}>
            قانون کلی (ساده):
          </Typography>
          <Stack component="ul" sx={{ pl: 2.5, m: 0, mb: 1.5 }} spacing={0.5}>
            <Typography component="li" variant="body2">
              <b>مدیر سایت</b> → سرپرست‌های همه واحدهای همون سایت + هر مدیر دیگه‌ای که زیر «سایر
              مدیران» اضافه کنید رو ارزیابی می‌کنه.
            </Typography>
            <Typography component="li" variant="body2">
              <b>سرپرست واحد</b> → همه پرسنل واحدش رو ارزیابی می‌کنه (مگه این‌که برای اون واحد سرشیفت
              هم تعریف کرده باشید - اون‌وقت فقط سرشیفت‌ها رو ارزیابی می‌کنه).
            </Typography>
            <Typography component="li" variant="body2">
              <b>سرشیفت</b> (اختیاری) → فقط پرسنلی که به خودش تخصیص داده شده رو ارزیابی می‌کنه.
            </Typography>
          </Stack>
          <Typography variant="body2" fontWeight={700} sx={{ mb: 0.5 }}>
            چطور شروع کنم؟
          </Typography>
          <Stack component="ol" sx={{ pl: 2.5, m: 0 }} spacing={0.5}>
            <Typography component="li" variant="body2">
              یه سایت رو از منوی بالا انتخاب کنید.
            </Typography>
            <Typography component="li" variant="body2">
              اگه سایت مدیر داره، توی «مدیران سایت» از بین پرسنل انتخابش کنید (می‌تونید چند نفر اضافه
              کنید).
            </Typography>
            <Typography component="li" variant="body2">
              برای هر واحد سازمانی که پایین صفحه لیست شده، روش کلیک کنید و یه سرپرست انتخاب کنید (از
              بین کل پرسنل سایت - لازم نیست حتماً عضو همون واحد باشه).
            </Typography>
            <Typography component="li" variant="body2">
              فقط اگه واقعاً نیاز دارید (مثلاً واحد بزرگه و چند شیفت داره)، سرشیفت هم اضافه کنید و
              پرسنل رو بینشون تقسیم کنید. اگه نیازی نیست، همین‌جوری رهاش کنید - سرپرست خودش کل واحد رو
              ارزیابی می‌کنه.
            </Typography>
          </Stack>
        </AccordionDetails>
      </Accordion>

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
