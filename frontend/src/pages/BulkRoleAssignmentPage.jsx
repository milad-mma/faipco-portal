/**
 * صفحه انتصاب دسته‌جمعی نقش: یک نقش را هم‌زمان به همه پرسنل یک سایت
 * و/یا یک واحد سازمانی اختصاص می‌دهد و پیش از ثبت، تعداد پرسنل منطبق با فیلتر را نشان می‌دهد.
 */
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

// کامپوننت صفحه؛ ورودی ندارد. فرم انتخاب نقش/سایت/واحد و دکمه انتصاب را رندر می‌کند
export default function BulkRoleAssignmentPage() {
  const [roles, setRoles] = useState(null);  // فهرست نقش‌ها (بدون superadmin)؛ null = در حال بارگذاری
  const [sites, setSites] = useState(null);
  const [departments, setDepartments] = useState([]);  // واحدهای سایت انتخاب‌شده

  const [roleId, setRoleId] = useState("");
  const [siteId, setSiteId] = useState("");
  const [departmentId, setDepartmentId] = useState("");

  const [matchingCount, setMatchingCount] = useState(null);  // تعداد پرسنل منطبق با فیلتر فعلی؛ null = فیلتری انتخاب نشده
  const [isLoadingCount, setIsLoadingCount] = useState(false);

  const [isAssigning, setIsAssigning] = useState(false);
  const [result, setResult] = useState(null); // { success, message } | null

  // بارگذاری اولیه نقش‌ها (به‌جز superadmin) و سایت‌ها
  useEffect(() => {
    fetchRoles().then((data) => setRoles(data.filter((r) => r.name !== "superadmin")));
    fetchSites().then(setSites);
  }, []);

  // با تغییر سایت، واحدهای همان سایت بارگذاری و انتخاب واحد پاک می‌شود
  useEffect(() => {
    if (!siteId) {
      setDepartments([]);
      setDepartmentId("");
      return;
    }
    fetchDepartments(siteId).then(setDepartments);
    setDepartmentId("");
  }, [siteId]);

  // شمارش پرسنل منطبق با فیلتر؛ با pageSize=1 فقط مقدار total از سرور خوانده می‌شود
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

  // اعتبارسنجی (نقش و حداقل یک فیلتر الزامی است) و ارسال درخواست انتصاب دسته‌جمعی؛
  // خروجی: پیام موفقیت با تعداد تازه‌منصوب/از قبل دارا/کل منطبق، یا پیام خطا در result
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
      setResult({ success: false, message: err.response?.data?.detail || "انتصاب دسته‌جمعی با خطا مواجه شد." });
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
        {roles === null || sites === null ? (
          <CircularProgress size={20} />
        ) : (
          <Stack spacing={2.5}>
            {/* انتخاب نقش */}
            <TextField select label="نقش" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
              {roles.map((r) => (
                <MenuItem key={r.id} value={r.id}>
                  {r.name} {r.description ? `— ${r.description}` : ""}
                </MenuItem>
              ))}
            </TextField>

            {/* انتخاب سایت (اختیاری؛ «همه سایت‌ها» = بدون فیلتر سایت) */}
            <TextField select label="سایت" value={siteId} onChange={(e) => setSiteId(e.target.value)}>
              <MenuItem value="">همه سایت‌ها</MenuItem>
              {sites.map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  {s.name}
                </MenuItem>
              ))}
            </TextField>

            {/* انتخاب واحد؛ فقط بعد از انتخاب سایت فعال می‌شود */}
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

            {/* نمایش تعداد پرسنل منطبق با فیلتر فعلی */}
            {(siteId || departmentId) && (
              <Alert severity="info">
                {isLoadingCount ? (
                  <CircularProgress size={14} />
                ) : (
                  <>این فیلتر الان روی <strong>{matchingCount} نفر</strong> منطبق است.</>
                )}
              </Alert>
            )}

            {/* پیام نتیجه و دکمه ثبت انتصاب */}
            <Box>
              {result && (
                <Alert severity={result.success ? "success" : "error"} sx={{ mb: 2 }}>
                  {result.message}
                </Alert>
              )}
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
