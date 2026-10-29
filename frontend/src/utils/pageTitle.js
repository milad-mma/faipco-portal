/**
 * عنوان فارسی یک مسیر پرتال برای گزارش «پرسنل آنلاین» (صفحه‌ای که شخص الان باز کرده؛ Migration 129).
 * اول صفحه‌های پرسنل (پنل کاربری)، بعد منوی مدیریت (NAV_ITEMS)؛ مسیرهای زیرصفحه با بلندترین پیشوند منطبق؛
 * مسیر ناشناخته همان مسیر برگردانده می‌شود.
 */
import { NAV_ITEMS } from "../config/navItems";

const PERSONNEL_PAGES = {
  "/my-dashboard": "داشبورد شخصی",
  "/profile": "پنل کاربری",
  "/notices": "اطلاعیه‌ها",
  "/notices/new": "اطلاعیه‌ی جدید",
  "/feedback": "انتقادات و پیشنهادات",
  "/my-vehicles": "خودروهای من",
  "/insurance-hub": "بیمه تکمیلی",
  "/insurance": "ثبت‌نام بیمه تکمیلی",
  "/insurance/invoices": "صورتحساب‌های بیمه",
  "/family": "مشخصات خانوادگی",
  "/bank-info": "اطلاعات بانکی",
  "/requests": "کارتابل درخواست",
  "/loans": "درخواست وام",
  "/advances": "درخواست مساعده",
  "/leave-requests": "درخواست مرخصی/ماموریت",
  "/my-performance": "ارزیابی عملکرد من",
  "/attendance-clock": "ورود و خروج",
  "/monthly-attendance": "گزارش تردد ماهانه",
  "/monthly-attendance/my-staff": "تردد پرسنل من",
  "/sites": "سایت‌ها",
};

let table = null;
function buildTable() {
  const map = { ...PERSONNEL_PAGES };
  const walk = (items) => {
    for (const item of items || []) {
      if (item.path && item.label && !(item.path in map)) map[item.path] = item.label;
      walk(item.children);
    }
  };
  walk(NAV_ITEMS);
  map["/"] = map["/"] || "داشبورد";
  return map;
}

export function pageTitle(path) {
  if (!path) return "";
  table ||= buildTable();
  if (table[path]) return table[path];
  // زیرصفحه (مثل /sites/3/settings یا /performance/forms/12): بلندترین پیشوند منطبق
  const prefix = Object.keys(table)
    .filter((p) => p !== "/" && path.startsWith(`${p}/`))
    .sort((a, b) => b.length - a.length)[0];
  return prefix ? table[prefix] : path;
}
