import { useEffect, useState } from "react";
import {
  Box,
  Card,
  Chip,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { fetchEmployees } from "../api/employees";
import { fetchSites } from "../api/sites";
import { monoFontSx } from "../theme";

export default function EmployeesPage() {
  const [employees, setEmployees] = useState([]);
  const [sites, setSites] = useState([]);
  const [selectedSite, setSelectedSite] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchSites().then(setSites);
  }, []);

  useEffect(() => {
    setIsLoading(true);
    fetchEmployees({ siteId: selectedSite || undefined })
      .then(setEmployees)
      .finally(() => setIsLoading(false));
  }, [selectedSite]);

  const siteNameById = Object.fromEntries(sites.map((s) => [s.id, s.name]));

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 3, flexWrap: "wrap", gap: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            پرسنل
          </Typography>
          <Typography variant="body2" color="text.secondary">
            فهرست پرسنل سینک‌شده از دیتابیس‌های سایت‌ها
          </Typography>
        </Box>
        <TextField
          select
          size="small"
          label="فیلتر بر اساس سایت"
          value={selectedSite}
          onChange={(e) => setSelectedSite(e.target.value)}
          sx={{ minWidth: 220 }}
        >
          <MenuItem value="">همه سایت‌ها</MenuItem>
          {sites.map((site) => (
            <MenuItem key={site.id} value={site.id}>
              {site.name}
            </MenuItem>
          ))}
        </TextField>
      </Box>

      <Card variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>کد پرسنلی</TableCell>
                <TableCell>نام و نام خانوادگی</TableCell>
                <TableCell>کد ملی</TableCell>
                <TableCell>موبایل</TableCell>
                <TableCell>سایت</TableCell>
                <TableCell>وضعیت</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {!isLoading && employees.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6}>
                    <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
                      هیچ پرسنلی یافت نشد. ابتدا از بخش «مدیریت Sync»، همگام‌سازی را برای سایت مورد نظر اجرا کنید.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {employees.map((emp) => (
                <TableRow key={emp.id} hover>
                  <TableCell sx={monoFontSx}>{emp.personnel_code}</TableCell>
                  <TableCell>
                    {emp.first_name} {emp.last_name}
                  </TableCell>
                  <TableCell sx={monoFontSx}>{emp.national_code || "—"}</TableCell>
                  <TableCell sx={monoFontSx}>{emp.mobile || "—"}</TableCell>
                  <TableCell>{siteNameById[emp.site_id] || emp.site_id}</TableCell>
                  <TableCell>
                    <Chip
                      size="small"
                      label={emp.is_active ? "فعال" : "غیرفعال"}
                      color={emp.is_active ? "success" : "default"}
                      variant="outlined"
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>
    </Box>
  );
}
