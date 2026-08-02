import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Card,
  Chip,
  Grid,
  InputAdornment,
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
import SearchOutlinedIcon from "@mui/icons-material/SearchOutlined";
import AdminPanelSettingsOutlinedIcon from "@mui/icons-material/AdminPanelSettingsOutlined";
import { fetchEmployees } from "../api/employees";
import { fetchSites } from "../api/sites";
import { fetchDepartments } from "../api/departments";
import { monoFontSx } from "../theme";
import AssignAccessDialog from "../components/AssignAccessDialog";

export default function AccessManagementPage() {
  const [sites, setSites] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [search, setSearch] = useState("");
  const [results, setResults] = useState([]);
  const [accessEmployee, setAccessEmployee] = useState(null);

  useEffect(() => {
    fetchSites().then(setSites);
    fetchDepartments().then(setDepartments);
  }, []);

  useEffect(() => {
    if (!search) {
      setResults([]);
      return;
    }
    const timer = setTimeout(() => {
      fetchEmployees({ search }).then(setResults);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const siteLabel = (id) => sites.find((s) => s.id === id)?.name || "—";

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        مدیریت دسترسی
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        شخص مورد نظر را از بین پرسنل جستجو کنید و مستقیماً نقش سازمانی (مدیر سایت / مدیر میانی)
        یا سرپرستی یک یا چند واحد را به او اختصاص دهید.
      </Typography>

      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
        <TextField
          fullWidth
          placeholder="جستجو بر اساس نام، کد پرسنلی یا کد ملی..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchOutlinedIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
        />

        {results.length > 0 && (
          <TableContainer sx={{ mt: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>کد پرسنلی</TableCell>
                  <TableCell>نام و نام خانوادگی</TableCell>
                  <TableCell>سایت</TableCell>
                  <TableCell align="center">اقدام</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {results.map((emp) => (
                  <TableRow key={emp.id} hover>
                    <TableCell sx={monoFontSx}>{emp.personnel_code}</TableCell>
                    <TableCell>
                      {emp.first_name} {emp.last_name}
                    </TableCell>
                    <TableCell>{siteLabel(emp.site_id)}</TableCell>
                    <TableCell align="center">
                      <Button
                        size="small"
                        startIcon={<AdminPanelSettingsOutlinedIcon />}
                        onClick={() => setAccessEmployee(emp)}
                      >
                        دسترسی
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
        {search && results.length === 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            پرسنلی با این عبارت پیدا نشد.
          </Typography>
        )}
      </Card>

      <Grid container spacing={2.5}>
        <Grid item xs={12}>
          <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 2 }}>
              نمای کلی سرپرستی واحدها
            </Typography>
            <Stack spacing={1.5}>
              {departments.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  هنوز هیچ واحد سازمانی‌ای ثبت نشده — واحدها معمولاً خودکار از Sync ساخته می‌شوند.
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
                    سرپرست: {dept.supervisor_name || "— بدون سرپرست —"}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </Card>
        </Grid>
      </Grid>

      <AssignAccessDialog employee={accessEmployee} sites={sites} onClose={() => setAccessEmployee(null)} />
    </Box>
  );
}
