import { Box } from "@mui/material";

/**
 * تب‌های «قرصی» (Segmented) مشترک بین صفحات برای ظاهر یکسان.
 * ورودی: tabs: [{ key, label, icon? }]، value (کلید تب فعال)، onChange(key) و sx اختیاری برای ظرف.
 * value / onChange بر اساس `key` کار می‌کنند نه ایندکس، تا پنهان/نمایان شدن شرطی تب‌ها انتخاب را جابه‌جا نکند.
 * خروجی: شبکه‌ای از دکمه‌ها با عرض مساوی؛ اگر tabs خالی باشد null.
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
        // در موبایل با تعداد تب زیاد، به‌جای فشرده شدن تا حد ناخوانایی، افقی اسکرول می‌شود
        overflowX: "auto",
        ...sx,
      }}
    >
      {/* هر تب یک button است؛ تب فعال با پس‌زمینه‌ی روشن و سایه متمایز می‌شود */}
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
