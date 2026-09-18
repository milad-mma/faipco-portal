import { Box } from "@mui/material";

/**
 * تب‌های «قرصی» (Segmented) — همان طراحی صفحه اطلاعیه‌ها، استخراج‌شده
 * در یک کامپوننت مشترک تا همه صفحات یک ظاهر واحد داشته باشند.
 *
 * ⚠️ چرا کامپوننت مشترک و نه کپی‌کردن استایل در هر صفحه: با کپی، اولین
 * تغییر طراحی باعث واگرایی صفحات می‌شد. حالا یک منبع واحد است.
 *
 * tabs: [{ key, label, icon? }]
 * value / onChange بر اساس `key` کار می‌کنند (نه ایندکس عددی) - چون
 * ایندکس با پنهان/نمایان شدن شرطی تب‌ها جابه‌جا می‌شود و به باگ منجر
 * می‌شد.
 */
export default function PillTabs({ tabs, value, onChange, sx }) {
  if (!tabs?.length) return null;

  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: `repeat(${tabs.length}, 1fr)`,
        bgcolor: "action.hover",
        borderRadius: 999,
        p: 0.5,
        mb: 3,
        gap: 0.5,
        // ⚠️ در موبایل با تعداد تب زیاد، به‌جای فشرده‌شدن تا حد ناخوانایی،
        // افقی اسکرول می‌شود - همان مشکلی که قبلاً در تب‌های Material بود.
        overflowX: "auto",
        ...sx,
      }}
    >
      {tabs.map((t) => (
        <Box
          key={t.key}
          component="button"
          type="button"
          onClick={() => onChange(t.key)}
          aria-selected={value === t.key}
          sx={{
            height: 34,
            minWidth: 90,
            border: "none",
            fontFamily: "inherit",
            borderRadius: 999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 0.75,
            cursor: "pointer",
            fontSize: 12,
            fontWeight: 700,
            whiteSpace: "nowrap",
            px: 1.5,
            color: value === t.key ? "primary.main" : "text.secondary",
            bgcolor: value === t.key ? "background.paper" : "transparent",
            boxShadow: value === t.key ? 1 : "none",
          }}
        >
          {t.icon}
          {t.label}
        </Box>
      ))}
    </Box>
  );
}
