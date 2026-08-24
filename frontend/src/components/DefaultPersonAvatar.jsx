/**
 * آواتار پیش‌فرض پرسنل — برای وقتی عکس واقعی موجود نیست. عمداً به‌جای رنگ
 * ثابت از currentColor استفاده می‌کند، یعنی همیشه همان رنگی را می‌گیرد که
 * المان بیرونی (مثلاً MuiAvatar با bgcolor تِم‌محور) برایش تعیین کرده —
 * بدون هیچ منطق جداگانه‌ای برای تشخیص تم روشن/تیره، در هر دو حالت خودش را
 * با پس‌زمینه هماهنگ می‌کند.
 */
export default function DefaultPersonAvatar({ size = "70%", sx }) {
  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      fill="currentColor"
      style={sx}
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="50" cy="38" r="19" />
      <path d="M50 63c-23.5 0-38 14.5-38 33v2.5a50 50 0 0 0 76 0V96c0-18.5-14.5-33-38-33z" />
    </svg>
  );
}
