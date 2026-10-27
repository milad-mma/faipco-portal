/**
 * نمایش تاریخ و ساعت شمسی و قالب فشرده‌ی جدول‌ها در موبایل (مثل جدول تردد ماهانه).
 */

// تاریخ شمسی + ساعت:دقیقه («۱۴۰۵/۸/۵ — ۱۳:۲۳»)؛ مقداری که ساعت ندارد (۰۰:۰۰) فقط با تاریخ؛ خالی/نامعتبر → «—»
export function faDateTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  const date = d.toLocaleDateString("fa-IR");
  if (!d.getHours() && !d.getMinutes()) return date;
  return `${date} — ${d.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" })}`;
}

// جدول فشرده: در موبایل فاصله‌ی سلول‌ها و قلم کوچک‌تر تا بدون اسکرول افقی در عرض صفحه جا شود
export const compactTableSx = {
  "& td, & th": {
    px: { xs: 0.75, sm: 1.5 },
    py: { xs: 0.75, sm: 1 },
    fontSize: { xs: "0.75rem", sm: "0.875rem" },
    verticalAlign: "top",
  },
  "& .MuiChip-root": { height: { xs: 22, sm: 24 }, fontSize: { xs: "0.7rem", sm: "0.8125rem" } },
};

// ستونی که در موبایل پنهان است (اطلاعاتش زیر ستون اصلی با onlyXs نمایش داده می‌شود)
export const hideXs = { display: { xs: "none", sm: "table-cell" } };
// متن کمکی که فقط در موبایل زیر ستون اصلی دیده می‌شود
export const onlyXs = { display: { xs: "block", sm: "none" } };
