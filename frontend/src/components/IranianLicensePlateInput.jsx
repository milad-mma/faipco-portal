import { Box, MenuItem, Select, TextField } from "@mui/material";

// حروف مجاز روی پلاک خودروهای شخصی ایران — مجموعه رایج/استاندارد (بدون
// حروفی که فقط مخصوص دسته‌های خاص‌اند مثل تاکسی/معلولین/نیروی انتظامی).
// طبق درخواست صریح کارفرما — فقط همین ۱۶ حرف مجاز پلاک، نه فهرست کامل
// حروف الفبا (بقیه حروف اصلاً روی پلاک خودروی ایران دیده نمی‌شوند).
const PLATE_LETTERS = ["ب", "ج", "د", "س", "ص", "ط", "ق", "ل", "م", "ن", "و", "ه", "ی", "ت", "ع", "ا"];

function onlyDigits(value, maxLen) {
  return value.replace(/[^0-9]/g, "").slice(0, maxLen);
}

/**
 * ورودی گرافیکی پلاک خودروی ایرانی — دقیقاً مطابق فرمت واقعی:
 * [۲ رقم] [حرف] [۳ رقم]  |  ایران [۲ رقم]
 *
 * value: { digits1, letter, digits2, iranCode } (رشته‌های خام، بدون اعتبارسنجی)
 * onChange: (nextValue) => void — کل شیء را با تغییر یک فیلد پس می‌دهد.
 */
export default function IranianLicensePlateInput({ value, onChange, disabled }) {
  const { digits1 = "", letter = "", digits2 = "", iranCode = "" } = value || {};

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
        direction: "ltr", // پلاک همیشه از چپ به راست خوانده می‌شود، صرف‌نظر از جهت کلی صفحه
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
        }}
      >
        <TextField
          value={digits1}
          onChange={(e) => update("digits1", onlyDigits(e.target.value, 2))}
          disabled={disabled}
          placeholder="۱۲"
          inputProps={{
            inputMode: "numeric",
            maxLength: 2,
            style: { textAlign: "center", fontSize: 26, fontWeight: 800, padding: "4px 0", width: 46 },
          }}
          variant="standard"
          InputProps={{ disableUnderline: true }}
        />
        <Select
          value={letter}
          onChange={(e) => update("letter", e.target.value)}
          disabled={disabled}
          displayEmpty
          variant="standard"
          disableUnderline
          sx={{ fontSize: 26, fontWeight: 800, minWidth: 46 }}
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
        <TextField
          value={digits2}
          onChange={(e) => update("digits2", onlyDigits(e.target.value, 3))}
          disabled={disabled}
          placeholder="۳۴۵"
          inputProps={{
            inputMode: "numeric",
            maxLength: 3,
            style: { textAlign: "center", fontSize: 26, fontWeight: 800, padding: "4px 0", width: 62 },
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
            style: { textAlign: "center", fontSize: 20, fontWeight: 800, padding: 0, width: 36 },
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

/** نمایش فقط‌خواندنی/فشرده همان پلاک — برای لیست خودروهای من و جدول گزارش Admin/حراست. */
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
        direction: "ltr",
        flexShrink: 0,
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 0.75,
          px: 1,
          py: 0.5,
          fontSize: 16,
          fontWeight: 800,
          color: "#16324F",
        }}
      >
        <span>{digits1}</span>
        <span>{letter}</span>
        <span>{digits2}</span>
      </Box>
      <Box
        sx={{
          borderInlineStart: "2px solid #16324F",
          bgcolor: "#EAF1F7",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          px: 0.75,
        }}
      >
        <Box sx={{ fontSize: 8, fontWeight: 800, color: "#16324F" }}>ایران</Box>
        <Box sx={{ fontSize: 13, fontWeight: 800, color: "#16324F" }}>{iranCode}</Box>
      </Box>
    </Box>
  );
}
