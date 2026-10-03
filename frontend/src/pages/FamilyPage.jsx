import { useEffect, useMemo, useState } from "react";
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
  Grid,
  IconButton,
  LinearProgress,
  MenuItem,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import InsertDriveFileOutlinedIcon from "@mui/icons-material/InsertDriveFileOutlined";
import BackLink from "../components/BackLink";
import FamilySummary from "../components/FamilySummary";
import JalaliCalendarField from "../components/JalaliCalendarField";
import { deleteMyFamilyDocument, downloadFamilyDocument, fetchMyFamily, saveMyFamily, uploadFamilyDocument } from "../api/family";
import {
  CHILD_TYPES,
  MEMBER_COLUMNS,
  MEMBER_LABEL,
  STATUS_COLOR,
  allowedDocuments,
  memberFieldApplies,
  memberFieldKey,
  saveBlob,
  toEn,
} from "../utils/family";

/**
 * صفحه‌ی «مشخصات خانوادگی» پرسنل (مسیر /family).
 * وضعیت تاهل، مشخصات همسر و فرزندان (به تفکیک پسر و دختر) و مدارک را می‌گیرد و برای بررسی منابع انسانی
 * می‌فرستد. کدام فیلد اجباری/اختیاری/مخفی است و کدام مدرک لازم است از تنظیمات پنل منابع انسانی می‌آید
 * (هیچ قاعده‌ای در این صفحه ثابت نیست). اعتبارسنجی نهایی سمت سرور است.
 */



let memberSeq = 0;

function emptyMember(type) {
  return { key: ++memberSeq, member_type: type, first_name: "", last_name: "", documents: [] };
}

// پرونده‌ی سرور → حالت فرم
// مدارک آپلودشده‌ای که هنوز در فرم ثبت نشده‌اند (مثلاً قبل از رفرش صفحه): مدارک سطح پرونده به فرم برمی‌گردند
function profileToForm(profile, formSettings) {
  const unlinked = (profile?.unlinked_documents || []).filter((d) => formSettings?.doc_types[d.doc_type]?.scope === "profile");
  if (!profile || profile.status === "draft") {
    return { marital_status: "", marriage_date: "", separation_date: "", is_head_of_household: null, has_children: null, documents: unlinked, members: [] };
  }
  return {
    marital_status: profile.marital_status || "",
    marriage_date: profile.marriage_date || "",
    separation_date: profile.separation_date || "",
    is_head_of_household: profile.is_head_of_household,
    has_children: profile.has_children,
    documents: [...(profile.documents || []), ...unlinked],
    members: (profile.members || []).map((m) => ({ ...m, key: ++memberSeq, documents: m.documents || [] })),
  };
}

function uploadErrorMessage(err) {
  const detail = err.response?.data?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (!err.response) return "ارتباط با سرور برقرار نشد؛ اتصال اینترنت را بررسی و دوباره تلاش کنید.";
  if (err.response.status === 413) return "حجم فایل برای سرور بیش از حد مجاز است.";
  return `آپلود فایل با خطا مواجه شد (کد ${err.response.status}).`;
}

// یک فیلد بر اساس نوعش (متن، تاریخ، کد ملی، موبایل، بله/خیر، انتخابی)
function FieldInput({ def, mode, value, onChange, options }) {
  const required = mode === "required";
  const label = def.label + (required ? " *" : "");
  if (def.kind === "bool") {
    return (
      <Box>
        <Typography variant="body2" sx={{ mb: 0.25 }}>
          {label}
        </Typography>
        <RadioGroup row value={value === true ? "yes" : value === false ? "no" : ""} onChange={(e) => onChange(e.target.value === "yes")}>
          <FormControlLabel value="yes" control={<Radio size="small" />} label="بله" />
          <FormControlLabel value="no" control={<Radio size="small" />} label="خیر" />
        </RadioGroup>
      </Box>
    );
  }
  if (def.kind === "choice") {
    return (
      <TextField select fullWidth size="small" label={label} value={value || ""} onChange={(e) => onChange(e.target.value || null)}>
        {!required && <MenuItem value="">—</MenuItem>}
        {Object.entries(options || {}).map(([k, v]) => (
          <MenuItem key={k} value={k}>
            {v}
          </MenuItem>
        ))}
      </TextField>
    );
  }
  if (def.kind === "date") {
    // تاریخ‌ها فقط از تقویم شمسی انتخاب می‌شوند؛ تولد/ازدواج/طلاق گذشته‌اند
    // def.future: تاریخ آینده مجاز است (مثل تاریخ اعتبار گواهی تحصیل)
    return <JalaliCalendarField label={def.label} required={required} value={value} onChange={onChange} disableFuture={!def.future} clearable={!required} />;
  }
  const inputProps = {};
  let transform = (v) => v;
  if (def.kind === "national_id") {
    transform = (v) => toEn(v).replace(/\D/g, "").slice(0, 10);
    inputProps.inputMode = "numeric";
  } else if (def.kind === "mobile") {
    transform = (v) => toEn(v).replace(/\D/g, "").slice(0, 11);
    inputProps.inputMode = "tel";
  }
  return (
    <TextField
      fullWidth
      size="small"
      label={label}
      value={value || ""}
      onChange={(e) => onChange(transform(e.target.value))}
      inputProps={{ ...inputProps, maxLength: def.kind === "text" ? 100 : undefined, dir: def.kind === "text" ? undefined : "ltr" }}
    />
  );
}

// جایگاه آپلود یک نوع مدرک
function DocSlot({ docType, formSettings, docs, onAdd, onRemove }) {
  const spec = formSettings.doc_types[docType];
  const required = formSettings.documents[docType]?.mode === "required";
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState("");

  async function handleFile(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError("");
    setProgress(0);
    try {
      const doc = await uploadFamilyDocument(file, docType, setProgress);
      onAdd(doc);
    } catch (err) {
      setError(uploadErrorMessage(err));
    } finally {
      setProgress(null);
    }
  }

  return (
    <Box sx={{ border: 1, borderColor: required && !docs.length ? "warning.main" : "divider", borderRadius: 1.5, p: 1.25, borderStyle: "dashed" }}>
      <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap" useFlexGap>
        <Typography variant="body2" fontWeight={700} sx={{ flex: 1, minWidth: 140 }}>
          {spec.label}
          {required ? " *" : " (اختیاری)"}
        </Typography>
        <Button component="label" size="small" variant="outlined" startIcon={<CloudUploadOutlinedIcon />} disabled={progress !== null}>
          انتخاب فایل
          <input hidden type="file" accept="image/*,application/pdf" onChange={handleFile} />
        </Button>
      </Stack>
      {progress !== null && <LinearProgress variant="determinate" value={progress} sx={{ mt: 1 }} />}
      {error && (
        <Alert severity="error" sx={{ mt: 1, py: 0 }}>
          {error}
        </Alert>
      )}
      {docs.map((d) => (
        <Stack key={d.id} direction="row" alignItems="center" spacing={1} sx={{ mt: 0.75 }}>
          <InsertDriveFileOutlinedIcon fontSize="small" color="action" />
          <Typography variant="caption" sx={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }} noWrap>
            {d.file_name}
            {d.expired ? " — منقضی شده" : d.expires_on ? ` — اعتبار تا ${d.expires_on}` : ""}
          </Typography>
          <IconButton size="small" onClick={() => onRemove(d)} aria-label="حذف مدرک">
            <DeleteOutlineOutlinedIcon fontSize="small" />
          </IconButton>
        </Stack>
      ))}
    </Box>
  );
}

// کارت یک عضو (همسر / پسر / دختر) در حالت ویرایش
function MemberCard({ member, title, formSettings, form, onChange, onRemove, onDocRemove }) {
  const fieldDefs = formSettings.field_defs;
  const defByKey = Object.fromEntries(fieldDefs.map((f) => [f.key, f]));
  // به‌روزرسانی تابعی (بر اساس آخرین نسخه‌ی عضو)، تا پایان یک آپلود طولانی تغییرات تایپ‌شده در همین مدت را پاک نکند
  const set = (patch) => onChange((m) => ({ ...m, ...patch }));
  const docTypes = allowedDocuments(formSettings, form, member);

  return (
    <Card variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <Stack direction="row" alignItems="center" sx={{ mb: 1.5 }}>
        <Typography fontWeight={800} sx={{ flex: 1 }}>
          {title}
        </Typography>
        {onRemove && (
          <Button size="small" color="error" startIcon={<DeleteOutlineOutlinedIcon />} onClick={onRemove}>
            حذف
          </Button>
        )}
      </Stack>
      <Grid container spacing={1.5}>
        <Grid item xs={12} sm={6}>
          <TextField fullWidth size="small" label="نام *" value={member.first_name} onChange={(e) => set({ first_name: e.target.value })} inputProps={{ maxLength: 100 }} />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField fullWidth size="small" label="نام خانوادگی *" value={member.last_name} onChange={(e) => set({ last_name: e.target.value })} inputProps={{ maxLength: 100 }} />
        </Grid>
        {MEMBER_COLUMNS[member.member_type].map((col) => {
          const alwaysRequired = col === "birth_date" && CHILD_TYPES.includes(member.member_type);
          const key = memberFieldKey(fieldDefs, member.member_type, col);
          if (!key && !alwaysRequired) return null;
          const mode = alwaysRequired ? "required" : formSettings.fields[key];
          if (mode === "hidden" || !memberFieldApplies(member.member_type, col, member, formSettings)) return null;
          const def = alwaysRequired ? { label: "تاریخ تولد", kind: "date" } : defByKey[key];
          const options = col === "relation" ? formSettings.relations : col === "custody" ? formSettings.custody_options : null;
          return (
            <Grid item xs={12} sm={def.kind === "bool" ? 12 : 6} md={def.kind === "bool" ? 6 : 4} key={col}>
              <FieldInput def={def} mode={mode} value={member[col]} options={options} onChange={(v) => set({ [col]: v })} />
            </Grid>
          );
        })}
      </Grid>
      {docTypes.length > 0 && (
        <Stack spacing={1} sx={{ mt: 2 }}>
          {docTypes.map((dt) => (
            <DocSlot
              key={dt}
              docType={dt}
              formSettings={formSettings}
              docs={member.documents.filter((d) => d.doc_type === dt)}
              onAdd={(doc) => onChange((m) => ({ ...m, documents: [...m.documents, doc] }))}
              onRemove={(doc) => {
                onDocRemove(doc);
                onChange((m) => ({ ...m, documents: m.documents.filter((d) => d.id !== doc.id) }));
              }}
            />
          ))}
        </Stack>
      )}
    </Card>
  );
}

function SectionCard({ num, title, children }) {
  return (
    <Card variant="outlined" sx={{ borderRadius: 2, mb: 2.5, overflow: "hidden" }}>
      <Stack direction="row" spacing={1.5} alignItems="center" sx={{ px: 2.5, py: 1.5, bgcolor: "action.hover" }}>
        <Box sx={{ width: 30, height: 30, borderRadius: "50%", bgcolor: "primary.main", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800 }}>
          {num}
        </Box>
        <Typography fontWeight={800}>{title}</Typography>
      </Stack>
      <Box sx={{ p: 2.5 }}>{children}</Box>
    </Card>
  );
}

export default function FamilyPage() {
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [dialog, setDialog] = useState(null); // { severity, text }

  async function load() {
    try {
      const d = await fetchMyFamily();
      setData(d);
      setForm(profileToForm(d.profile, d.form));
      // مدارک عضوِ ثبت‌نشده قابل نسبت دادن به عضو خاصی نیستند؛ حذف می‌شوند تا سهمیه‌ی آپلود را پر نکنند
      (d.profile?.unlinked_documents || [])
        .filter((doc) => d.form.doc_types[doc.doc_type]?.scope === "member")
        .forEach((doc) => deleteMyFamilyDocument(doc.id).catch(() => {}));
      const submitted = d.profile && d.profile.status !== "draft";
      setEditing(!submitted && d.can_edit);
    } catch (err) {
      setLoadError(err.response?.data?.detail || "بارگذاری اطلاعات با خطا مواجه شد.");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const formSettings = data?.form;
  const defByKey = useMemo(() => Object.fromEntries((formSettings?.field_defs || []).map((f) => [f.key, f])), [formSettings]);

  if (loadError) return <Alert severity="error">{loadError}</Alert>;
  if (!data || !form) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  const profile = data.profile;
  const submitted = profile && profile.status !== "draft";
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const fieldMode = (key) => formSettings.fields[key];

  async function removeDoc(doc) {
    // مدرک ثبت‌نشده همان لحظه حذف می‌شود؛ مدرک ثبت‌شده با ثبت دوباره‌ی فرم حذف می‌شود
    const linked = [...(profile?.documents || []), ...(profile?.members || []).flatMap((m) => m.documents || [])].some((d) => d.id === doc.id);
    if (!linked) {
      try {
        await deleteMyFamilyDocument(doc.id);
      } catch {
        /* پاک‌سازی خودکار سرور بعداً حذفش می‌کند */
      }
    }
  }

  function setMarital(value) {
    setForm((f) => {
      let members = f.members;
      if (value === "married" && !members.some((m) => m.member_type === "spouse")) {
        members = [emptyMember("spouse"), ...members];
      }
      if (value !== "married") members = members.filter((m) => m.member_type !== "spouse");
      return { ...f, marital_status: value, members };
    });
  }

  function setHasChildren(value) {
    setForm((f) => ({ ...f, has_children: value, members: value ? f.members : f.members.filter((m) => m.member_type === "spouse") }));
  }

  const updateMember = (key, update) => setForm((f) => ({ ...f, members: f.members.map((m) => (m.key === key ? update(m) : m)) }));
  const removeMember = (key) => setForm((f) => ({ ...f, members: f.members.filter((m) => m.key !== key) }));
  const addChild = (type) => setForm((f) => ({ ...f, members: [...f.members, emptyMember(type)] }));

  async function openDoc(doc) {
    try {
      saveBlob(await downloadFamilyDocument(doc.id), doc.file_name);
    } catch {
      setDialog({ severity: "error", text: "دانلود مدرک با خطا مواجه شد." });
    }
  }

  async function handleSubmit() {
    setSaving(true);
    try {
      const payload = {
        marital_status: form.marital_status || null,
        marriage_date: form.marriage_date || null,
        separation_date: form.separation_date || null,
        is_head_of_household: form.is_head_of_household,
        has_children: form.has_children,
        // مدرکی که با پاسخ‌های فعلی موضوعیت ندارد (و جایگاهش پنهان شده) فرستاده نمی‌شود
        document_ids: form.documents.filter((d) => profileDocTypes.includes(d.doc_type)).map((d) => d.id),
        members: form.members.map((m) => {
          const { key, documents, id, ...rest } = m; // eslint-disable-line no-unused-vars
          const allowed = allowedDocuments(formSettings, form, m);
          return { ...rest, document_ids: documents.filter((d) => allowed.includes(d.doc_type)).map((d) => d.id) };
        }),
      };
      await saveMyFamily(payload);
      await load();
      setEditing(false);
      setDialog({ severity: "success", text: "مشخصات خانوادگی ثبت شد و پس از بررسی واحد منابع انسانی اعمال می‌شود." });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setDialog({ severity: "error", text: typeof detail === "string" ? detail : "ثبت فرم با خطا مواجه شد؛ فیلدها را بررسی کنید." });
    } finally {
      setSaving(false);
    }
  }

  const profileDocTypes = allowedDocuments(formSettings, form, null);
  const spouse = form.members.find((m) => m.member_type === "spouse");
  const sons = form.members.filter((m) => m.member_type === "son");
  const daughters = form.members.filter((m) => m.member_type === "daughter");
  const profileField = (column) => {
    const key = `profile.${column}`;
    const mode = fieldMode(key);
    if (mode === "hidden") return null;
    return <FieldInput def={defByKey[key]} mode={mode} value={form[column]} onChange={(v) => set({ [column]: v })} />;
  };

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <BackLink to="/profile" label="بازگشت" />
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }} flexWrap="wrap" useFlexGap>
        <Typography variant="h5" fontWeight={700} sx={{ flex: 1 }}>
          مشخصات خانوادگی
        </Typography>
        {submitted && <Chip color={STATUS_COLOR[profile.status]} label={formSettings.statuses[profile.status]} />}
      </Stack>

      {!data.employee && <Alert severity="info">این بخش فقط برای حساب‌های متصل به پرسنل در دسترس است.</Alert>}
      {data.employee && !data.enabled && !submitted && <Alert severity="info">ثبت مشخصات خانوادگی در حال حاضر غیرفعال است.</Alert>}

      {formSettings.notes?.length > 0 && data.employee && (
        <Alert severity="info" icon={false} sx={{ mb: 2 }}>
          <Stack component="ul" sx={{ m: 0, pr: 2.5, pl: 0 }} spacing={0.5}>
            {formSettings.notes.map((n, i) => (
              <li key={i}>
                <Typography variant="body2">{n}</Typography>
              </li>
            ))}
          </Stack>
        </Alert>
      )}

      {submitted && ["rejected", "returned"].includes(profile.status) && profile.review_note && (
        <Alert severity={profile.status === "rejected" ? "error" : "warning"} sx={{ mb: 2 }}>
          <Typography variant="body2" fontWeight={700}>
            {profile.status === "rejected" ? "مشخصات شما تأیید نشد:" : "لطفاً فرم را اصلاح کنید:"}
          </Typography>
          <Typography variant="body2" sx={{ whiteSpace: "pre-line" }}>
            {profile.review_note}
          </Typography>
        </Alert>
      )}
      {submitted && profile.status === "approved" && (
        <Alert severity="success" sx={{ mb: 2 }}>
          مشخصات شما تأیید شده است{profile.effective_date ? ` (تاریخ اثر: ${profile.effective_date})` : ""}.
        </Alert>
      )}
      {submitted && profile.status === "pending" && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          مشخصات شما در انتظار بررسی واحد منابع انسانی است.
        </Alert>
      )}
      {submitted && !data.can_edit && data.lock_reason && data.enabled && (
        <Alert severity="info" sx={{ mb: 2 }}>
          {data.lock_reason}
        </Alert>
      )}

      {/* حالت نمایش */}
      {submitted && !editing && (
        <Card variant="outlined" sx={{ p: 2.5, borderRadius: 2 }}>
          <FamilySummary profile={profile} formSettings={formSettings} onOpenDoc={openDoc} />
          {data.can_edit && (
            <Button
              variant="contained"
              startIcon={<EditOutlinedIcon />}
              sx={{ mt: 2 }}
              onClick={() => {
                setForm(profileToForm(profile, formSettings));
                setEditing(true);
              }}
            >
              ویرایش مشخصات
            </Button>
          )}
        </Card>
      )}

      {/* حالت ویرایش */}
      {editing && (
        <>
          <SectionCard num={1} title="وضعیت تاهل">
            <RadioGroup row value={form.marital_status} onChange={(e) => setMarital(e.target.value)}>
              {Object.entries(formSettings.marital_statuses).map(([k, v]) => (
                <FormControlLabel key={k} value={k} control={<Radio />} label={v} />
              ))}
            </RadioGroup>
            <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
              {form.marital_status === "married" && profileField("marriage_date") && (
                <Grid item xs={12} sm={6}>
                  {profileField("marriage_date")}
                </Grid>
              )}
              {["divorced", "widowed"].includes(form.marital_status) && profileField("separation_date") && (
                <Grid item xs={12} sm={6}>
                  {profileField("separation_date")}
                </Grid>
              )}
              {profileField("is_head_of_household") && (
                <Grid item xs={12}>
                  {profileField("is_head_of_household")}
                </Grid>
              )}
            </Grid>
            {profileDocTypes.length > 0 && (
              <Stack spacing={1} sx={{ mt: 1.5 }}>
                {profileDocTypes.map((dt) => (
                  <DocSlot
                    key={dt}
                    docType={dt}
                    formSettings={formSettings}
                    docs={form.documents.filter((d) => d.doc_type === dt)}
                    onAdd={(doc) => setForm((f) => ({ ...f, documents: [...f.documents, doc] }))}
                    onRemove={(doc) => {
                      removeDoc(doc);
                      setForm((f) => ({ ...f, documents: f.documents.filter((d) => d.id !== doc.id) }));
                    }}
                  />
                ))}
              </Stack>
            )}
          </SectionCard>

          {spouse && (
            <SectionCard num={2} title="مشخصات همسر">
              <MemberCard
                member={spouse}
                title="همسر"
                formSettings={formSettings}
                form={form}
                onChange={(update) => updateMember(spouse.key, update)}
                onDocRemove={removeDoc}
              />
            </SectionCard>
          )}

          <SectionCard num={spouse ? 3 : 2} title="فرزندان">
            <Typography variant="body2" sx={{ mb: 0.5 }}>
              فرزند دارید؟ *
            </Typography>
            <RadioGroup
              row
              value={form.has_children === true ? "yes" : form.has_children === false ? "no" : ""}
              onChange={(e) => setHasChildren(e.target.value === "yes")}
            >
              <FormControlLabel value="yes" control={<Radio />} label="بله" />
              <FormControlLabel value="no" control={<Radio />} label="خیر" />
            </RadioGroup>
            {form.has_children && (
              <Stack spacing={2.5} sx={{ mt: 1.5 }}>
                {[
                  ["son", "پسران", sons],
                  ["daughter", "دختران", daughters],
                ].map(([type, title, list]) => (
                  <Box key={type}>
                    <Stack direction="row" alignItems="center" sx={{ mb: 1 }}>
                      <Typography fontWeight={800} sx={{ flex: 1 }}>
                        {title} ({list.length.toLocaleString("fa-IR")})
                      </Typography>
                      <Button size="small" variant="outlined" color={type === "son" ? "success" : "info"} startIcon={<AddIcon />} onClick={() => addChild(type)}>
                        افزودن {MEMBER_LABEL[type]}
                      </Button>
                    </Stack>
                    <Stack spacing={1.5}>
                      {list.map((m, i) => (
                        <MemberCard
                          key={m.key}
                          member={m}
                          title={`${MEMBER_LABEL[type]} ${(i + 1).toLocaleString("fa-IR")}`}
                          formSettings={formSettings}
                          form={form}
                          onChange={(update) => updateMember(m.key, update)}
                          onRemove={() => removeMember(m.key)}
                          onDocRemove={removeDoc}
                        />
                      ))}
                    </Stack>
                  </Box>
                ))}
              </Stack>
            )}
          </SectionCard>

          <Stack direction="row" spacing={1.5} sx={{ mb: 4 }}>
            <Button variant="contained" size="large" onClick={handleSubmit} disabled={saving} startIcon={saving ? <CircularProgress size={18} color="inherit" /> : null}>
              ثبت و ارسال برای بررسی
            </Button>
            {submitted && (
              <Button size="large" onClick={() => setEditing(false)} disabled={saving}>
                انصراف
              </Button>
            )}
          </Stack>
        </>
      )}

      <Dialog open={Boolean(dialog)} onClose={() => setDialog(null)} maxWidth="xs" fullWidth>
        <DialogTitle>{dialog?.severity === "success" ? "ثبت شد" : "خطا"}</DialogTitle>
        <DialogContent>
          <Alert severity={dialog?.severity || "info"}>{dialog?.text}</Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog(null)}>بستن</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
