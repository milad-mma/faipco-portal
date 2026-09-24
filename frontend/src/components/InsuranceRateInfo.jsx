import { Box, Paper, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";

/**
 * متن یک نکته را به آرایه‌ای از رشته و عناصر React تبدیل می‌کند:
 * قطعه‌های داخل **...** به <strong> و داخل __...__ به <u> تبدیل می‌شوند،
 * بقیه‌ی متن به‌صورت رشته‌ی ساده می‌ماند. هیچ HTML ای تفسیر نمی‌شود.
 */
export function renderNote(text) {
  const parts = [];
  const re = /(\*\*[^*]+\*\*|__[^_]+__)/g;
  let last = 0;
  let key = 0;
  for (const m of text.matchAll(re)) {
    if (m.index > last) parts.push(text.slice(last, m.index)); // متن ساده‌ی قبل از نشانه
    const token = m[0];
    const inner = token.slice(2, -2); // متن بدون ** یا __ اطرافش
    parts.push(
      token.startsWith("**") ? (
        <strong key={key++}>{inner}</strong>
      ) : (
        <u key={key++}>{inner}</u>
      )
    );
    last = m.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last)); // متن ساده‌ی بعد از آخرین نشانه
  return parts;
}

// عدد را با جداکننده‌ی هزارگان انگلیسی نمایش می‌دهد (مثلاً 1,250,000)
const fmt = (n) => Number(n || 0).toLocaleString("en-US");

/**
 * جدول نرخ حق بیمه به تفکیک سن (تحت تکفل / غیر تحت تکفل) و کادر آبی نکات.
 * ورودی: rateTable (unit, age_header, ..., rows) و notes (آرایه‌ی رشته).
 * هم در فرم پرسنل و هم در پیش‌نمایش صفحه‌ی تنظیمات استفاده می‌شود.
 */
export default function InsuranceRateInfo({ rateTable, notes }) {
  if (!rateTable) return null;
  return (
    <Box>
      {/* جدول نرخ: سرستون دو ردیفی (سن | حق بیمه → غیر تحت تکفل / تحت تکفل) */}
      <Paper variant="outlined" sx={{ overflow: "auto", mb: 2 }}>
        <Table size="small" sx={{ "& th, & td": { textAlign: "center" } }}>
          <TableHead>
            <TableRow sx={{ "& th": { bgcolor: "grey.900", color: "#fff", fontWeight: 700 } }}>
              <TableCell rowSpan={2}>{rateTable.age_header}</TableCell>
              <TableCell colSpan={2}>حق بیمه ({rateTable.unit})</TableCell>
            </TableRow>
            <TableRow sx={{ "& th": { bgcolor: "grey.900", color: "#fff", fontWeight: 700 } }}>
              <TableCell>{rateTable.non_dependent_header}</TableCell>
              <TableCell>{rateTable.dependent_header}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {rateTable.rows.map((row, i) => (
              <TableRow key={i}>
                <TableCell sx={{ fontWeight: 700 }}>{row.age_label}</TableCell>
                <TableCell sx={{ color: "error.main", fontWeight: 700, direction: "ltr" }}>{fmt(row.non_dependent)}</TableCell>
                <TableCell sx={{ color: "success.main", fontWeight: 700, direction: "ltr" }}>{fmt(row.dependent)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
      {/* کادر آبی نکات؛ فقط وقتی حداقل یک نکته وجود دارد */}
      {notes?.length > 0 && (
        <Box sx={{ bgcolor: "#e7f3fb", border: "1px solid #b6dcf2", color: "#0c4a6e", borderRadius: 2, p: 2 }}>
          <Box component="ul" sx={{ m: 0, pr: 2.5, lineHeight: 2.1 }}>
            {notes.map((n, i) => (
              <Typography component="li" variant="body2" key={i}>
                {renderNote(n)}
              </Typography>
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );
}
