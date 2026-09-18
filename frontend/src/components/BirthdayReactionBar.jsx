import { useState } from "react";
import { Box, Collapse, Stack, Typography } from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { setBirthdayReaction } from "../api/employees";

/**
 * ⚠️ طبق تصمیمات صریح کاربر:
 *   - چهار ایموجی ثابت، هرکدام با معنای مشخص در فضای اداری.
 *   - معنی هر ایموجی **بعد از انتخاب** نمایش داده می‌شود، نه همیشه -
 *     اگر هر چهار توضیح دائم زیر نوار بودند، کارت داشبورد سه‌برابر
 *     بلندتر می‌شد و بقیه کارت‌ها را هل می‌داد. روی دسکتاپ با نگه‌داشتن
 *     موس (title) هم قابل‌دیدن است، پیش از انتخاب.
 *   - فهرست تبریک‌گویندگان برای همه قابل‌مشاهده است، ولی پیش‌فرض بسته
 *     است تا ارتفاع کارت را اشغال نکند.
 *   - خودِ متولد نمی‌تواند به تولد خودش ری‌اکشن بزند (سمت سرور هم اعمال
 *     می‌شود؛ اینجا فقط نوار را غیرفعال نشان می‌دهیم).
 */
const EMOJIS = [
  { key: "party", char: "🎉", meaning: "تبریک پرانرژی و ایجاد نشاط تیمی؛ مناسب برای همه" },
  { key: "cake", char: "🎂", meaning: "استانداردترین تبریک اداری؛ کاملاً رسمی، خنثی و ایمن برای همه رده‌ها" },
  { key: "white_heart", char: "🤍", meaning: "نماد احترام، پاکی و آرزوی سلامتی؛ گزینه‌ای محترمانه و بی‌طرف" },
  { key: "blue_heart", char: "💙", meaning: "نماد وفاداری سازمانی و روحیه تیمی؛ مناسب برای هم‌رده‌ها و اعضای تیم" },
];

const EMOJI_BY_KEY = Object.fromEntries(EMOJIS.map((e) => [e.key, e.char]));

// ⚠️ طبق درخواست صریح کاربر: فعل باید با تعداد مطابقت کند - «۱ نفر تبریک
// گفت» در برابر «۳ نفر تبریک گفتند». در یک تابع مشترک نگه داشته شده تا
// دو جایی که این متن نمایش داده می‌شود هرگز از هم واگرا نشوند.
function greetingLabel(total) {
  const verb = total === 1 ? "گفت" : "گفتند";
  return `${total.toLocaleString("fa-IR")} نفر تبریک ${verb}`;
}

/**
 * ⚠️ طبق گزارش کاربر: نسخه قبلی یک Chip ساده بود و هیچ نشانه‌ای نداشت
 * که کلیک‌پذیر است. حالا با رنگ لینک، آیکون فلش (که با باز/بسته شدن
 * می‌چرخد) و زیرخط هنگام Hover، کاملاً واضح است که باید رویش زد.
 */
function ReactorsToggle({ total, open, onClick }) {
  return (
    <Box
      component="button"
      type="button"
      onClick={onClick}
      aria-expanded={open}
      sx={{
        mt: 0.75,
        display: "flex",
        alignItems: "center",
        gap: 0.25,
        px: 0,
        py: 0.25,
        border: "none",
        bgcolor: "transparent",
        cursor: "pointer",
        color: "primary.main",
        fontSize: 11,
        fontWeight: 700,
        fontFamily: "inherit",
        "&:hover": { textDecoration: "underline" },
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

export default function BirthdayReactionBar({ person, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [showList, setShowList] = useState(false);
  const [hint, setHint] = useState(null);
  const [error, setError] = useState("");

  const counts = person.reaction_counts || {};
  const reactors = person.reactors || [];
  const total = reactors.length;

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

  // ⚠️ خودِ متولد نوار ری‌اکشن نمی‌بیند - فقط تعداد تبریک‌ها و فهرست.
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
                // ⚠️ رنگ صریح متن دکمه - عنصر <button> رنگ پیش‌فرض مرورگر را
                // می‌گیرد (نه رنگ تم)، پس در دارک‌مود باید صریح تعیین شود.
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
                    // ⚠️ رفع باگ دارک‌مود: قبلاً هیچ رنگی تعیین نشده بود، پس
                    // عدد رنگ پیش‌فرض دکمه (مشکی) را می‌گرفت و در حالت تیره
                    // روی پس‌زمینه تیره کاملاً نامرئی می‌شد.
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

      {total > 0 && (
        <ReactorsToggle total={total} open={showList} onClick={() => setShowList((v) => !v)} />
      )}
      <ReactorList open={showList} reactors={reactors} />
    </Box>
  );
}

function ReactorList({ open, reactors }) {
  return (
    <Collapse in={open}>
      <Stack spacing={0.5} sx={{ mt: 0.75, pt: 0.75, borderTop: "1px solid", borderColor: "divider" }}>
        {reactors.map((r, i) => (
          <Stack key={`${r.user_id}-${i}`} direction="row" alignItems="center" spacing={1}>
            <Typography sx={{ fontSize: 13, width: 18 }}>{EMOJI_BY_KEY[r.emoji] || "•"}</Typography>
            {/* ⚠️ طبق درخواست صریح کاربر: واحد سازمانی کنار نام باشد، نه
                زیر آن. noWrap روی خودِ ردیف است تا اگر نام و واحد با هم
                جا نشدند، به‌جای شکستن به خط دوم، با «…» کوتاه شود. */}
            <Typography sx={{ fontSize: 12, minWidth: 0, flex: 1 }} noWrap>
              {r.name}
              {r.department && (
                <Typography component="span" sx={{ fontSize: 11, ml: 0.75 }} color="text.secondary">
                  — {r.department}
                </Typography>
              )}
            </Typography>
          </Stack>
        ))}
      </Stack>
    </Collapse>
  );
}
