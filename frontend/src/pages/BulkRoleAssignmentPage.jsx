import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import GroupAddOutlinedIcon from "@mui/icons-material/GroupAddOutlined";
import { fetchRoles, bulkAssignRole } from "../api/users";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import { fetchEmployees } from "../api/employees";

export default function BulkRoleAssignmentPage() {
  const [roles, setRoles] = useState(null);
  const [sites, setSites] = useState(null);
  const [departments, setDepartments] = useState([]);

  const [roleId, setRoleId] = useState("");
  const [siteId, setSiteId] = useState("");
  const [departmentId, setDepartmentId] = useState("");

  const [matchingCount, setMatchingCount] = useState(null);
  const [isLoadingCount, setIsLoadingCount] = useState(false);

  const [isAssigning, setIsAssigning] = useState(false);
  const [result, setResult] = useState(null); // { success, message } | null

  useEffect(() => {
    fetchRoles().then((data) => setRoles(data.filter((r) => r.name !== "superadmin")));
    fetchSites().then(setSites);
  }, []);

  useEffect(() => {
    if (!siteId) {
      setDepartments([]);
      setDepartmentId("");
      return;
    }
    fetchDepartments(siteId).then(setDepartments);
    setDepartmentId("");
  }, [siteId]);

  useEffect(() => {
    if (!siteId && !departmentId) {
      setMatchingCount(null);
      return;
    }
    setIsLoadingCount(true);
    fetchEmployees({
      siteId: siteId || undefined,
      departmentIds: departmentId ? [departmentId] : undefined,
      pageSize: 1,
    })
      .then((data) => setMatchingCount(data.total))
      .finally(() => setIsLoadingCount(false));
  }, [siteId, departmentId]);

  async function handleAssign() {
    setResult(null);
    if (!roleId) {
      setResult({ success: false, message: "یک نقش انتخاب کنید." });
      return;
    }
    if (!siteId && !departmentId) {
      setResult({ success: false, message: "حداقل یک سایت یا واحد سازمانی برای فیلتر انتخاب کنید." });
      return;
    }
    setIsAssigning(true);
    try {
      const data = await bulkAssignRole({
        roleId,
        siteId: siteId || undefined,
        departmentId: departmentId || undefined,
      });
      setResult({
        success: true,
        message: `${data.assigned_count} نفر تازه این نقش را گرفتند. ${data.already_had_count} نفر از قبل داشتند (نادیده گرفته شد). مجموع پرسنل مطابق فیلتر: ${data.total_matched} نفر.`,
      });
    } catch (err) {
      setResult({ success: false, message: err.response?.data?.detail || "انتصاب دسته‌جمعی ناموفق بود." });
    } finally {
      setIsAssigning(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        انتصاب دسته‌جمعی نقش
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        یک نقش (مثلاً «attendance-pilot») را هم‌زمان به همه پرسنل یک سایت یا یک واحد سازمانی خاص
        اختصاص می‌دهد — بدون نیاز به انتخاب یکی‌یکی. پرسنلی که هنوز هیچ‌وقت وارد پرتال نشده هم
        مشکلی ندارد؛ حساب کاربری‌شان همین‌جا خودکار ساخته می‌شود.
      </Typography>

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
        {result && (
          <Alert severity={result.success ? "success" : "error"} sx={{ mb: 2 }}>
            {result.message}
          </Alert>
        )}

        {roles === null || sites === null ? (
          <CircularProgress size={20} />
        ) : (
          <Stack spacing={2.5}>
            <TextField select label="نقش" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
              {roles.map((r) => (
                <MenuItem key={r.id} value={r.id}>
                  {r.name} {r.description ? `— ${r.description}` : ""}
                </MenuItem>
              ))}
            </TextField>

            <TextField select label="سایت" value={siteId} onChange={(e) => setSiteId(e.target.value)}>
              <MenuItem value="">همه سایت‌ها</MenuItem>
              {sites.map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.name}
                </MenuItem>
              ))}
            </TextField>

            <TextField
              select
              label="واحد سازمانی (اختیاری)"
              value={departmentId}
              onChange={(e) => setDepartmentId(e.target.value)}
              disabled={!siteId || departments.length === 0}
              helperText={!siteId ? "اول یک سایت انتخاب کنید" : ""}
            >
              <MenuItem value="">همه واحدها</MenuItem>
              {departments.map((d) => (
                <MenuItem key={d.id} value={d.id}>
                  {d.name}
                </MenuItem>
              ))}
            </TextField>

            {(siteId || departmentId) && (
              <Alert severity="info">
                {isLoadingCount ? (
                  <CircularProgress size={14} />
                ) : (
                  <>این فیلتر الان روی <strong>{matchingCount} نفر</strong> منطبق است.</>
                )}
              </Alert>
            )}

            <Box>
              <Button
                variant="contained"
                startIcon={isAssigning ? <CircularProgress size={18} color="inherit" /> : <GroupAddOutlinedIcon />}
                onClick={handleAssign}
                disabled={isAssigning || !roleId || (!siteId && !departmentId)}
              >
                {isAssigning ? "در حال انتصاب..." : "اختصاص نقش به این گروه"}
              </Button>
            </Box>
          </Stack>
        )}
      </Card>
    </Box>
  );
}
