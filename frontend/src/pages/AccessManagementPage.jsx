import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  Grid,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import { fetchSites } from "../api/sites";
import { createDepartment, fetchDepartments } from "../api/departments";
import { fetchUsers } from "../api/users";

export default function AccessManagementPage() {
  const [sites, setSites] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [users, setUsers] = useState([]);
  const [newDept, setNewDept] = useState({ site_id: "", name: "", code: "" });
  const [error, setError] = useState("");

  useEffect(() => {
    fetchSites().then(setSites);
    fetchDepartments().then(setDepartments);
    fetchUsers().then(setUsers);
  }, []);

  const siteLabel = (id) => sites.find((s) => s.id === id)?.name || "—";
  const supervisorLabel = (userId) => {
    if (!userId) return "— بدون سرپرست —";
    return users.find((u) => u.id === userId)?.username || `کاربر #${userId}`;
  };

  async function handleCreateDepartment() {
    setError("");
    try {
      await createDepartment(newDept);
      setNewDept({ site_id: "", name: "", code: "" });
      setDepartments(await fetchDepartments());
    } catch (err) {
      setError(err.response?.data?.detail || "ساخت واحد سازمانی ناموفق بود");
    }
  }

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        مدیریت دسترسی
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        واحدهای سازمانی را اینجا بسازید. انتصاب نقش (مدیرعامل/HR/مدیر سایت) و
        تعیین سرپرست هر واحد از صفحه «پرسنل» و مستقیماً از روی خودِ شخص انجام می‌شود.
      </Typography>

      <Alert severity="info" icon={<InfoOutlinedIcon />} sx={{ mb: 3 }}>
        برای دادن دسترسی به یک نفر: به صفحه «پرسنل» بروید، او را جستجو کنید و دکمه
        «دسترسی» را بزنید.
      </Alert>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2.5}>
        <Grid item xs={12} md={7}>
          <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
              واحدهای سازمانی
            </Typography>
            <Stack spacing={1.5}>
              {departments.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  هنوز هیچ واحد سازمانی‌ای ساخته نشده.
                </Typography>
              )}
              {departments.map((dept) => (
                <Box
                  key={dept.id}
                  sx={{
                    p: 1.5,
                    border: "1px solid",
                    borderColor: "divider",
                    borderRadius: 2,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 1,
                  }}
                >
                  <Box>
                    <Typography variant="body2" fontWeight={600}>
                      {dept.name}
                    </Typography>
                    <Chip size="small" label={siteLabel(dept.site_id)} sx={{ mt: 0.5 }} />
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    سرپرست: {supervisorLabel(dept.supervisor_user_id)}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </Card>
        </Grid>

        <Grid item xs={12} md={5}>
          <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
              واحد سازمانی جدید
            </Typography>
            <Stack spacing={1.5}>
              <TextField
                select
                size="small"
                label="سایت"
                value={newDept.site_id}
                onChange={(e) => setNewDept({ ...newDept, site_id: e.target.value })}
              >
                {sites.map((s) => (
                  <MenuItem key={s.id} value={s.id}>
                    {s.name}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                size="small"
                label="نام واحد"
                value={newDept.name}
                onChange={(e) => setNewDept({ ...newDept, name: e.target.value })}
              />
              <TextField
                size="small"
                label="کد واحد"
                value={newDept.code}
                onChange={(e) => setNewDept({ ...newDept, code: e.target.value })}
              />
              <Button variant="contained" onClick={handleCreateDepartment}>
                ساخت واحد
              </Button>
            </Stack>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
