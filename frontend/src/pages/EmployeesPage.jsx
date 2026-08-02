import { useEffect, useState } from "react";
import {
  Box,
  Card,
  Chip,
  InputAdornment,
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
import SearchOutlinedIcon from "@mui/icons-material/SearchOutlined";
import { fetchEmployees } from "../api/employees";
import { fetchSites } from "../api/sites";
import { monoFontSx } from "../theme";

export default function EmployeesPage() {
  const [employees, setEmployees] = useState([]);
  const [sites, setSites] = useState([]);
  const [selectedSite, setSelectedSite] = useState("");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchSites().then(setSites);
  }, []);

  useEffect(() => {
    setIsLoading(true);
    const timer = setTimeout(() => {
      fetchEmployees({ siteId: selectedSite || undefined, search: search || undefined })
        .then(setEmployees)
        .finally(() => setIsLoading(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [selectedSite, search]);

  const siteNameById = Object.fromEntries(sites.map((s) => [s.id, s.name]));

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" fontWeight={700}>
          پرسنل
        </Typography>
        <Typography variant="body2" color="text.secondary">
          فهرست پرسنل سینک‌شده از دیتابیس‌های سایت‌ها. برای دادن دسترسی به کسی، از
          صفحه «مدیریت دسترسی» استفاده کنید.
        </Typography>
      </Box>

      <Box sx={{ display: "flex", gap: 2, mb: 3, flexWrap: "wrap" }}>
        <TextField
          size="small"
          placeholder="جستجو بر اساس نام، کد پرسنلی یا کد ملی..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ minWidth: 280, flexGrow: 1 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchOutlinedIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
        />
        <TextField
          select
          size="small"
          label="فیلتر بر اساس سایت"
          value={selectedSite}
          onChange={(e) => setSelectedSite(e.target.value)}
          sx={{ minWidth: 200 }}
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
                      {search
                        ? "با این عبارت جستجو، پرسنلی یافت نشد."
                        : "هیچ پرسنلی یافت نشد. ابتدا از بخش «مدیریت Sync»، همگام‌سازی را اجرا کنید."}
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
