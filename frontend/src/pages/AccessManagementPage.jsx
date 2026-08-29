import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
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
import { fetchMyAccessibleSites, fetchSites } from "../api/sites";
import { fetchAccessOverview } from "../api/users";
import { monoFontSx } from "../theme";
import { roleDisplayName } from "../utils/roleLabels";
import AssignAccessDialog from "../components/AssignAccessDialog";

export default function AccessManagementPage() {
  const [sites, setSites] = useState([]);
  const [overview, setOverview] = useState(null);
  const [mySiteIds, setMySiteIds] = useState(undefined); // undefined = هنوز لود نشده، null = نامحدود

  const [search, setSearch] = useState("");
  const [results, setResults] = useState([]);
  const [accessEmployee, setAccessEmployee] = useState(null);

  useEffect(() => {
    fetchSites().then(setSites);
    loadOverview();
    // ⚠️ رفع یک نقص واقعی امنیتی/UX: قبلاً جست‌وجوی پرسنل اینجا هیچ
    // محدودیت سایتی نداشت — کسی با users.manage فقط برای یک سایت،
    // می‌توانست پرسنل *همه* سایت‌های دیگر را هم جست‌وجو/پیدا کند (که
    // البته حالا Backend اختصاص نقش برایشان را رد می‌کند، ولی همچنان
    // گیج‌کننده بود که اصلاً در نتایج جست‌وجو ظاهر شوند).
    fetchMyAccessibleSites("users.manage").then(({ unrestricted, sites: accessibleSites }) => {
      setMySiteIds(unrestricted ? null : accessibleSites.map((s) => s.id));
    });
  }, []);

  function loadOverview() {
    fetchAccessOverview().then(setOverview);
  }

  useEffect(() => {
    if (!search || mySiteIds === undefined) {
      setResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      if (mySiteIds === null) {
        // نامحدود — یک جست‌وجوی ساده کافی است
        const data = await fetchEmployees({ search });
        setResults(data.items);
      } else {
        // محدود به چند سایت خاص — چون fetchEmployees فقط یک siteId
        // می‌گیرد، برای هر سایت مجاز جدا جست‌وجو و نتایج را با هم ادغام می‌کنیم
        const pages = await Promise.all(mySiteIds.map((siteId) => fetchEmployees({ search, siteId })));
        setResults(pages.flatMap((p) => p.items));
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [search, mySiteIds]);

  const siteLabel = (id) => sites.find((s) => s.id === id)?.name || "—";

  function closeAccessDialog() {
    setAccessEmployee(null);
    loadOverview(); // بعد از تغییر احتمالی، جدول نمای کلی را تازه کن
  }

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
          placeholder="جستجو بر اساس نام، کد پرسنلی یا کد ملی برای دادن دسترسی جدید..."
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

      {/* جدول جداگانه: همه کسانی که هر نوع دسترسی/نقشی دارند */}
      <Card variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
        <Box sx={{ p: 3, pb: 0 }}>
          <Typography variant="subtitle1" fontWeight={700}>
            نمای کلی دسترسی‌ها
          </Typography>
          <Typography variant="body2" color="text.secondary">
            همه پرسنلی که هر نوع نقش سازمانی یا سرپرستی واحد دارند
          </Typography>
        </Box>
        <TableContainer sx={{ mt: 2 }}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>کد پرسنلی</TableCell>
                <TableCell>نام و نام خانوادگی</TableCell>
                <TableCell>سایت</TableCell>
                <TableCell>نقش‌ها</TableCell>
                <TableCell>سرپرست کدام واحدها</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {overview === null ? (
                <TableRow>
                  <TableCell colSpan={5}>
                    <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
                      <CircularProgress size={24} />
                    </Box>
                  </TableCell>
                </TableRow>
              ) : (
                <>
                  {overview.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5}>
                        <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
                          هنوز هیچ‌کس نقش سازمانی یا سرپرستی واحدی ندارد.
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                  {overview.map((entry) => (
                <TableRow key={entry.employee_id} hover>
                  <TableCell sx={monoFontSx}>{entry.personnel_code}</TableCell>
                  <TableCell>
                    {entry.first_name} {entry.last_name}
                  </TableCell>
                  <TableCell>{entry.site_name}</TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                      {entry.roles.length === 0 && (
                        <Typography variant="caption" color="text.secondary">
                          —
                        </Typography>
                      )}
                      {entry.roles.map((r, i) => (
                        <Chip
                          key={i}
                          size="small"
                          color="primary"
                          variant="outlined"
                          label={
                            roleDisplayName(r.role_name) +
                            (r.site_name ? ` — ${r.site_name}` : " (سراسری)")
                          }
                        />
                      ))}
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                      {entry.supervised_departments.length === 0 && (
                        <Typography variant="caption" color="text.secondary">
                          —
                        </Typography>
                      )}
                      {entry.supervised_departments.map((d) => (
                        <Chip key={d.id} size="small" label={`${d.name} (${d.site_name})`} />
                      ))}
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
                </>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>

      <AssignAccessDialog
        employee={accessEmployee}
        sites={mySiteIds === null || mySiteIds === undefined ? sites : sites.filter((s) => mySiteIds.includes(s.id))}
        onClose={closeAccessDialog}
      />
    </Box>
  );
}
