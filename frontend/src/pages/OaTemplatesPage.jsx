// «قالب‌های نامه» — اتوماسیون اداری فاز ۲: سربرگ، پابرگ، حاشیه و قلم (برای همه‌ی سایت‌ها یکسان)، جدا برای A4 و A5، با پیش‌نمایش زنده.
// هر ذخیره یک نسخه‌ی تازه می‌سازد؛ پیش‌نویس‌هایی که با نسخه‌ی قبلی ساخته شده‌اند تا ذخیره‌ی بعدی همان را نگه می‌دارند.
// قالب برای همه‌ی سایت‌ها یکسان است؛ مجوز automation.templates.
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Checkbox,
  CircularProgress,
  Divider,
  FormControlLabel,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import { fetchTemplates, saveTemplate, uploadTemplateLogo } from "../api/automationLetters";
import LetterPreview from "../components/oa/LetterPreview";
import { safePreviewLayouts } from "../components/oa/sanitizeTemplatePreview";
import { toPersianDigits } from "../utils/searchText";

const SAMPLE_SUBJECT = "نمونه‌ی موضوع نامه";
const SAMPLE_BODY =
  "<p>با سلام و احترام،</p><p>این متن نمونه است تا جای سربرگ، پابرگ و حاشیه‌ها روی کاغذ دیده شود. متن واقعی نامه هنگام نوشتن پیش‌نویس وارد می‌شود.</p><p>با تشکر</p>";

const clone = (o) => JSON.parse(JSON.stringify(o));

// نمونه‌ی شروع برای سربرگ و پابرگ HTML (style درون‌خطی؛ جهت‌ها فیزیکی‌اند)
const SAMPLE_HEADER_HTML = `<table style="width: 100%; height: 100%; border-collapse: collapse; border-bottom: 0.4mm solid #333">
  <tr>
    <td style="width: 30%; vertical-align: middle"><img src="{{logo}}" style="max-height: 22mm; max-width: 45mm"></td>
    <td style="text-align: center; vertical-align: middle">
      <div style="font-size: 15pt; font-weight: bold">{{title}}</div>
      <div style="font-size: 10pt; color: #444">{{subtitle}}</div>
    </td>
    <td style="width: 30%; vertical-align: middle; font-size: 9pt; line-height: 1.9">
      <div>شماره: {{number}}</div>
      <div>تاریخ: {{date}}</div>
      <div>پیوست: {{attachment}}</div>
    </td>
  </tr>
</table>`;
const SAMPLE_FOOTER_HTML = `<div style="border-top: 0.3mm solid #999; display: flex; justify-content: space-between; align-items: center; height: 100%; font-size: 8pt; color: #333">
  <span>نشانی و تلفن شرکت</span>
  <span>صفحه {{page}} از {{pages}}</span>
</div>`;
const PLACEHOLDER_HELP =
  "جای‌نگهدارها: {{logo}} (فقط در src تصویر)، {{title}}، {{subtitle}}، {{site}}، {{number}}، {{date}}، {{attachment}}، {{page}}، {{pages}}. فقط style درون‌خطی؛ اسکریپت، لینک و تصویر بیرونی حذف می‌شوند.";

function HtmlField({ label, value, onChange, sample }) {
  return (
    <Stack spacing={1}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Typography variant="body2" fontWeight={700} sx={{ flex: 1 }}>{label}</Typography>
        {!value && <Button size="small" onClick={() => onChange(sample)}>شروع از نمونه</Button>}
        {value && <Button size="small" color="inherit" onClick={() => onChange("")}>پاک کردن (برگشت به حالت ساده)</Button>}
      </Stack>
      <TextField
        multiline
        minRows={value ? 6 : 2}
        maxRows={20}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder="خالی = سربرگ/پابرگ ساده از فیلدهای بالا"
        inputProps={{ dir: "ltr", spellCheck: false, style: { fontFamily: "monospace", fontSize: 13 } }}
      />
    </Stack>
  );
}

function NumberField({ label, value, onChange, min, max, width = 110 }) {
  return (
    <TextField
      size="small"
      type="number"
      label={label}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      inputProps={{ min, max }}
      sx={{ width }}
    />
  );
}

export default function OaTemplatesPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null); // id قالب یا "new"
  const [form, setForm] = useState(null);
  const [paper, setPaper] = useState("A4");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null); // { ok, message }
  const openedSnapshot = useRef(null);
  const isDirty = Boolean(form && openedSnapshot.current && JSON.stringify(form) !== openedSnapshot.current);

  function load(selectId) {
    return fetchTemplates()
      .then((d) => {
        setData(d);
        if (selectId) open(d, selectId, true);
      })
      .catch((err) => setError(err.response?.data?.detail || "دریافت قالب‌ها ناموفق بود."));
  }

  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function open(d, id, force = false) {
    if (!force && id === selected) return;
    if (!force && isDirty && !window.confirm("تغییرات قالب ذخیره نشده‌اند. بدون ذخیره قالب دیگری باز شود؟")) return;
    setResult(null);
    setSelected(id);
    let next;
    if (id === "new") {
      next = { id: null, name: "", default_paper_size: "A4", is_active: true, layouts: clone(d.default_layouts) };
    } else {
      const t = d.templates.find((x) => x.id === id);
      if (!t) return;
      const layouts = clone(t.layouts);
      for (const k of Object.keys(layouts)) {
        layouts[k].header.html = layouts[k].header.html || "";
        layouts[k].footer.html = layouts[k].footer.html || "";
      }
      next = { ...t, layouts };
      setPaper(t.default_paper_size);
    }
    openedSnapshot.current = JSON.stringify(next);
    setForm(next);
  }

  const layout = form?.layouts?.[paper];
  const previewLayouts = useMemo(() => safePreviewLayouts(form?.layouts), [form?.layouts]);
  const previewLayout = previewLayouts?.[paper];

  useEffect(() => {
    if (!isDirty) return undefined;
    const beforeUnload = (event) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [isDirty]);

  function setLayout(patch) {
    setForm((f) => ({ ...f, layouts: { ...f.layouts, [paper]: { ...f.layouts[paper], ...patch } } }));
  }
  function setHeader(patch) {
    setLayout({ header: { ...layout.header, ...patch } });
  }
  function setFooter(patch) {
    setLayout({ footer: { ...layout.footer, ...patch } });
  }
  function setMargin(key, v) {
    setLayout({ margins_mm: { ...layout.margins_mm, [key]: v } });
  }

  async function handleLogo(file) {
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const f = await uploadTemplateLogo(file);
      // لوگو برای هر دو اندازه‌ی کاغذ؛ اگر لازم شد می‌شود یکی را برداشت
      setForm((prev) => ({
        ...prev,
        layouts: Object.fromEntries(
          Object.entries(prev.layouts).map(([k, l]) => [k, { ...l, header: { ...l.header, logo_file_id: f.id } }]),
        ),
      }));
    } catch (err) {
      setResult({ ok: false, message: err.response?.data?.detail || "بارگذاری لوگو ناموفق بود." });
    } finally {
      setUploading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setResult(null);
    try {
      const saved = await saveTemplate(form.id, {
        name: form.name,
        default_paper_size: form.default_paper_size,
        is_active: form.is_active,
        layouts: form.layouts,
      });
      await load(saved.id);
      setResult({ ok: true, message: `ذخیره شد (نسخه‌ی ${toPersianDigits(saved.version_no)}).` });
    } catch (err) {
      setResult({ ok: false, message: err.response?.data?.detail || "ذخیره ناموفق بود." });
    } finally {
      setSaving(false);
    }
  }


  if (error) return <Alert severity="error">{error}</Alert>;
  if (!data) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        قالب‌های نامه
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        سربرگ، پابرگ و حاشیه‌ی نامه‌ها — برای همه‌ی سایت‌ها یکسان. چیدمان A4 و A5 جدا تنظیم می‌شود. هر ذخیره یک نسخه‌ی تازه است و نامه‌های قبلی
        دست نمی‌خورند.
      </Typography>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="flex-start">
        <Card variant="outlined" sx={{ width: { xs: "100%", md: 240 }, flex: "none", minWidth: 0, borderRadius: 2 }}>
          <List dense>
            {data.templates.map((t) => (
              <ListItemButton key={t.id} selected={selected === t.id} onClick={() => open(data, t.id)}>
                <ListItemText
                  primary={t.name + (t.is_active ? "" : " (غیرفعال)")}
                  primaryTypographyProps={{ noWrap: true, title: t.name }}
                  secondary={`نسخه‌ی ${toPersianDigits(t.version_no || 0)}`}
                />
              </ListItemButton>
            ))}
            {data.templates.length === 0 && (
              <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
                هنوز قالبی نیست.
              </Typography>
            )}
          </List>
          <Divider />
          <Box sx={{ p: 1 }}>
            <Button fullWidth startIcon={<AddIcon />} onClick={() => open(data, "new")} sx={{ height: 40 }}>
              قالب جدید
            </Button>
          </Box>
        </Card>

        {form && layout && (
          <Stack direction={{ xs: "column", xl: "row" }} spacing={2} sx={{ flex: 1, minWidth: 0, width: "100%" }} alignItems="flex-start">
            <Card variant="outlined" sx={{ p: 2, borderRadius: 2, flex: 1, minWidth: 0, width: "100%" }}>
              <Stack spacing={2}>
                <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
                  <TextField size="small" label="نام قالب" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} sx={{ minWidth: 220 }} inputProps={{ maxLength: 120 }} />
                  <TextField select size="small" label="کاغذ پیش‌فرض" value={form.default_paper_size} onChange={(e) => setForm({ ...form, default_paper_size: e.target.value })} sx={{ width: 140 }}>
                    <MenuItem value="A4">A4</MenuItem>
                    <MenuItem value="A5">A5</MenuItem>
                  </TextField>
                  <FormControlLabel control={<Checkbox checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />} label="فعال" />
                </Stack>

                <Tabs value={paper} onChange={(_, v) => setPaper(v)}>
                  <Tab value="A4" label="چیدمان A4" />
                  <Tab value="A5" label="چیدمان A5" />
                </Tabs>

                <Typography variant="subtitle2" fontWeight={700}>سربرگ</Typography>
                <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap alignItems="center">
                  <Button component="label" variant="outlined" startIcon={uploading ? <CircularProgress size={16} /> : <ImageOutlinedIcon />} disabled={uploading} sx={{ height: 40 }}>
                    {layout.header.logo_file_id ? "تغییر لوگو" : "بارگذاری لوگو"}
                    <input hidden type="file" accept=".png,.jpg,.jpeg,.webp" onChange={(e) => { handleLogo(e.target.files?.[0]); e.target.value = ""; }} />
                  </Button>
                  {layout.header.logo_file_id && (
                    <Button color="inherit" onClick={() => setHeader({ logo_file_id: null })} sx={{ height: 40 }}>
                      برداشتن لوگو از {paper}
                    </Button>
                  )}
                  <NumberField label="ارتفاع (mm)" value={layout.header.height_mm} min={10} max={120} onChange={(v) => setHeader({ height_mm: v })} />
                </Stack>
                <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
                  <TextField size="small" label="عنوان" value={layout.header.title} onChange={(e) => setHeader({ title: e.target.value })} sx={{ minWidth: 240 }} inputProps={{ maxLength: 120 }} />
                  <TextField size="small" label="زیرعنوان" value={layout.header.subtitle} onChange={(e) => setHeader({ subtitle: e.target.value })} sx={{ minWidth: 240 }} inputProps={{ maxLength: 200 }} />
                </Stack>
                <Stack direction="row" flexWrap="wrap">
                  <FormControlLabel control={<Checkbox checked={layout.header.show_number} onChange={(e) => setHeader({ show_number: e.target.checked })} />} label="شماره" />
                  <FormControlLabel control={<Checkbox checked={layout.header.show_date} onChange={(e) => setHeader({ show_date: e.target.checked })} />} label="تاریخ" />
                  <FormControlLabel control={<Checkbox checked={layout.header.show_attachment} onChange={(e) => setHeader({ show_attachment: e.target.checked })} />} label="پیوست" />
                </Stack>

                <Typography variant="subtitle2" fontWeight={700}>حاشیه‌ها و قلم</Typography>
                <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
                  <NumberField label="بالا (mm)" value={layout.margins_mm.top} min={5} max={60} onChange={(v) => setMargin("top", v)} />
                  <NumberField label="پایین (mm)" value={layout.margins_mm.bottom} min={5} max={60} onChange={(v) => setMargin("bottom", v)} />
                  <NumberField label="راست (mm)" value={layout.margins_mm.right} min={5} max={60} onChange={(v) => setMargin("right", v)} />
                  <NumberField label="چپ (mm)" value={layout.margins_mm.left} min={5} max={60} onChange={(v) => setMargin("left", v)} />
                  <NumberField label="قلم (pt)" value={layout.font_size_pt} min={8} max={18} onChange={(v) => setLayout({ font_size_pt: v })} />
                </Stack>

                <Typography variant="subtitle2" fontWeight={700}>پابرگ</Typography>
                <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
                  <TextField size="small" label="متن پابرگ (نشانی، تلفن، …)" value={layout.footer.text} onChange={(e) => setFooter({ text: e.target.value })} sx={{ minWidth: 300, flex: 1 }} inputProps={{ maxLength: 300 }} />
                  <NumberField label="ارتفاع (mm)" value={layout.footer.height_mm} min={0} max={60} onChange={(v) => setFooter({ height_mm: v })} />
                </Stack>

                <Divider />
                <Typography variant="subtitle2" fontWeight={700}>چیدمان با کد HTML (اختیاری)</Typography>
                <Typography variant="caption" color="text.secondary">
                  اگر پر شود، به‌جای سربرگ/پابرگ ساده‌ی بالا استفاده می‌شود (ارتفاع همان «ارتفاع (mm)» بالاست). {PLACEHOLDER_HELP}
                </Typography>
                <HtmlField label={`HTML سربرگ ${paper}`} value={layout.header.html} onChange={(v) => setHeader({ html: v })} sample={SAMPLE_HEADER_HTML} />
                <HtmlField label={`HTML پابرگ ${paper}`} value={layout.footer.html} onChange={(v) => setFooter({ html: v })} sample={SAMPLE_FOOTER_HTML} />
                <Box>
                  <Button
                    size="small"
                    onClick={() => {
                      const other = paper === "A4" ? "A5" : "A4";
                      setForm((f) => ({
                        ...f,
                        layouts: {
                          ...f.layouts,
                          [other]: {
                            ...f.layouts[other],
                            header: { ...f.layouts[other].header, html: layout.header.html },
                            footer: { ...f.layouts[other].footer, html: layout.footer.html },
                          },
                        },
                      }));
                    }}
                  >
                    کپی HTML این چیدمان به {paper === "A4" ? "A5" : "A4"}
                  </Button>
                </Box>

                {result && <Alert severity={result.ok ? "success" : "error"}>{result.message}</Alert>}
                <Box>
                  <Button variant="contained" startIcon={saving ? <CircularProgress size={16} color="inherit" /> : <SaveOutlinedIcon />} onClick={handleSave} disabled={saving || !form.name.trim()} sx={{ height: 40 }}>
                    {form.id ? "ذخیره (نسخه‌ی تازه)" : "ساخت قالب"}
                  </Button>
                </Box>
              </Stack>
            </Card>

            <Card variant="outlined" sx={{ p: 2, borderRadius: 2, bgcolor: "action.hover", flex: "none", width: { xs: "100%", xl: "auto" }, overflowX: "auto" }}>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
                پیش‌نمایش — کاغذ <bdi dir="ltr">{paper}</bdi>
              </Typography>
              <LetterPreview paper={paper} layout={previewLayout} subject={SAMPLE_SUBJECT} bodyHtml={SAMPLE_BODY} scale={paper === "A5" ? 0.7 : 0.5} siteName="نام سایت" />
            </Card>
          </Stack>
        )}
      </Stack>
    </Box>
  );
}
