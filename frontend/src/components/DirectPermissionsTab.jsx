/**
 * تب «مجوزهای مستقیم» دیالوگ دسترسی پرسنل (Migration 106؛ docs/rbac.md).
 *
 * جدول ماتریسی: هر مجوز یک ردیف، هر سایت یک ستون چک‌باکس (+ ستون «همه‌ی سایت‌ها» برای مدیر نامحدود). حالت درختی حفظ
 * شده: مجوزها با پیشوند کد گروه‌بندی می‌شوند و ردیف گروه (باز/بسته) برای هر ستون یک چک‌باکس «همه‌ی مجوزهای گروه» دارد.
 * - تیک «همه‌ی سایت‌ها» = مجوز برای همه‌ی سایت‌ها و سایت‌های آینده (همه‌ی ستون‌ها تیک می‌خورند)؛ برداشتن یک سایت از آن،
 *   مجوز را به بقیه‌ی سایت‌ها محدود می‌کند؛ برداشتن «همه» کل مجوز را برمی‌دارد.
 * - مجوزی که از نقش می‌رسد در همان خانه خاکستری (تیک‌خورده و غیرفعال) با توضیح «از نقش …» نشان داده می‌شود.
 * - فیلتر «فقط مجوزهای مستقیم» و جست‌وجو. تغییرات تا زدن «ذخیره» فقط در صفحه‌اند (PUT یک‌جا: مجموعه‌ی کامل).
 *
 * مدیر سایتی (users.manage فقط برای بعضی سایت‌ها): فقط ستون سایت‌های خودش؛ ستون «همه» ندارد؛ ردیف‌های خارج از اختیارش
 * (سایت دیگر یا سراسری از superuser) فقط نمایش داده می‌شوند و سرور دست‌نخورده نگهشان می‌دارد.
 * ورودی: employee، sites (سایت‌های در اختیار بیننده)، allSites. خروجی: Box محتوای تب.
 */
import { Fragment, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  FormControlLabel,
  IconButton,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import ChevronLeftOutlinedIcon from "@mui/icons-material/ChevronLeftOutlined";
import SearchField from "./SearchField";
import {
  fetchEmployeePermissions,
  replaceEmployeePermissions,
} from "../api/employees";
import { fetchPermissions } from "../api/users";
import { roleDisplayName } from "../utils/roleLabels";

const ALL = "all"; // کلید ستون «همه‌ی سایت‌ها»

// آیا مجوز مستقیم (null = همه، آرایه = سایت‌ها، undefined = ندارد) شامل این ستون است؟
function covers(grant, column) {
  if (grant === undefined) return false;
  if (column === ALL) return grant === null;
  return grant === null || grant.includes(column);
}

// وضعیت جدید یک مجوز بعد از تیک/برداشتن یک ستون. siteIds = همه‌ی سایت‌های ستون‌دار (برای شکستن «همه»)
function applyColumn(grant, column, on, siteIds) {
  if (column === ALL) return on ? null : undefined;
  if (on) {
    if (grant === null) return null;
    const list = [...(grant || [])];
    if (!list.includes(column)) list.push(column);
    return list;
  }
  const base = grant === null ? siteIds : grant || [];
  const list = base.filter((id) => id !== column);
  return list.length ? list : undefined;
}

export default function DirectPermissionsTab({ employee, sites, allSites }) {
  const [permissions, setPermissions] = useState(null); // همه‌ی مجوزهای سیستم
  const [inherited, setInherited] = useState([]); // از نقش‌ها: {code, role_name, site_id}
  const [allowedSiteIds, setAllowedSiteIds] = useState(null); // سایت‌های users.manage بیننده؛ null = نامحدود
  const [grants, setGrants] = useState({}); // وضعیت ویرایش: {permission_id: null | [site_id]}
  const [saved, setSaved] = useState({}); // آخرین وضعیت ذخیره‌شده (برای تشخیص تغییر)
  const [expanded, setExpanded] = useState({});
  const [onlyDirect, setOnlyDirect] = useState(false);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!employee) return;
    let ignore = false;
    setError("");
    setSuccess("");
    Promise.all([fetchPermissions(), fetchEmployeePermissions(employee.id)])
      .then(([perms, mine]) => {
        if (ignore) return;
        setPermissions(perms);
        setInherited(mine.inherited || []);
        setAllowedSiteIds(mine.allowed_site_ids ?? null);
        const state = {};
        for (const d of mine.direct || [])
          state[d.permission_id] = d.site_ids === null ? null : [...d.site_ids];
        setGrants(state);
        setSaved(state);
      })
      .catch(
        (err) =>
          !ignore &&
          setError(err.response?.data?.detail || "دریافت مجوزها ناموفق بود."),
      );
    return () => {
      ignore = true;
    };
  }, [employee]);

  // گروه‌بندی با پیشوند کد (مثل صفحه‌ی نقش‌ها) + فیلتر جست‌وجو و «فقط مستقیم»
  const grouped = useMemo(() => {
    if (!permissions) return [];
    const q = query.trim().toLowerCase();
    const groups = {};
    for (const p of permissions) {
      if (onlyDirect && !(p.id in grants)) continue;
      if (
        q &&
        !p.code.toLowerCase().includes(q) &&
        !(p.description || "").toLowerCase().includes(q)
      )
        continue;
      const prefix = p.code.split(".")[0];
      (groups[prefix] ||= []).push(p);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [permissions, grants, onlyDirect, query]);

  // مجوزهای ارث‌رسیده از نقش‌ها: {code: [{role_name, site_id}]}
  const inheritedByCode = useMemo(() => {
    const map = {};
    for (const i of inherited) (map[i.code] ||= []).push(i);
    return map;
  }, [inherited]);

  const unrestricted = allowedSiteIds === null;
  // ردیفی که بیننده اجازه‌ی تغییرش را ندارد (سراسری یا سایت خارج از اختیار): فقط نمایش
  const isLocked = (scope) =>
    !unrestricted &&
    (scope === null || scope.some((id) => !allowedSiteIds.includes(id)));

  const dirty = useMemo(
    () =>
      JSON.stringify(sortGrants(grants)) !== JSON.stringify(sortGrants(saved)),
    [grants, saved],
  );
  const siteName = (id) =>
    (allSites || sites).find((s) => s.id === id)?.name || "—";

  const siteIds = sites.map((s) => s.id);
  const columns = [...(unrestricted ? [ALL] : []), ...siteIds];

  // خانه‌ی (مجوز، ستون) قابل تغییر است؟ ردیف قفل (خارج از اختیار بیننده) نه
  const editable = (p) => !(p.id in grants) || !isLocked(grants[p.id]);

  function toggleCell(p, column) {
    setGrants((prev) => {
      const next = { ...prev };
      const value = applyColumn(prev[p.id], column, !covers(prev[p.id], column), siteIds);
      if (value === undefined) delete next[p.id];
      else next[p.id] = value;
      return next;
    });
  }

  // تیک ستون در ردیف گروه: همه‌ی مجوزهای قابل‌تغییر گروه برای این ستون روشن/خاموش
  function toggleGroupColumn(items, column) {
    setGrants((prev) => {
      const targets = items.filter((p) => !(p.id in prev) || !isLocked(prev[p.id]));
      const allOn = targets.length > 0 && targets.every((p) => covers(prev[p.id], column));
      const next = { ...prev };
      for (const p of targets) {
        const value = applyColumn(prev[p.id], column, !allOn, siteIds);
        if (value === undefined) delete next[p.id];
        else next[p.id] = value;
      }
      return next;
    });
  }

  // نقش‌هایی که این مجوز را برای این ستون می‌دهند (نقش سراسری همه‌ی ستون‌ها را پوشش می‌دهد)
  function rolesFor(code, column) {
    return (inheritedByCode[code] || []).filter(
      (r) => r.site_id == null || (column !== ALL && r.site_id === column),
    );
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = Object.entries(grants).map(([id, siteIds]) => ({
        permission_id: Number(id),
        site_ids: siteIds,
      }));
      const result = await replaceEmployeePermissions(employee.id, payload);
      const state = {};
      for (const d of result.direct || [])
        state[d.permission_id] = d.site_ids === null ? null : [...d.site_ids];
      setGrants(state);
      setSaved(state);
      setInherited(result.inherited || []);
      setSuccess("مجوزهای مستقیم ذخیره شد.");
    } catch (err) {
      setError(err.response?.data?.detail || "ذخیره‌ی مجوزها ناموفق بود.");
    } finally {
      setSaving(false);
    }
  }

  if (permissions === null && !error) {
    return (
      <Box sx={{ py: 3, textAlign: "center" }}>
        <CircularProgress size={22} />
      </Box>
    );
  }

  const directCount = Object.keys(grants).length;
  const columnLabel = (column) => (column === ALL ? "همه‌ی سایت‌ها" : siteName(column));
  const stickyCell = {
    position: "sticky",
    right: 0,
    bgcolor: "background.paper",
    zIndex: 1,
    minWidth: 220,
    maxWidth: 320,
  };

  return (
    <Stack spacing={1.5}>
      <Alert severity="info" sx={{ py: 0.5 }}>
        مجوز مستقیم یک استثنا کنار نقش‌هاست و فقط «اضافه» می‌کند. هر ستون یک سایت است؛ تیک «همه‌ی سایت‌ها» شامل
        سایت‌های آینده هم می‌شود. خانه‌های خاکستری از نقش می‌رسند و از این‌جا برداشته نمی‌شوند. تیک ردیف گروه همه‌ی
        مجوزهای آن گروه را برای همان ستون می‌دهد یا برمی‌دارد.
      </Alert>
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        flexWrap="wrap"
        useFlexGap
      >
        {/* فیلتر سمت کلاینت (فهرست کوچک است) */}
        <SearchField
          value={query}
          onChange={setQuery}
          placeholder="جست‌وجوی مجوز…"
          fullWidth={false}
          sx={{ flex: 1, minWidth: 160 }}
        />
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={onlyDirect}
              onChange={(e) => setOnlyDirect(e.target.checked)}
            />
          }
          label={
            <Typography variant="body2">
              فقط مستقیم‌ها ({directCount})
            </Typography>
          }
        />
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      {success && <Alert severity="success">{success}</Alert>}

      {grouped.length === 0 ? (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ py: 2, textAlign: "center" }}
        >
          {onlyDirect ? "هنوز مجوز مستقیمی داده نشده." : "مجوزی پیدا نشد."}
        </Typography>
      ) : (
        <TableContainer
          sx={{ maxHeight: 440, border: 1, borderColor: "divider", borderRadius: 1.5 }}
        >
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ ...stickyCell, zIndex: 3, fontWeight: 700 }}>
                  مجوز
                </TableCell>
                {columns.map((column) => (
                  <TableCell
                    key={column}
                    align="center"
                    sx={{
                      fontWeight: 700,
                      whiteSpace: "nowrap",
                      bgcolor: column === ALL ? "action.hover" : undefined,
                    }}
                  >
                    {columnLabel(column)}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {grouped.map(([group, items]) => {
                const isExpanded = expanded[group] !== false;
                const selectedCount = items.filter((p) => p.id in grants).length;
                const targets = items.filter(editable);
                return (
                  <Fragment key={group}>
                    {/* ردیف گروه (درخت): باز/بسته + تیک «همه‌ی مجوزهای گروه» برای هر ستون */}
                    <TableRow sx={{ bgcolor: "action.selected" }}>
                      <TableCell
                        sx={{ ...stickyCell, bgcolor: "action.selected", cursor: "pointer" }}
                        onClick={() =>
                          setExpanded((prev) => ({ ...prev, [group]: !isExpanded }))
                        }
                      >
                        <Stack direction="row" alignItems="center" spacing={0.5}>
                          <IconButton size="small" sx={{ p: 0.25 }}>
                            {isExpanded ? (
                              <ExpandMoreOutlinedIcon fontSize="small" />
                            ) : (
                              <ChevronLeftOutlinedIcon fontSize="small" />
                            )}
                          </IconButton>
                          <Typography variant="body2" fontWeight={700} sx={{ flex: 1 }}>
                            {group}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {selectedCount}/{items.length}
                          </Typography>
                        </Stack>
                      </TableCell>
                      {columns.map((column) => {
                        const on = targets.filter((p) => covers(grants[p.id], column)).length;
                        return (
                          <TableCell key={column} align="center" sx={{ py: 0 }}>
                            <Tooltip
                              title={`همه‌ی مجوزهای گروه ${group} — ${columnLabel(column)}`}
                              arrow
                            >
                              <span>
                                <Checkbox
                                  size="small"
                                  disabled={targets.length === 0}
                                  checked={targets.length > 0 && on === targets.length}
                                  indeterminate={on > 0 && on < targets.length}
                                  onChange={() => toggleGroupColumn(items, column)}
                                />
                              </span>
                            </Tooltip>
                          </TableCell>
                        );
                      })}
                    </TableRow>
                    {isExpanded &&
                      items.map((p) => {
                        const grant = grants[p.id];
                        const locked = p.id in grants && isLocked(grant);
                        return (
                          <TableRow key={p.id} hover>
                            <TableCell sx={{ ...stickyCell, pl: 4 }}>
                              <Typography variant="body2">{p.code}</Typography>
                              {p.description && (
                                <Typography
                                  variant="caption"
                                  color="text.secondary"
                                  display="block"
                                >
                                  {p.description}
                                </Typography>
                              )}
                              {locked && (
                                <Typography variant="caption" color="warning.main" display="block">
                                  توسط مدیر ارشد یا برای سایت دیگری داده شده — از این‌جا قابل تغییر نیست
                                </Typography>
                              )}
                            </TableCell>
                            {columns.map((column) => {
                              const direct = covers(grant, column);
                              const roles = direct ? [] : rolesFor(p.code, column);
                              if (roles.length > 0) {
                                return (
                                  <TableCell key={column} align="center" sx={{ py: 0 }}>
                                    <Tooltip
                                      title={`از نقش ${roles.map((r) => roleDisplayName(r.role_name)).join("، ")}`}
                                      arrow
                                    >
                                      <span>
                                        <Checkbox size="small" checked disabled />
                                      </span>
                                    </Tooltip>
                                  </TableCell>
                                );
                              }
                              return (
                                <TableCell
                                  key={column}
                                  align="center"
                                  sx={{ py: 0, bgcolor: column === ALL ? "action.hover" : undefined }}
                                >
                                  <Checkbox
                                    size="small"
                                    checked={direct}
                                    disabled={locked}
                                    onChange={() => toggleCell(p, column)}
                                    inputProps={{ "aria-label": `${p.code} — ${columnLabel(column)}` }}
                                  />
                                </TableCell>
                              );
                            })}
                          </TableRow>
                        );
                      })}
                  </Fragment>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Stack direction="row" spacing={1} alignItems="center">
        <Button
          variant="contained"
          size="small"
          onClick={handleSave}
          disabled={!dirty || saving}
        >
          {saving ? "در حال ذخیره..." : "ذخیره‌ی مجوزهای مستقیم"}
        </Button>
        {dirty && (
          <Button
            size="small"
            onClick={() => setGrants(saved)}
            disabled={saving}
          >
            انصراف از تغییرات
          </Button>
        )}
      </Stack>
    </Stack>
  );
}

// برای مقایسه‌ی دو وضعیت: کلیدها و سایت‌ها مرتب می‌شوند
function sortGrants(obj) {
  return Object.keys(obj)
    .sort((a, b) => Number(a) - Number(b))
    .map((k) => [
      Number(k),
      obj[k] === null ? null : [...obj[k]].sort((a, b) => a - b),
    ]);
}
