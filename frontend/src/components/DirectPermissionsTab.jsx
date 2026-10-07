/**
 * تب «مجوزهای مستقیم» دیالوگ دسترسی پرسنل (Migration 106؛ docs/rbac.md).
 *
 * همان درخت مجوزهای صفحه‌ی نقش‌ها (گروه‌بندی با پیشوند کد)، ولی برای یک نفر و با انتخاب سایت کنار هر مجوز:
 * - تیک هر مجوز + چیپ سایت: پیش‌فرض «همه‌ی سایت‌ها»؛ با کلیک، یک یا چند سایت انتخاب می‌شود.
 * - تیک گروه: همه‌ی مجوزهای گروه با سایت انتخابی گروه (پیش‌فرض همه‌ی سایت‌ها).
 * - مجوزهایی که از نقش می‌رسند خاکستری و تیک‌خورده با برچسب «از نقش …» نشان داده می‌شوند؛ از این‌جا قابل برداشتن نیستند
 *   (باید از نقش برداشته شوند) ولی می‌شود مستقیم هم داد (مثلاً برای سایت دیگری).
 * - فیلتر «فقط مجوزهای مستقیم» و جست‌وجو برای فهرست شلوغ.
 * تغییرات تا زدن «ذخیره» فقط در صفحه‌اند (PUT یک‌جا: مجموعه‌ی کامل).
 *
 * مدیر سایتی (users.manage فقط برای بعضی سایت‌ها): «همه‌ی سایت‌ها» ندارد؛ پیش‌فرض مجوز تازه = سایت‌های خودش؛ ردیف‌های
 * خارج از اختیارش (سایت دیگر یا سراسری از superuser) فقط نمایش داده می‌شوند و سرور دست‌نخورده نگهشان می‌دارد.
 * ورودی: employee، sites (سایت‌های در اختیار بیننده). خروجی: Box محتوای تب.
 */
import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Collapse,
  FormControlLabel,
  IconButton,
  Menu,
  MenuItem,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import ChevronLeftOutlinedIcon from "@mui/icons-material/ChevronLeftOutlined";
import PlaceOutlinedIcon from "@mui/icons-material/PlaceOutlined";
import { fetchEmployeePermissions, replaceEmployeePermissions } from "../api/employees";
import { fetchPermissions } from "../api/users";
import { roleDisplayName } from "../utils/roleLabels";

/**
 * چیپ انتخاب سایت یک مجوز (یا یک گروه). value: null = همه‌ی سایت‌ها، وگرنه آرایه‌ی id سایت‌ها.
 * منو: «همه‌ی سایت‌ها» + یک تیک برای هر سایت. انتخاب همه‌ی سایت‌ها به‌صورت تکی = «همه».
 */
function SiteScopeChip({ value, sites, nameOf, onChange, disabled, allowAll, size = "small" }) {
  const [anchor, setAnchor] = useState(null);
  const isAll = value === null;
  const label = isAll ? "همه‌ی سایت‌ها" : value.map((id) => nameOf(id)).join("، ");

  function toggleSite(id) {
    const current = isAll ? sites.map((s) => s.id) : value;
    const next = current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
    if (next.length === 0) return; // حداقل یک سایت؛ برای برداشتن مجوز، تیک خودش برداشته می‌شود
    // فقط مدیر نامحدود می‌تواند «همه‌ی سایت‌ها» (شامل سایت‌های آینده) بدهد؛ مدیر سایتی همیشه سایت‌های مشخص
    onChange(allowAll && sites.length > 0 && sites.every((s) => next.includes(s.id)) ? null : next);
  }

  return (
    <>
      <Chip
        size={size}
        icon={<PlaceOutlinedIcon />}
        label={label}
        variant={isAll ? "outlined" : "filled"}
        color={isAll ? "default" : "primary"}
        onClick={disabled ? undefined : (e) => setAnchor(e.currentTarget)}
        disabled={disabled}
        sx={{ maxWidth: 220, "& .MuiChip-label": { overflow: "hidden", textOverflow: "ellipsis" } }}
      />
      <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)}>
        {allowAll && (
          <MenuItem
            dense
            onClick={() => {
              onChange(null);
              setAnchor(null);
            }}
          >
            <Checkbox size="small" checked={isAll} />
            همه‌ی سایت‌ها (و سایت‌های آینده)
          </MenuItem>
        )}
        {sites.map((s) => (
          <MenuItem dense key={s.id} onClick={() => toggleSite(s.id)}>
            <Checkbox size="small" checked={isAll || value.includes(s.id)} />
            {s.name}
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}

export default function DirectPermissionsTab({ employee, sites, allSites }) {
  const [permissions, setPermissions] = useState(null); // همه‌ی مجوزهای سیستم
  const [inherited, setInherited] = useState([]); // از نقش‌ها: {code, role_name, site_id}
  const [allowedSiteIds, setAllowedSiteIds] = useState(null); // سایت‌های users.manage بیننده؛ null = نامحدود
  const [grants, setGrants] = useState({}); // وضعیت ویرایش: {permission_id: null | [site_id]}
  const [saved, setSaved] = useState({}); // آخرین وضعیت ذخیره‌شده (برای تشخیص تغییر)
  const [groupScope, setGroupScope] = useState({}); // سایت انتخابی هر گروه برای «انتخاب همه»
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
        for (const d of mine.direct || []) state[d.permission_id] = d.site_ids === null ? null : [...d.site_ids];
        setGrants(state);
        setSaved(state);
      })
      .catch((err) => !ignore && setError(err.response?.data?.detail || "دریافت مجوزها ناموفق بود."));
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
      if (q && !p.code.toLowerCase().includes(q) && !(p.description || "").toLowerCase().includes(q)) continue;
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
  // پیش‌فرض یک مجوز تازه: نامحدود ← «همه‌ی سایت‌ها»؛ مدیر سایتی ← سایت‌های خودش
  const defaultScope = () => (unrestricted ? null : sites.map((s) => s.id));
  // ردیفی که بیننده اجازه‌ی تغییرش را ندارد (سراسری یا سایت خارج از اختیار): فقط نمایش
  const isLocked = (scope) =>
    !unrestricted && (scope === null || scope.some((id) => !allowedSiteIds.includes(id)));

  const dirty = useMemo(() => JSON.stringify(sortGrants(grants)) !== JSON.stringify(sortGrants(saved)), [grants, saved]);
  const siteName = (id) => (allSites || sites).find((s) => s.id === id)?.name || "—";

  function setGrant(id, value) {
    setGrants((prev) => {
      const next = { ...prev };
      if (value === undefined) delete next[id];
      else next[id] = value;
      return next;
    });
  }

  function toggleGroup(items, group) {
    const scope = groupScope[group] === undefined ? defaultScope() : groupScope[group];
    setGrants((prev) => {
      const editable = items.filter((p) => !(p.id in prev) || !isLocked(prev[p.id]));
      const allOn = editable.every((p) => p.id in prev);
      const next = { ...prev };
      for (const p of editable) {
        if (allOn) delete next[p.id];
        else if (!(p.id in next)) next[p.id] = scope === null ? null : [...scope];
      }
      return next;
    });
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
      for (const d of result.direct || []) state[d.permission_id] = d.site_ids === null ? null : [...d.site_ids];
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

  return (
    <Stack spacing={1.5}>
      <Alert severity="info" sx={{ py: 0.5 }}>
        مجوز مستقیم یک استثنا کنار نقش‌هاست و فقط «اضافه» می‌کند. مجوزهای خاکستری از نقش می‌رسند و از این‌جا برداشته
        نمی‌شوند. برای هر مجوز می‌توانید سایت را محدود کنید (پیش‌فرض: همه‌ی سایت‌ها).
      </Alert>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
        <TextField
          size="small"
          label="جست‌وجوی مجوز"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          sx={{ flex: 1, minWidth: 160 }}
        />
        <FormControlLabel
          control={<Switch size="small" checked={onlyDirect} onChange={(e) => setOnlyDirect(e.target.checked)} />}
          label={<Typography variant="body2">فقط مستقیم‌ها ({directCount})</Typography>}
        />
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      {success && <Alert severity="success">{success}</Alert>}

      <Stack spacing={0.5} sx={{ maxHeight: 400, overflowY: "auto", pr: 0.5 }}>
        {grouped.length === 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ py: 2, textAlign: "center" }}>
            {onlyDirect ? "هنوز مجوز مستقیمی داده نشده." : "مجوزی پیدا نشد."}
          </Typography>
        )}
        {grouped.map(([group, items]) => {
          const selectedCount = items.filter((p) => p.id in grants).length;
          const allSelected = selectedCount === items.length;
          const isExpanded = expanded[group] !== false;
          const scope = groupScope[group] === undefined ? defaultScope() : groupScope[group];
          return (
            <Box key={group} sx={{ border: "1px solid", borderColor: "divider", borderRadius: 1.5 }}>
              <Stack
                direction="row"
                alignItems="center"
                spacing={0.5}
                sx={{ px: 1, py: 0.5, cursor: "pointer" }}
                onClick={() => setExpanded((prev) => ({ ...prev, [group]: !isExpanded }))}
              >
                <IconButton size="small" sx={{ p: 0.25 }}>
                  {isExpanded ? <ExpandMoreOutlinedIcon fontSize="small" /> : <ChevronLeftOutlinedIcon fontSize="small" />}
                </IconButton>
                <Tooltip title="انتخاب همه‌ی مجوزهای این گروه (با سایتِ انتخاب‌شده در چیپ گروه؛ مجوزهای تیک‌خورده‌ی قبلی عوض نمی‌شوند)" arrow>
                  <Checkbox
                    size="small"
                    checked={allSelected}
                    indeterminate={selectedCount > 0 && !allSelected}
                    onClick={(e) => e.stopPropagation()}
                    onChange={() => toggleGroup(items, group)}
                  />
                </Tooltip>
                <Typography variant="body2" fontWeight={700} sx={{ flex: 1 }}>
                  {group}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {selectedCount}/{items.length}
                </Typography>
                <Tooltip title="سایت پیش‌فرض برای مجوزهایی که با تیک گروه اضافه می‌شوند" arrow>
                  <Box onClick={(e) => e.stopPropagation()}>
                    <SiteScopeChip
                      value={scope}
                      sites={sites}
                      nameOf={siteName}
                      allowAll={unrestricted}
                      onChange={(next) => setGroupScope((prev) => ({ ...prev, [group]: next }))}
                      disabled={!unrestricted && sites.length < 2}
                    />
                  </Box>
                </Tooltip>
              </Stack>
              <Collapse in={isExpanded}>
                <Stack sx={{ pb: 0.5 }}>
                  {items.map((p) => {
                    const direct = p.id in grants;
                    const locked = direct && isLocked(grants[p.id]);
                    const fromRoles = inheritedByCode[p.code] || [];
                    return (
                      <Stack
                        key={p.id}
                        direction="row"
                        alignItems="flex-start"
                        spacing={0.5}
                        sx={{ pl: 1, pr: 1, py: 0.25, bgcolor: !direct && fromRoles.length ? "action.hover" : undefined }}
                      >
                        <Tooltip title={locked ? "این مجوز توسط مدیر ارشد یا برای سایت دیگری داده شده و از این‌جا قابل تغییر نیست" : ""} arrow>
                          <span>
                            <Checkbox
                              size="small"
                              checked={direct}
                              disabled={locked}
                              onChange={() => setGrant(p.id, direct ? undefined : defaultScope())}
                              sx={{ mt: -0.25 }}
                            />
                          </span>
                        </Tooltip>
                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Typography variant="body2" color={!direct && fromRoles.length ? "text.secondary" : "text.primary"}>
                            {p.code}
                          </Typography>
                          {p.description && (
                            <Typography variant="caption" color="text.secondary" display="block">
                              {p.description}
                            </Typography>
                          )}
                          {fromRoles.length > 0 && (
                            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mt: 0.25 }}>
                              {fromRoles.map((r, i) => (
                                <Chip
                                  key={i}
                                  size="small"
                                  variant="outlined"
                                  label={`از نقش ${roleDisplayName(r.role_name)}${r.site_id ? ` — ${siteName(r.site_id)}` : ""}`}
                                  sx={{ height: 18, fontSize: 10 }}
                                />
                              ))}
                            </Stack>
                          )}
                        </Box>
                        {direct && (
                          <SiteScopeChip
                            value={grants[p.id]}
                            sites={sites}
                            nameOf={siteName}
                            allowAll={unrestricted}
                            onChange={(next) => setGrant(p.id, next)}
                            disabled={locked || (!unrestricted && sites.length < 2)}
                          />
                        )}
                      </Stack>
                    );
                  })}
                </Stack>
              </Collapse>
            </Box>
          );
        })}
      </Stack>

      <Stack direction="row" spacing={1} alignItems="center">
        <Button variant="contained" size="small" onClick={handleSave} disabled={!dirty || saving}>
          {saving ? "در حال ذخیره..." : "ذخیره‌ی مجوزهای مستقیم"}
        </Button>
        {dirty && (
          <Button size="small" onClick={() => setGrants(saved)} disabled={saving}>
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
    .map((k) => [Number(k), obj[k] === null ? null : [...obj[k]].sort((a, b) => a - b)]);
}
