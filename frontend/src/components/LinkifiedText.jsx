import { Link } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";

/**
 * نمایش متن ساده با لینک‌های قابل کلیک - بدون رندر HTML (امکان تزریق اسکریپت
 * وجود ندارد؛ لینک‌ها به‌صورت المان React ساخته می‌شوند).
 *
 * دو شکل پشتیبانی می‌شود:
 *   - [متن لینک](آدرس)   ← آدرس می‌تواند https://... یا مسیر داخلی پرتال مثل /leave-requests باشد
 *   - https://... خام     ← خودِ آدرس لینک می‌شود
 *
 * ⚠️ فقط http/https و مسیرهای داخلی که با «/» شروع می‌شوند مجازند؛ هر چیز دیگر
 * (مثلاً javascript:) به‌صورت متن عادی نمایش داده می‌شود. لینک خارجی در تب
 * جدید باز می‌شود، مسیر داخلی داخل همین پرتال (onInternalClick مثلاً برای
 * بستن دیالوگ).
 */
const TOKEN_RE = /\[([^\]\n]+)\]\(([^)\s]+)\)|(https?:\/\/[^\s<>()]+[^\s<>().,;:!?،؛»"'])/g;

function isInternal(url) {
  return url.startsWith("/") && !url.startsWith("//");
}

function isAllowed(url) {
  return isInternal(url) || /^https?:\/\//i.test(url);
}

export default function LinkifiedText({ text, onInternalClick }) {
  if (!text) return null;
  const parts = [];
  let last = 0;
  let key = 0;
  for (const match of text.matchAll(TOKEN_RE)) {
    const [whole, label, mdUrl, bareUrl] = match;
    const url = mdUrl || bareUrl;
    if (!isAllowed(url)) continue;
    if (match.index > last) parts.push(text.slice(last, match.index));
    const content = label || url;
    parts.push(
      isInternal(url) ? (
        <Link key={key++} component={RouterLink} to={url} onClick={onInternalClick}>
          {content}
        </Link>
      ) : (
        <Link key={key++} href={url} target="_blank" rel="noopener noreferrer" sx={{ wordBreak: "break-all" }}>
          {content}
        </Link>
      )
    );
    last = match.index + whole.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <>{parts}</>;
}
