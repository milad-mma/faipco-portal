import { Box, Card, Chip, Stack, Typography } from "@mui/material";
import InsertDriveFileOutlinedIcon from "@mui/icons-material/InsertDriveFileOutlined";
import { CHILD_TYPES, MEMBER_COLUMNS, MEMBER_LABEL, memberFieldKey, yesNo } from "../utils/family";

/**
 * نمایش فقط‌خواندنی یک پرونده‌ی «مشخصات خانوادگی» (صفحه‌ی پرسنل و پنل منابع انسانی).
 * ورودی: profile (خروجی سرور)، formSettings (تعریف فیلدها/مدارک/گزینه‌ها) و onOpenDoc اختیاری برای دانلود مدرک.
 */
function ReadRow({ label, value }) {
  return (
    <Stack direction="row" spacing={1} sx={{ py: 0.4 }}>
      <Typography variant="body2" color="text.secondary" sx={{ minWidth: 150 }}>
        {label}
      </Typography>
      <Typography variant="body2" fontWeight={700}>
        {value || "—"}
      </Typography>
    </Stack>
  );
}

export default function FamilySummary({ profile, formSettings, onOpenDoc }) {
  const fieldDefs = formSettings.field_defs;
  const defByKey = Object.fromEntries(fieldDefs.map((f) => [f.key, f]));
  const fmt = (def, v, col) => {
    if (def?.kind === "bool") return yesNo(v);
    if (col === "relation") return formSettings.relations[v];
    if (col === "custody") return formSettings.custody_options[v];
    return v;
  };
  const docList = (docs) =>
    docs?.length > 0 && (
      <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
        {docs.map((d) => (
          <Chip
            key={d.id}
            size="small"
            variant="outlined"
            color={d.expired ? "error" : "default"}
            icon={<InsertDriveFileOutlinedIcon />}
            label={`${formSettings.doc_types[d.doc_type]?.label || "مدرک"}${d.expired ? " (منقضی)" : ""}`}
            onClick={onOpenDoc ? () => onOpenDoc(d) : undefined}
          />
        ))}
      </Stack>
    );
  const counters = { son: 0, daughter: 0 };
  return (
    <Stack spacing={1.5}>
      <Box>
        <ReadRow label="وضعیت تاهل" value={formSettings.marital_statuses[profile.marital_status]} />
        {profile.marriage_date && <ReadRow label="تاریخ ازدواج" value={profile.marriage_date} />}
        {profile.separation_date && <ReadRow label="تاریخ طلاق / فوت همسر" value={profile.separation_date} />}
        {profile.is_head_of_household !== null && <ReadRow label="سرپرست خانوار" value={yesNo(profile.is_head_of_household)} />}
        <ReadRow label="دارای فرزند" value={yesNo(profile.has_children)} />
        {docList(profile.documents)}
      </Box>
      {(profile.members || []).map((m) => {
        const n = CHILD_TYPES.includes(m.member_type) ? ++counters[m.member_type] : null;
        return (
          <Card key={m.id} variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
            <Typography fontWeight={800} sx={{ mb: 0.5 }}>
              {MEMBER_LABEL[m.member_type]}
              {n ? ` ${n}` : ""}: {m.first_name} {m.last_name}
            </Typography>
            {MEMBER_COLUMNS[m.member_type].map((col) => {
              if (m[col] === null || m[col] === undefined || m[col] === "") return null;
              const key = memberFieldKey(fieldDefs, m.member_type, col);
              const def = key ? defByKey[key] : { label: "تاریخ تولد", kind: "date" };
              return <ReadRow key={col} label={def.label} value={fmt(def, m[col], col)} />;
            })}
            {docList(m.documents)}
          </Card>
        );
      })}
    </Stack>
  );
}

