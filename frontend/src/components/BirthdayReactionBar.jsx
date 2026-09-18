import { useState } from "react";
import { Box, Chip, Collapse, Stack, Typography } from "@mui/material";
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
        <Chip
          size="small"
          label={`${total.toLocaleString("fa-IR")} نفر تبریک گفتند`}
          onClick={() => setShowList((v) => !v)}
          sx={{ height: 22, fontSize: 11, cursor: "pointer" }}
        />
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
                "&:hover": { bgcolor: "action.hover" },
              }}
            >
              <span>{e.char}</span>
              {n > 0 && (
                <Typography component="span" sx={{ fontSize: 10, fontWeight: 700 }}>
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
        <Chip
          size="small"
          label={`${total.toLocaleString("fa-IR")} نفر تبریک گفتند`}
          onClick={() => setShowList((v) => !v)}
          sx={{ mt: 0.75, height: 22, fontSize: 11, cursor: "pointer" }}
        />
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
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography sx={{ fontSize: 12 }} noWrap>
                {r.name}
              </Typography>
              {r.department && (
                <Typography sx={{ fontSize: 10 }} color="text.secondary" noWrap>
                  {r.department}
                </Typography>
              )}
            </Box>
          </Stack>
        ))}
      </Stack>
    </Collapse>
  );
}
