// Dates in office automation use the organization's Asia/Tehran calendar day,
// not the phone's timezone (important for Android TWA and travelling employees).
import { gregorianToJalali, jalaliToGregorian } from "./jalaliDate.js";
const tehran = new Intl.DateTimeFormat("en-US", {
  timeZone: "Asia/Tehran", year: "numeric", month: "2-digit", day: "2-digit",
});
const pad = (n) => String(n).padStart(2, "0");
export function oaToJalali(iso) {
  if (!iso) return null;
  const parts = Object.fromEntries(tehran.formatToParts(new Date(iso)).map((p) => [p.type, p.value]));
  const d = new Date(Number(parts.year), Number(parts.month) - 1, Number(parts.day));
  const { jy, jm, jd } = gregorianToJalali(d);
  return `${jy}/${pad(jm)}/${pad(jd)}`;
}
export function oaJalaliEndOfDay(value) {
  const m = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/.exec(value || "");
  if (!m) return null;
  const d = jalaliToGregorian(Number(m[1]), Number(m[2]), Number(m[3]));
  // Iran observes UTC+03:30 without DST in the supported contemporary dates.
  return new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate(), 20, 29)).toISOString();
}
