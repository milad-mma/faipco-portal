/**
 * بخش «تقسیم درخت واحدها بین سایت‌ها» در تب نگاشت پرسنل تنظیمات سایت.
 *
 * وقتی چند سایت پرتال به یک دیتابیس کاراوب مشترک وصل‌اند، هر سایت یک یا چند
 * «واحد ریشه» دارد و هر واحد متعلق به سایتی است که نزدیک‌ترین ریشه‌ی بالادستش
 * را دارد. این کامپوننت ستون «واحد بالادست» را می‌گیرد، درخت واحدهای منبع را با
 * پیش‌نمایش سرور نشان می‌دهد و اجازه می‌دهد ریشه‌های این سایت علامت زده شوند.
 * تغییرات فقط در فرم است و با دکمه‌ی ذخیره‌ی نگاشت اعمال می‌شود.
 *
 * ورودی: siteId، mappingForm و setMappingForm (فرم نگاشت پرسنل صفحه‌ی والد)، disabled.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AccountTreeOutlinedIcon from "@mui/icons-material/AccountTreeOutlined";
import { previewSiteOrgFilter } from "../api/sites";

// رنگ تراشه‌ی سایت‌ها به ترتیب نمایش (سایت جاری همیشه primary)
const SITE_COLORS = ["primary", "success", "secondary", "info", "warning"];

// کد واحد را برای مرتب‌سازی عددی آماده می‌کند (کدهای غیرعددی بعد از عددی‌ها)
const codeSortKey = (code) => (/^\d+$/.test(code) ? [0, Number(code)] : [1, code]);
const compareCodes = (a, b) => {
  const [ka, va] = codeSortKey(a);
  const [kb, vb] = codeSortKey(b);
  return ka - kb || (va < vb ? -1 : va > vb ? 1 : 0);
};

/**
 * واحدهای پیش‌نمایش را به ترتیب درختی (والد، سپس فرزندان) با عمق هر واحد برمی‌گرداند.
 * واحدی که والدش در فهرست نیست در سطح اول نمایش داده می‌شود.
 */
function flattenTree(units) {
  const codes = new Set(units.map((u) => u.code));
  const children = new Map();
  const tops = [];
  for (const unit of units) {
    if (unit.parent && codes.has(unit.parent)) {
      if (!children.has(unit.parent)) children.set(unit.parent, []);
      children.get(unit.parent).push(unit);
    } else {
      tops.push(unit);
    }
  }
  const byCode = (a, b) => compareCodes(a.code, b.code);
  const out = [];
  const visited = new Set();
  // پیمایش عمق‌اول با محافظت در برابر حلقه‌ی داده‌ی منبع
  const walk = (unit, depth) => {
    if (visited.has(unit.code)) return;
    visited.add(unit.code);
    out.push({ ...unit, depth });
    (children.get(unit.code) || []).sort(byCode).forEach((child) => walk(child, depth + 1));
  };
  tops.sort(byCode).forEach((unit) => walk(unit, 0));
  // واحدهای داخل حلقه که از هیچ سطح اولی دیده نشدند
  units.filter((u) => !visited.has(u.code)).forEach((u) => out.push({ ...u, depth: 0 }));
  return out;
}

export default function OrgRootFilterSection({ siteId, mappingForm, setMappingForm, disabled }) {
  const [preview, setPreview] = useState(null); // آخرین پاسخ پیش‌نمایش سرور
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [loadedOnce, setLoadedOnce] = useState(false); // بعد از اولین بارگذاری، تغییر ریشه‌ها خودکار پیش‌نمایش را تازه می‌کند
  const requestSeq = useRef(0); // فقط جواب آخرین درخواست نمایش داده شود

  const roots = mappingForm.root_department_codes || [];

  // پیش‌نمایش را با وضعیت فعلی فرم از سرور می‌گیرد
  async function loadPreview(form = mappingForm) {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError("");
    try {
      const data = await previewSiteOrgFilter(siteId, form);
      if (seq === requestSeq.current) {
        setPreview(data);
        setLoadedOnce(true);
      }
    } catch (err) {
      if (seq === requestSeq.current) setError(err.response?.data?.detail || "دریافت درخت واحدها با خطا مواجه شد.");
    } finally {
      if (seq === requestSeq.current) setLoading(false);
    }
  }

  // بعد از تغییر ریشه‌ها (با تأخیر کوتاه) پیش‌نمایش دوباره گرفته می‌شود تا سایت هر واحد به‌روز شود
  const rootsKey = roots.join(",");
  useEffect(() => {
    if (!loadedOnce) return undefined;
    const timer = setTimeout(() => loadPreview(), 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rootsKey]);

  // نام و رنگ هر سایت در پیش‌نمایش (برای تراشه‌ها)
  const siteMeta = useMemo(() => {
    const meta = new Map();
    (preview?.sites || []).forEach((s, i) => {
      meta.set(s.site_id, { name: s.site_name, color: s.is_current ? "primary" : SITE_COLORS[(i % 4) + 1], current: s.is_current });
    });
    return meta;
  }, [preview]);

  // ریشه‌هایی که متعلق به سایت‌های دیگرند و نباید از اینجا انتخاب شوند
  const foreignRoots = useMemo(() => {
    const map = new Map();
    (preview?.sites || []).filter((s) => !s.is_current).forEach((s) => s.roots.forEach((code) => map.set(code, s.site_name)));
    return map;
  }, [preview]);

  const treeRows = useMemo(() => flattenTree(preview?.units || []), [preview]);
  const unitName = (code) => preview?.units?.find((u) => u.code === code)?.name || code;

  // علامت زدن/برداشتن یک واحد به‌عنوان ریشه‌ی این سایت
  function toggleRoot(code) {
    const next = roots.includes(code) ? roots.filter((c) => c !== code) : [...roots, code];
    setMappingForm({ ...mappingForm, root_department_codes: next });
  }

  return (
    <Box>
      <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 0.5 }}>
        تقسیم درخت واحدها بین سایت‌ها (اختیاری)
      </Typography>
      <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 1.5, lineHeight: 1.9 }}>
        برای وقتی که چند سایت به یک دیتابیس کاراوب مشترک وصل‌اند. هر سایت یک یا چند «واحد ریشه» دارد و هر واحد
        متعلق به سایتی است که <b>نزدیک‌ترین ریشه‌ی بالادستش</b> را دارد. پرسنل واحدهایی که زیر هیچ ریشه‌ای نیستند
        وارد نمی‌شوند و در گزارش همگام‌سازی هشدار می‌گیرند. اگر هیچ ریشه‌ای انتخاب نشود، همه‌ی پرسنل منبع (مثل قبل)
        همگام می‌شوند. سایت‌هایی «هم‌منبع» شمرده می‌شوند که نوع دیتابیس، میزبان، پورت و نام دیتابیس اتصالشان دقیقاً
        یکسان باشد؛ آدرس سرور را در همه‌ی سایت‌ها به یک شکل وارد کنید (مثلاً همه IP یا همه نام سرور).
      </Typography>

      {/* ستون بالادست + دکمه‌ی بارگذاری درخت */}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "flex-start" }}>
        <TextField
          label="ستون واحد بالادست در جدول Lookup واحدها"
          value={mappingForm.department_lookup_parent_column || ""}
          onChange={(e) => setMappingForm({ ...mappingForm, department_lookup_parent_column: e.target.value })}
          helperText="مثال: TFather"
          disabled={disabled}
          sx={{ flex: 1 }}
        />
        <Button
          variant="outlined"
          startIcon={loading ? <CircularProgress size={16} /> : <AccountTreeOutlinedIcon />}
          onClick={() => loadPreview()}
          disabled={disabled || loading}
          sx={{ mt: { sm: 1 }, whiteSpace: "nowrap" }}
        >
          نمایش درخت واحدها
        </Button>
      </Stack>

      {/* ریشه‌های انتخاب‌شده (حتی پیش از بارگذاری درخت) */}
      {roots.length > 0 && (
        <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary" sx={{ alignSelf: "center" }}>
            ریشه‌های این سایت:
          </Typography>
          {roots.map((code) => (
            <Chip
              key={code}
              size="small"
              color="primary"
              label={`${unitName(code)} (${code})`}
              onDelete={disabled ? undefined : () => toggleRoot(code)}
            />
          ))}
        </Stack>
      )}

      {error && (
        <Alert severity="error" sx={{ mt: 1.5 }}>
          {error}
        </Alert>
      )}

      {preview && (
        <Box sx={{ mt: 1.5 }}>
          {preview.error && (
            <Alert severity="error" sx={{ mb: 1.5 }}>
              {preview.error}
            </Alert>
          )}

          {/* خلاصه‌ی هر سایت هم‌منبع */}
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
            {preview.sites.map((s) => (
              <Paper
                key={s.site_id}
                variant="outlined"
                sx={{ px: 1.5, py: 1, borderRadius: 2, borderColor: s.is_current ? "primary.main" : "divider" }}
              >
                <Typography variant="body2" fontWeight={700}>
                  {s.site_name}
                  {s.is_current ? " (این سایت)" : ""}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {s.roots.length ? `${s.unit_count} واحد · ${s.active_employee_count} پرسنل فعال` : "بدون ریشه"}
                </Typography>
              </Paper>
            ))}
          </Stack>

          {preview.unassigned_active_employees > 0 && roots.length > 0 && (
            <Alert severity="warning" sx={{ mb: 1.5 }}>
              {preview.unassigned_active_employees} پرسنل فعال در واحدهایی هستند که زیر هیچ ریشه‌ای نیستند و با این
              تنظیمات وارد هیچ سایتی نمی‌شوند (واحدهای نارنجی پایین).
            </Alert>
          )}

          {/* درخت واحدها با علامت ریشه و سایت هر واحد */}
          <Paper variant="outlined" sx={{ borderRadius: 2, maxHeight: 420, overflow: "auto" }}>
            {treeRows.map((unit) => {
              const foreignOwner = foreignRoots.get(unit.code);
              const meta = unit.site_id != null ? siteMeta.get(unit.site_id) : null;
              return (
                <Stack
                  key={unit.code}
                  direction="row"
                  alignItems="center"
                  spacing={1}
                  // تورفتگی عمق درخت با pl؛ افزونه‌ی RTL آن را به سمت شروع (راست) برمی‌گرداند
                  sx={{ py: 0.25, pl: 1 + unit.depth * 2.5, pr: 1, borderBottom: "1px solid", borderColor: "divider" }}
                >
                  <Checkbox
                    size="small"
                    checked={roots.includes(unit.code)}
                    onChange={() => toggleRoot(unit.code)}
                    disabled={disabled || Boolean(foreignOwner)}
                    inputProps={{ "aria-label": `ریشه‌ی این سایت: ${unit.name}` }}
                  />
                  <Typography variant="body2" sx={{ flex: 1, minWidth: 0 }} noWrap>
                    {unit.name}{" "}
                    <Typography component="span" variant="caption" color="text.secondary">
                      ({unit.code}) · {unit.active_employees} نفر
                    </Typography>
                  </Typography>
                  {foreignOwner && <Chip size="small" variant="outlined" label={`ریشه‌ی ${foreignOwner}`} />}
                  {meta ? (
                    <Chip size="small" color={meta.color} variant={meta.current ? "filled" : "outlined"} label={meta.name} />
                  ) : (
                    roots.length > 0 && <Chip size="small" color="warning" label="بدون سایت" />
                  )}
                </Stack>
              );
            })}
            {treeRows.length === 0 && (
              <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: "center" }}>
                واحدی در جدول منبع پیدا نشد.
              </Typography>
            )}
          </Paper>
          <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1 }}>
            تغییرات فقط با «ذخیره Mapping» اعمال می‌شوند و از همگام‌سازی بعدی اثر می‌گذارند.
          </Typography>
        </Box>
      )}
    </Box>
  );
}
