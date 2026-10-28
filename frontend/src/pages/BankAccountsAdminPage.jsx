/**
 * پنل «اطلاعات بانکی پرسنل» (docs/bank-accounts.md):
 * - تب «گزارش» (bank_accounts.view): پرسنل فعال × بانک‌های سایت با وضعیت تکمیل، جست‌وجو، فیلتر، خروجی Excel،
 *   سابقه‌ی تغییرات هر پرسنل و (با bank_accounts.manage) اصلاح اطلاعات.
 * - تب «بانک‌ها» (bank_accounts.manage): تعریف بانک‌های هر سایت، اجباری/اختیاری بودن و حالت هر فیلد.
 */
import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  MenuItem,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import HistoryOutlinedIcon from "@mui/icons-material/HistoryOutlined";
import BackLink from "../components/BackLink";
import BankAccountForm from "../components/BankAccountForm";
import PillTabs from "../components/PillTabs";
import SearchField from "../components/SearchField";
import SiteFilterSelect from "../components/SiteFilterSelect";
import { useAuth } from "../context/AuthContext";
import useDebounced from "../hooks/useDebounced";
import { fetchMyAccessibleSites, fetchSites } from "../api/sites";
import {
  addSiteBank,
  adminSaveBankAccount,
  deleteBank,
  exportBankReport,
  fetchBankReport,
  fetchEmployeeBankHistory,
  fetchSiteBanks,
  updateBank,
} from "../api/bankAccounts";
import { BANK_FIELDS, MODE_LABELS, formatBankValue } from "../utils/bank";
import { compactTableSx, faDateTime, hideXs } from "../utils/dateTimeFa";
import { BankHistoryList } from "./BankInfoPage";

function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export default function BankAccountsAdminPage() {
  const { user } = useAuth();
  const canManage = Boolean(user?.can_manage_bank_accounts);
  const [tab, setTab] = useState("report");
  const tabs = [
    { key: "report", label: "گزارش" },
    ...(canManage ? [{ key: "banks", label: "بانک‌ها" }] : []),
  ];
  return (
    <Box>
      <BackLink to="/" label="بازگشت" />
      <Typography variant="h5" fontWeight={800} sx={{ mb: 2 }}>
        اطلاعات بانکی پرسنل
      </Typography>
      {tabs.length > 1 && <PillTabs tabs={tabs} value={tab} onChange={setTab} sx={{ maxWidth: 360 }} />}
      {tab === "report" ? <ReportTab canManage={canManage} /> : <BanksTab />}
    </Box>
  );
}

// ---------- گزارش ----------

function ReportTab({ canManage }) {
  const [siteId, setSiteId] = useState(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const debouncedSearch = useDebounced(search);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [historyFor, setHistoryFor] = useState(null); // {employee, items}
  const [editFor, setEditFor] = useState(null); // ردیف پرسنل

  const load = useCallback(() => {
    const params = { site_id: siteId || undefined, search: debouncedSearch || undefined, status: status || undefined };
    return fetchBankReport(params)
      .then((d) => {
        setData(d);
        setError("");
      })
      .catch((err) => setError(err.response?.data?.detail || "دریافت گزارش با خطا مواجه شد."));
  }, [siteId, debouncedSearch, status]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleExport() {
    setExporting(true);
    try {
      const blob = await exportBankReport({ site_id: siteId || undefined, status: status || undefined });
      saveBlob(blob, "bank_accounts.xlsx");
    } catch {
      setError("دریافت خروجی Excel با خطا مواجه شد.");
    } finally {
      setExporting(false);
    }
  }

  function openHistory(item) {
    setHistoryFor({ item, items: null });
    fetchEmployeeBankHistory(item.employee_id)
      .then((items) => setHistoryFor({ item, items }))
      .catch(() => setHistoryFor({ item, items: [] }));
  }

  const banksById = Object.fromEntries((data?.banks || []).map((b) => [b.id, b]));

  return (
    <Box>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1.5}
        alignItems={{ xs: "stretch", sm: "flex-end" }}
        sx={{ mb: 2 }}
      >
        <SearchField value={search} onChange={setSearch} sx={{ maxWidth: { sm: 300 } }} />
        <SiteFilterSelect value={siteId} onChange={setSiteId} permission="bank_accounts.view" />
        <TextField
          select
          size="small"
          label="وضعیت"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          sx={{ minWidth: 150 }}
        >
          <MenuItem value="">همه</MenuItem>
          <MenuItem value="missing">تکمیل نشده</MenuItem>
          <MenuItem value="complete">تکمیل</MenuItem>
        </TextField>
        <Button
          variant="outlined"
          startIcon={exporting ? <CircularProgress size={16} /> : <FileDownloadOutlinedIcon />}
          onClick={handleExport}
          disabled={exporting}
          sx={{ height: 40 }}
        >
          خروجی Excel
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {!data && !error && <CircularProgress size={24} />}

      {data && (
        <>
          <Stack direction="row" spacing={1} sx={{ mb: 1.5 }} flexWrap="wrap" useFlexGap>
            <Chip size="small" label={`کل: ${data.counts.total}`} />
            <Chip size="small" color="success" variant="outlined" label={`تکمیل: ${data.counts.complete}`} />
            <Chip size="small" color="warning" variant="outlined" label={`تکمیل نشده: ${data.counts.missing}`} />
          </Stack>
          {data.banks.length === 0 && (
            <Alert severity="info" sx={{ mb: 2 }}>
              هنوز بانکی برای سایت{siteId ? "" : "‌ها"} تعریف نشده است{canManage ? " — از تب «بانک‌ها» اضافه کنید." : "."}
            </Alert>
          )}
          <Card variant="outlined" sx={{ borderRadius: 2 }}>
            <TableContainer>
              <Table size="small" sx={compactTableSx}>
                <TableHead>
                  <TableRow>
                    <TableCell>پرسنل</TableCell>
                    <TableCell sx={hideXs}>واحد</TableCell>
                    <TableCell>اطلاعات بانکی</TableCell>
                    <TableCell>وضعیت</TableCell>
                    <TableCell align="center">عملیات</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.items.map((item) => (
                    <TableRow key={item.employee_id}>
                      <TableCell>
                        {item.first_name} {item.last_name}
                        <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                          {item.personnel_code}
                          {!siteId && item.site_name ? ` — ${item.site_name}` : ""}
                        </Typography>
                      </TableCell>
                      <TableCell sx={hideXs}>{item.department_name || "—"}</TableCell>
                      <TableCell>
                        {item.accounts.map((acc) => {
                          const bank = banksById[acc.bank_id];
                          if (!bank) return null;
                          return (
                            <Box key={acc.bank_id} sx={{ mb: 0.5 }}>
                              <Typography variant="caption" fontWeight={700}>
                                {bank.name}
                              </Typography>
                              {BANK_FIELDS.filter((f) => bank[`${f.key}_mode`] !== "hidden").map((f) => (
                                <Typography key={f.key} variant="caption" sx={{ display: "block" }}>
                                  {f.label}:{" "}
                                  <Box component="span" dir="ltr">
                                    {formatBankValue(f.key, acc.account?.[f.key])}
                                  </Box>
                                </Typography>
                              ))}
                            </Box>
                          );
                        })}
                      </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          variant="outlined"
                          color={item.missing_required ? "warning" : "success"}
                          label={item.missing_required ? "تکمیل نشده" : "تکمیل"}
                        />
                        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
                          {item.terms_accepted_at
                            ? `تعهد: ${faDateTime(item.terms_accepted_at)}`
                            : "تعهد پذیرفته نشده"}
                        </Typography>
                      </TableCell>
                      <TableCell align="center" sx={{ whiteSpace: "nowrap" }}>
                        <Tooltip title="سابقه‌ی تغییرات">
                          <IconButton size="small" onClick={() => openHistory(item)}>
                            <HistoryOutlinedIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        {canManage && (
                          <Tooltip title="اصلاح">
                            <IconButton size="small" onClick={() => setEditFor(item)}>
                              <EditOutlinedIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {data.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} align="center">
                        موردی یافت نشد.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Card>
        </>
      )}

      {/* سابقه‌ی تغییرات یک پرسنل */}
      <Dialog open={Boolean(historyFor)} onClose={() => setHistoryFor(null)} fullWidth maxWidth="sm">
        <DialogTitle>
          سابقه‌ی تغییرات — {historyFor?.item.first_name} {historyFor?.item.last_name}
        </DialogTitle>
        <DialogContent>{historyFor && <BankHistoryList items={historyFor.items} />}</DialogContent>
        <DialogActions>
          <Button onClick={() => setHistoryFor(null)}>بستن</Button>
        </DialogActions>
      </Dialog>

      {/* اصلاح اطلاعات یک پرسنل (منابع انسانی) */}
      <Dialog open={Boolean(editFor)} onClose={() => setEditFor(null)} fullWidth maxWidth="sm">
        <DialogTitle>
          اصلاح اطلاعات بانکی — {editFor?.first_name} {editFor?.last_name}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2.5} sx={{ pt: 1 }}>
            {editFor?.accounts.map((acc) => {
              const bank = banksById[acc.bank_id];
              if (!bank) return null;
              return (
                <Box key={acc.bank_id}>
                  <Typography fontWeight={700} sx={{ mb: 1 }}>
                    {bank.name}
                  </Typography>
                  <BankAccountForm
                    bank={{ ...bank, account: acc.account }}
                    onSave={async (payload) => {
                      const info = await adminSaveBankAccount(editFor.employee_id, bank.id, payload);
                      const fresh = Object.fromEntries(info.banks.map((b) => [b.id, b.account]));
                      setEditFor((prev) =>
                        prev && {
                          ...prev,
                          accounts: prev.accounts.map((a) => ({ ...a, account: fresh[a.bank_id] ?? a.account })),
                        },
                      );
                      load();
                    }}
                  />
                </Box>
              );
            })}
            <Typography variant="caption" color="text.secondary">
              تغییرات با نام شما در سابقه‌ی پرسنل ثبت می‌شود.
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditFor(null)}>بستن</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

// ---------- تعریف بانک‌ها ----------

const EMPTY_BANK = {
  name: "",
  is_required: true,
  account_number_mode: "required",
  sheba_mode: "required",
  card_number_mode: "optional",
  is_active: true,
};

function BanksTab() {
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState(null);
  const [banks, setBanks] = useState(null);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState(null); // {id?, ...fields}
  const [saving, setSaving] = useState(false);
  const [toDelete, setToDelete] = useState(null);

  // سایت‌هایی که کاربر برایشان bank_accounts.manage دارد؛ پیش‌فرض اولین سایت
  useEffect(() => {
    fetchMyAccessibleSites("bank_accounts.manage").then(async ({ unrestricted, sites: accessible }) => {
      const list = unrestricted ? await fetchSites() : accessible;
      setSites(list);
      setSiteId((current) => current ?? list[0]?.id ?? null);
    });
  }, []);

  const load = useCallback(() => {
    if (!siteId) return;
    setBanks(null);
    fetchSiteBanks(siteId)
      .then(setBanks)
      .catch((err) => setError(err.response?.data?.detail || "دریافت بانک‌ها با خطا مواجه شد."));
  }, [siteId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const { id, ...payload } = dialog;
      if (id) await updateBank(id, payload);
      else await addSiteBank(siteId, payload);
      setDialog(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره‌ی بانک با خطا مواجه شد.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setError("");
    try {
      await deleteBank(toDelete.id);
      setToDelete(null);
      load();
    } catch (err) {
      setToDelete(null);
      setError(err.response?.data?.detail || "حذف بانک با خطا مواجه شد.");
    }
  }

  async function toggleActive(bank) {
    try {
      await updateBank(bank.id, { is_active: !bank.is_active });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "تغییر وضعیت بانک با خطا مواجه شد.");
    }
  }

  return (
    <Box>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1.5}
        alignItems={{ xs: "stretch", sm: "flex-end" }}
        sx={{ mb: 2 }}
      >
        {sites.length > 1 && (
          <TextField
            select
            size="small"
            label="سایت"
            value={siteId ?? ""}
            onChange={(e) => setSiteId(Number(e.target.value))}
            sx={{ minWidth: 200 }}
          >
            {sites.map((s) => (
              <MenuItem key={s.id} value={s.id}>
                {s.name}
              </MenuItem>
            ))}
          </TextField>
        )}
        <Button
          variant="contained"
          startIcon={<AddOutlinedIcon />}
          onClick={() => setDialog({ ...EMPTY_BANK })}
          disabled={!siteId}
          sx={{ height: 40 }}
        >
          افزودن بانک
        </Button>
      </Stack>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {siteId && banks === null && <CircularProgress size={24} />}

      {banks && (
        <Card variant="outlined" sx={{ borderRadius: 2 }}>
          <TableContainer>
            <Table size="small" sx={compactTableSx}>
              <TableHead>
                <TableRow>
                  <TableCell>بانک</TableCell>
                  <TableCell>الزام</TableCell>
                  <TableCell sx={hideXs}>شماره حساب</TableCell>
                  <TableCell sx={hideXs}>شبا</TableCell>
                  <TableCell sx={hideXs}>شماره کارت</TableCell>
                  <TableCell>فعال</TableCell>
                  <TableCell align="center">عملیات</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {banks.map((bank) => (
                  <TableRow key={bank.id}>
                    <TableCell>{bank.name}</TableCell>
                    <TableCell>{bank.is_required ? "اجباری" : "اختیاری"}</TableCell>
                    {BANK_FIELDS.map((f) => (
                      <TableCell key={f.key} sx={hideXs}>
                        {MODE_LABELS[bank[`${f.key}_mode`]]}
                      </TableCell>
                    ))}
                    <TableCell>
                      <Switch size="small" checked={bank.is_active} onChange={() => toggleActive(bank)} />
                    </TableCell>
                    <TableCell align="center" sx={{ whiteSpace: "nowrap" }}>
                      <IconButton size="small" onClick={() => setDialog({ ...bank })}>
                        <EditOutlinedIcon fontSize="small" />
                      </IconButton>
                      <IconButton size="small" onClick={() => setToDelete(bank)}>
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
                {banks.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      هنوز بانکی برای این سایت تعریف نشده است.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Card>
      )}

      {/* افزودن/ویرایش بانک */}
      <Dialog open={Boolean(dialog)} onClose={() => setDialog(null)} fullWidth maxWidth="xs">
        <DialogTitle>{dialog?.id ? "ویرایش بانک" : "افزودن بانک"}</DialogTitle>
        <DialogContent>
          {dialog && (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <TextField
                size="small"
                label="نام بانک"
                value={dialog.name}
                onChange={(e) => setDialog((d) => ({ ...d, name: e.target.value }))}
                inputProps={{ maxLength: 100 }}
                autoFocus
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={dialog.is_required}
                    onChange={(e) => setDialog((d) => ({ ...d, is_required: e.target.checked }))}
                  />
                }
                label="پرسنل باید اطلاعات این بانک را وارد کنند (اجباری)"
              />
              {BANK_FIELDS.map((f) => (
                <TextField
                  key={f.key}
                  select
                  size="small"
                  label={f.label}
                  value={dialog[`${f.key}_mode`]}
                  onChange={(e) => setDialog((d) => ({ ...d, [`${f.key}_mode`]: e.target.value }))}
                >
                  {Object.entries(MODE_LABELS).map(([value, label]) => (
                    <MenuItem key={value} value={value}>
                      {label}
                    </MenuItem>
                  ))}
                </TextField>
              ))}
              <FormControlLabel
                control={
                  <Switch
                    checked={dialog.is_active}
                    onChange={(e) => setDialog((d) => ({ ...d, is_active: e.target.checked }))}
                  />
                }
                label="فعال (در فرم پرسنل نمایش داده شود)"
              />
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog(null)}>انصراف</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving || !dialog?.name?.trim()}>
            ذخیره
          </Button>
        </DialogActions>
      </Dialog>

      {/* تأیید حذف */}
      <Dialog open={Boolean(toDelete)} onClose={() => setToDelete(null)}>
        <DialogTitle>حذف بانک</DialogTitle>
        <DialogContent>
          «{toDelete?.name}» حذف شود؟ اگر پرسنلی برای این بانک اطلاعات ثبت کرده باشد حذف نمی‌شود و باید آن را
          غیرفعال کنید.
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setToDelete(null)}>انصراف</Button>
          <Button color="error" variant="contained" onClick={handleDelete}>
            حذف
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
