/**
 * پلاک خودروی ایرانی: ورودی گرافیکی (IranianLicensePlateInput)، تابع بررسی کامل بودن
 * (isPlateComplete) و نمایش فشرده‌ی فقط‌خواندنی (PlateDisplay).
 * چون stylis-plugin-rtl مقدار direction در sx را برمی‌گرداند، ترتیب چپ‌به‌راست پلاک با
 * flexDirection: "row-reverse" (که در سند RTL عناصر را از چپ به راست می‌چیند) تثبیت می‌شود.
 */
import { Box, MenuItem, Select, TextField } from "@mui/material";

// ۱۶ حرف مجاز روی پلاک خودروهای شخصی ایران (بدون حروف مخصوص دسته‌های خاص مثل تاکسی،
// معلولین و نیروی انتظامی)
const PLATE_LETTERS = ["ب", "ج", "د", "س", "ص", "ط", "ق", "ل", "م", "ن", "و", "ه", "ی", "ت", "ع", "ا"];

// فقط ارقام لاتین را نگه می‌دارد و به حداکثر طول مشخص کوتاه می‌کند
function onlyDigits(value, maxLen) {
  return value.replace(/[^0-9]/g, "").slice(0, maxLen);
}

/**
 * ورودی گرافیکی پلاک خودروی ایرانی مطابق فرمت واقعی:
 * [۲ رقم] [حرف] [۳ رقم]  |  ایران [۲ رقم]
 *
 * value: { digits1, letter, digits2, iranCode } (رشته‌های خام، بدون اعتبارسنجی)
 * onChange: (nextValue) => void — کل شیء را با تغییر یک فیلد پس می‌دهد.
 * disabled: غیرفعال کردن همه‌ی فیلدها.
 */
export default function IranianLicensePlateInput({ value, onChange, disabled }) {
  const { digits1 = "", letter = "", digits2 = "", iranCode = "" } = value || {};

  // ارسال کل شیء پلاک به والد با مقدار جدید یک فیلد
  function update(field, val) {
    onChange({ digits1, letter, digits2, iranCode, [field]: val });
  }

  return (
    <Box
      sx={{
        display: "inline-flex",
        alignItems: "stretch",
        border: "3px solid #16324F",
        borderRadius: 2,
        overflow: "hidden",
        bgcolor: "#fff",
        width: "100%",
        maxWidth: 380,
        height: 74,
        // ترتیب چپ‌به‌راست با row-reverse تثبیت می‌شود (direction: "ltr" در sx توسط stylis-plugin-rtl برگردانده می‌شود)
        flexDirection: "row-reverse",
      }}
    >
      {/* بخش اصلی: [۲ رقم] [حرف] [۳ رقم] */}
      <Box
        sx={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 1,
          px: 1,
          // ترتیب چپ‌به‌راست ورودی‌ها هم به همان دلیل با row-reverse تثبیت می‌شود
          flexDirection: "row-reverse",
        }}
      >
        {/* دو رقم اول */}
        <TextField
          value={digits1}
          onChange={(e) => update("digits1", onlyDigits(e.target.value, 2))}
          disabled={disabled}
          placeholder="۱۲"
          inputProps={{
            inputMode: "numeric",
            maxLength: 2,
            style: { textAlign: "center", fontSize: 26, fontWeight: 800, padding: "4px 0", width: 46, color: "#16324F" },
          }}
          variant="standard"
          InputProps={{ disableUnderline: true }}
        />
        {/* انتخاب حرف پلاک */}
        <Select
          value={letter}
          onChange={(e) => update("letter", e.target.value)}
          disabled={disabled}
          displayEmpty
          variant="standard"
          disableUnderline
          sx={{ fontSize: 26, fontWeight: 800, minWidth: 46, color: "#16324F" }}
          MenuProps={{ PaperProps: { sx: { maxHeight: 320 } } }}
        >
          <MenuItem value="" disabled>
            حرف
          </MenuItem>
          {PLATE_LETTERS.map((l) => (
            <MenuItem key={l} value={l} sx={{ fontSize: 20 }}>
              {l}
            </MenuItem>
          ))}
        </Select>
        {/* سه رقم وسط */}
        <TextField
          value={digits2}
          onChange={(e) => update("digits2", onlyDigits(e.target.value, 3))}
          disabled={disabled}
          placeholder="۳۴۵"
          inputProps={{
            inputMode: "numeric",
            maxLength: 3,
            style: { textAlign: "center", fontSize: 26, fontWeight: 800, padding: "4px 0", width: 62, color: "#16324F" },
          }}
          variant="standard"
          InputProps={{ disableUnderline: true }}
        />
      </Box>

      {/* جداکننده + بخش ایران */}
      <Box
        sx={{
          width: 72,
          flexShrink: 0,
          borderInlineStart: "3px solid #16324F",
          bgcolor: "#EAF1F7",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          py: 0.5,
        }}
      >
        <Box sx={{ fontSize: 11, fontWeight: 800, color: "#16324F", mb: 0.25 }}>ایران</Box>
        <TextField
          value={iranCode}
          onChange={(e) => update("iranCode", onlyDigits(e.target.value, 2))}
          disabled={disabled}
          placeholder="۶۷"
          inputProps={{
            inputMode: "numeric",
            maxLength: 2,
            style: { textAlign: "center", fontSize: 20, fontWeight: 800, padding: 0, width: 36, color: "#16324F" },
          }}
          variant="standard"
          InputProps={{ disableUnderline: true }}
        />
      </Box>
    </Box>
  );
}

/** آیا مقدار پلاک کامل و معتبر است (برای فعال/غیرفعال‌کردن دکمه ثبت). */
export function isPlateComplete(value) {
  const { digits1, letter, digits2, iranCode } = value || {};
  return (
    /^[0-9]{2}$/.test(digits1 || "") &&
    Boolean(letter) &&
    /^[0-9]{3}$/.test(digits2 || "") &&
    /^[0-9]{2}$/.test(iranCode || "")
  );
}

/**
 * نمایش فقط‌خواندنی و فشرده‌ی پلاک با ابعاد ثابت — برای فهرست خودروهای من و جدول گزارش Admin/حراست.
 * ورودی: digits1، letter، digits2 و iranCode.
 */
export function PlateDisplay({ digits1, letter, digits2, iranCode }) {
  return (
    <Box
      sx={{
        display: "inline-flex",
        alignItems: "stretch",
        border: "2px solid #16324F",
        borderRadius: 1,
        overflow: "hidden",
        bgcolor: "#fff",
        // stylis-plugin-rtl خصوصیت‌های جهت‌دار sx را برعکس می‌کند و direction: "ltr" در اینجا بی‌اثر است؛
        // بنابراین ترتیب چپ‌به‌راست بخش‌های پلاک با row-reverse تثبیت می‌شود.
        flexDirection: "row-reverse",
        flexShrink: 0,
        // ابعاد ثابت تا همه‌ی پلاک‌ها (مستقل از عرض ارقام یا ناقص بودن) هم‌اندازه باشند
        width: 168,
        height: 38,
      }}
    >
      <Box
        sx={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 0.75,
          px: 1,
          fontSize: 16,
          fontWeight: 800,
          color: "#16324F",
          // ترتیب چپ‌به‌راست ارقام هم به همان دلیل با row-reverse تثبیت می‌شود
          flexDirection: "row-reverse",
          // ارقام با عرض یکسان رندر می‌شوند تا تغییر ارقام چیدمان را جابه‌جا نکند
          fontVariantNumeric: "tabular-nums",
          lineHeight: 1,
          whiteSpace: "nowrap",
        }}
      >
        {/* دو رقم، حرف و سه رقم با حداقل عرض ثابت برای هر بخش */}
        <Box component="span" sx={{ minWidth: 26, textAlign: "center" }}>
          {digits1}
        </Box>
        <Box component="span" sx={{ minWidth: 16, textAlign: "center" }}>
          {letter}
        </Box>
        <Box component="span" sx={{ minWidth: 38, textAlign: "center" }}>
          {digits2}
        </Box>
      </Box>
      <Box
        sx={{
          borderInlineStart: "2px solid #16324F",
          bgcolor: "#EAF1F7",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          // عرض ثابت تا کد استان تک‌رقمی بلوک را باریک‌تر نکند
          width: 38,
          flexShrink: 0,
        }}
      >
        {/* بخش «ایران» و کد استان */}
        <Box sx={{ fontSize: 8, fontWeight: 800, color: "#16324F" }}>ایران</Box>
        <Box sx={{ fontSize: 13, fontWeight: 800, color: "#16324F" }}>{iranCode}</Box>
      </Box>
    </Box>
  );
}
