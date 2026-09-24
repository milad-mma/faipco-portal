import { Link } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";

/**
 * نمایش متن ساده با لینک‌های قابل کلیک، بدون رندر HTML (لینک‌ها به‌صورت المان React ساخته می‌شوند،
 * پس امکان تزریق اسکریپت وجود ندارد).
 *
 * ورودی: text (متن خام) و onInternalClick (اختیاری؛ هنگام کلیک روی لینک داخلی، مثلاً برای بستن دیالوگ).
 * خروجی: Fragment شامل تکه‌های متن و المان‌های Link؛ اگر text خالی باشد null.
 *
 * دو شکل پشتیبانی می‌شود:
 *   - [متن لینک](آدرس)   ← آدرس می‌تواند https://... یا مسیر داخلی پرتال مثل /leave-requests باشد
 *   - https://... خام     ← خودِ آدرس لینک می‌شود
 *
 * فقط http/https و مسیرهای داخلی که با «/» شروع می‌شوند مجازند؛ هر چیز دیگر (مثلاً javascript:)
 * به‌صورت متن عادی می‌ماند. لینک خارجی در تب جدید و مسیر داخلی با React Router باز می‌شود.
 */
// الگوی یافتن لینک Markdown یا آدرس خام؛ علائم نگارشی انتهایی (فارسی و لاتین) جزو آدرس خام حساب نمی‌شوند
const TOKEN_RE = /\[([^\]\n]+)\]\(([^)\s]+)\)|(https?:\/\/[^\s<>()]+[^\s<>().,;:!?،؛»"'])/g;

// مسیر داخلی پرتال: با «/» شروع شود ولی «//» (آدرس بدون پروتکل) نباشد
function isInternal(url) {
  return url.startsWith("/") && !url.startsWith("//");
}

// فقط مسیر داخلی یا آدرس http/https مجاز است
function isAllowed(url) {
  return isInternal(url) || /^https?:\/\//i.test(url);
}

export default function LinkifiedText({ text, onInternalClick }) {
  if (!text) return null;
  const parts = [];
  let last = 0;
  let key = 0;
  // متن را پیمایش می‌کند و بین هر تطبیق، متن عادی و سپس المان لینک را به parts اضافه می‌کند
  for (const match of text.matchAll(TOKEN_RE)) {
    const [whole, label, mdUrl, bareUrl] = match;
    const url = mdUrl || bareUrl;
    if (!isAllowed(url)) continue;  // آدرس غیرمجاز به‌صورت متن عادی باقی می‌ماند
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
  if (last < text.length) parts.push(text.slice(last));  // باقی‌مانده‌ی متن بعد از آخرین لینک
  return <>{parts}</>;
}
