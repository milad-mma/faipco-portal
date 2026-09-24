/**
 * نوار تبریک تولد (ری‌اکشن ایموجی) زیر هر همکار متولد در کارت تولدهای داشبورد.
 * شامل: کامپوننت اصلی BirthdayReactionBar، دکمه‌ی باز/بسته کردن فهرست تبریک‌گویندگان (ReactorsToggle)
 * و خود فهرست (ReactorList).
 */
import { useState } from "react";
import { Box, Collapse, Stack, Typography } from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import EmployeeAvatar from "./EmployeeAvatar";
import { setBirthdayReaction } from "../api/employees";

// چهار ایموجی ثابت تبریک؛ key همان مقداری است که به سرور فرستاده می‌شود و meaning بعد از انتخاب
// (و روی دسکتاپ به‌صورت title هنگام hover) نمایش داده می‌شود
const EMOJIS = [
  { key: "party", char: "🎉", meaning: "تبریک پرانرژی و ایجاد نشاط تیمی؛ مناسب برای همه" },
  { key: "cake", char: "🎂", meaning: "استانداردترین تبریک اداری؛ کاملاً رسمی، خنثی و ایمن برای همه رده‌ها" },
  { key: "white_heart", char: "🤍", meaning: "نماد احترام، پاکی و آرزوی سلامتی؛ گزینه‌ای محترمانه و بی‌طرف" },
  { key: "blue_heart", char: "💙", meaning: "نماد وفاداری سازمانی و روحیه تیمی؛ مناسب برای هم‌رده‌ها و اعضای تیم" },
];

// نگاشت key ایموجی به کاراکتر آن
const EMOJI_BY_KEY = Object.fromEntries(EMOJIS.map((e) => [e.key, e.char]));

// متن تعداد تبریک‌ها با فعل مطابق تعداد («۱ نفر تبریک گفت» / «۳ نفر تبریک گفتند»)؛
// هر دو محل نمایش این متن از همین تابع استفاده می‌کنند
function greetingLabel(total) {
  const verb = total === 1 ? "گفت" : "گفتند";
  return `${total.toLocaleString("fa-IR")} نفر تبریک ${verb}`;
}

/**
 * دکمه‌ی تمام‌عرض «N نفر تبریک گفتند» که فهرست تبریک‌گویندگان را باز/بسته می‌کند.
 * ورودی: total (تعداد)، open (وضعیت باز بودن فهرست) و onClick.
 * خروجی: یک <button> با کادر، پس‌زمینه و آیکون فلشی که با باز شدن ۱۸۰ درجه می‌چرخد.
 */
function ReactorsToggle({ total, open, onClick }) {
  return (
    <Box
      component="button"
      type="button"
      onClick={onClick}
      aria-expanded={open}
      sx={{
        // عرض کامل، وسط‌چین، با کادر و پس‌زمینه تا ظاهر دکمه داشته باشد
        mt: 1,
        width: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 0.5,
        px: 1,
        py: 0.6,
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        bgcolor: "action.hover",
        cursor: "pointer",
        color: "primary.main",
        fontSize: 11,
        fontWeight: 700,
        fontFamily: "inherit",
        "&:hover": { bgcolor: "action.selected" },
      }}
    >
      {greetingLabel(total)}
      <ExpandMoreIcon
        sx={{
          fontSize: 15,
          transition: "transform 0.2s",
          transform: open ? "rotate(180deg)" : "none",
        }}
      />
    </Box>
  );
}

/**
 * نوار ری‌اکشن تولد برای یک همکار.
 * ورودی: person (اطلاعات فرد متولد شامل reaction_counts، reactors، my_reaction، is_self) و
 * onChanged (برای بارگذاری مجدد داده‌ها پس از ثبت ری‌اکشن).
 * خروجی: دکمه‌های ایموجی با تعداد هرکدام، معنی ایموجی انتخاب‌شده و فهرست تبریک‌گویندگان (پیش‌فرض بسته).
 * خودِ فرد متولد نوار ایموجی را نمی‌بیند (سمت سرور هم اعمال می‌شود) و فقط تعداد و فهرست را می‌بیند.
 */
export default function BirthdayReactionBar({ person, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [showList, setShowList] = useState(false); // باز بودن فهرست تبریک‌گویندگان
  const [hint, setHint] = useState(null); // key ایموجی تازه انتخاب‌شده برای نمایش معنی آن؛ null = چیزی نمایش داده نشود
  const [error, setError] = useState("");

  const counts = person.reaction_counts || {}; // تعداد هر ایموجی به تفکیک key
  const reactors = person.reactors || [];
  const total = reactors.length;

  // ثبت/تغییر/برداشتن ری‌اکشن؛ اگر سرور emoji خالی برگرداند (ری‌اکشن برداشته شد) معنی پنهان می‌شود
  async function handleClick(emojiKey) {
    if (person.is_self || busy) return;
    setError("");
    setBusy(true);
    try {
      const result = await setBirthdayReaction(person.id, emojiKey);
      setHint(result.emoji ? emojiKey : null);
      onChanged();
    } catch (err) {
      setError(err.response?.data?.detail || "ثبت تبریک با خطا مواجه شد.");
    } finally {
      setBusy(false);
    }
  }

  // خودِ متولد نوار ری‌اکشن نمی‌بیند؛ فقط تعداد تبریک‌ها و فهرست (در صورت وجود)
  if (person.is_self) {
    return total > 0 ? (
      <Box sx={{ mt: 0.75 }}>
        <ReactorsToggle total={total} open={showList} onClick={() => setShowList((v) => !v)} />
        <ReactorList open={showList} reactors={reactors} />
      </Box>
    ) : null;
  }

  return (
    <Box sx={{ mt: 0.75 }}>
      {/* دکمه‌های ایموجی؛ ایموجی انتخاب‌شده‌ی کاربر با کادر رنگ اصلی مشخص می‌شود */}
      <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
        {EMOJIS.map((e) => {
          const n = counts[e.key] || 0;
          const mine = person.my_reaction === e.key;
          return (
            <Box
              key={e.key}
              component="button"
              type="button"
              title={e.meaning}
              disabled={busy}
              onClick={() => handleClick(e.key)}
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 0.5,
                px: 1,
                py: 0.35,
                borderRadius: 999,
                fontSize: 14,
                cursor: busy ? "default" : "pointer",
                bgcolor: mine ? "action.selected" : "transparent",
                border: "1px solid",
                borderColor: mine ? "primary.main" : "divider",
                // رنگ صریح متن: عنصر <button> رنگ پیش‌فرض مرورگر را می‌گیرد نه رنگ تم (مهم در دارک‌مود)
                color: "text.primary",
                "&:hover": { bgcolor: "action.hover" },
              }}
            >
              <span>{e.char}</span>
              {n > 0 && (
                <Typography
                  component="span"
                  sx={{
                    fontSize: 10,
                    fontWeight: 700,
                    // رنگ صریح عدد از تم تا در دارک‌مود رنگ پیش‌فرض دکمه (مشکی) را نگیرد
                    color: mine ? "primary.main" : "text.secondary",
                  }}
                >
                  {n.toLocaleString("fa-IR")}
                </Typography>
              )}
            </Box>
          );
        })}
      </Stack>

      {/* خطای ثبت تبریک */}
      {error && (
        <Typography variant="caption" color="error" display="block" sx={{ mt: 0.5 }}>
          {error}
        </Typography>
      )}

      {/* معنی ایموجی انتخاب‌شده - فقط بعد از انتخاب */}
      <Collapse in={Boolean(hint)}>
        {hint && (
          <Typography
            variant="caption"
            sx={{ mt: 0.75, display: "block", p: 0.75, borderRadius: 1, bgcolor: "action.hover", lineHeight: 1.6 }}
          >
            {EMOJI_BY_KEY[hint]} {EMOJIS.find((e) => e.key === hint)?.meaning}
          </Typography>
        )}
      </Collapse>

      {/* دکمه و فهرست تبریک‌گویندگان */}
      {total > 0 && (
        <ReactorsToggle total={total} open={showList} onClick={() => setShowList((v) => !v)} />
      )}
      <ReactorList open={showList} reactors={reactors} />
    </Box>
  );
}

/**
 * فهرست تاشوی تبریک‌گویندگان.
 * ورودی: open (باز/بسته) و reactors (هر مورد: employee_id، has_photo، name، department، emoji).
 * خروجی: Collapse شامل ردیف‌های آواتار، نام، واحد و ایموجی هر نفر.
 */
function ReactorList({ open, reactors }) {
  return (
    <Collapse in={open}>
      <Stack spacing={0.5} sx={{ mt: 0.75, pt: 0.75, borderTop: "1px solid", borderColor: "divider" }}>
        {/* هر ردیف به همان ترتیب ردیف فرد متولد: آواتار (سمت راست در RTL)، نام، واحد سازمانی
            و در انتها ری‌اکشن آن شخص. */}
        {reactors.map((r, i) => (
          <Stack key={`${r.user_id}-${i}`} direction="row" alignItems="center" spacing={1}>
            <EmployeeAvatar employeeId={r.employee_id} hasPhoto={r.has_photo} size={24} />
            <Typography sx={{ fontSize: 12, minWidth: 0, flex: 1 }} noWrap>
              {r.name}
              {r.department && (
                <Typography component="span" sx={{ fontSize: 11, ml: 0.75 }} color="text.secondary">
                  — {r.department}
                </Typography>
              )}
            </Typography>
            {/* ایموجی بیرون از بلوک noWrap و با flexShrink:0 است تا با کوتاه شدن نام/واحد بلند («…»)
                همیشه دیده شود. */}
            <Typography sx={{ fontSize: 13, flexShrink: 0 }}>
              {EMOJI_BY_KEY[r.emoji] || "•"}
            </Typography>
          </Stack>
        ))}
      </Stack>
    </Collapse>
  );
}
