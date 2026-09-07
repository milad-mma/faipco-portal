import DashboardOutlinedIcon from "@mui/icons-material/DashboardOutlined";
import GroupOutlinedIcon from "@mui/icons-material/GroupOutlined";
import ApartmentOutlinedIcon from "@mui/icons-material/ApartmentOutlined";
import CorporateFareOutlinedIcon from "@mui/icons-material/CorporateFareOutlined";
import SyncOutlinedIcon from "@mui/icons-material/SyncOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import AdminPanelSettingsOutlinedIcon from "@mui/icons-material/AdminPanelSettingsOutlined";
import CloudDownloadOutlinedIcon from "@mui/icons-material/CloudDownloadOutlined";
import RateReviewOutlinedIcon from "@mui/icons-material/RateReviewOutlined";
import AccountTreeOutlinedIcon from "@mui/icons-material/AccountTreeOutlined";
import EventOutlinedIcon from "@mui/icons-material/EventOutlined";
import AssignmentOutlinedIcon from "@mui/icons-material/AssignmentOutlined";
import SystemUpdateAltOutlinedIcon from "@mui/icons-material/SystemUpdateAltOutlined";
import VpnLockOutlinedIcon from "@mui/icons-material/VpnLockOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import GroupAddOutlinedIcon from "@mui/icons-material/GroupAddOutlined";
import FingerprintOutlinedIcon from "@mui/icons-material/FingerprintOutlined";
import CakeOutlinedIcon from "@mui/icons-material/CakeOutlined";
import DirectionsCarFilledOutlinedIcon from "@mui/icons-material/DirectionsCarFilledOutlined";
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import AssessmentOutlinedIcon from "@mui/icons-material/AssessmentOutlined";
import ForumOutlinedIcon from "@mui/icons-material/ForumOutlined";

/**
 * ⚠️ منبع واحد و مرکزی همه مقصدهای منو-دار پروژه (Single Source of
 * Truth) - قبلاً دو لیست کاملاً جدا و دستی وجود داشت: NAV_ITEMS در
 * Layout.jsx (برای منوی کناری Admin) و EXTRA_ACCESS_ITEMS در
 * ProfilePage.jsx (برای «دسترسی‌های ویژه» کاربران غیر-Admin در نوار
 * پایین). این دوگانگی دقیقاً همان چیزی بود که باعث شد «ارزیابی عملکرد»
 * برای کاربران غیر-Admin با مجوز کامل، هیچ راه دسترسی از UI نداشته
 * باشد - چون فقط به یکی از این دو لیست اضافه شده بود، نه هردو.
 *
 * از این به بعد، هر مقصد جدید فقط **یک‌بار**، همین‌جا اضافه می‌شود -
 * هم Layout.jsx (منوی کناری/نوار پایین Admin) و هم ProfilePage.jsx
 * («دسترسی‌های ویژه») از همین یک آرایه می‌خوانند؛ اگر یک آیتم children
 * داشته باشد، ProfilePage.jsx آن را مسطح (Flatten) می‌کند - چون آن‌جا
 * مفهوم زیرمنو وجود ندارد.
 *
 * شکل هر آیتم:
 *   label: متن نمایشی
 *   path: مسیر
 *   icon: JSX آیکون
 *   adminOnly (اختیاری): فقط ادمین اصلی (is_superuser) - نه با مجوز، با خودِ is_superuser
 *   hiddenForAdmin (اختیاری): برعکس - برای ادمین اصلی مخفی است
 *   check (اختیاری): (user) => boolean - اگر تعریف نشود، یعنی محدودیت
 *     خاصی ندارد (فقط adminOnly/hiddenForAdmin ملاک است). برای آیتم‌های
 *     دارای children، اگر check تعریف نشود، خودکار به‌صورت «حداقل یکی
 *     از فرزندان قابل‌دسترسی است» محاسبه می‌شود - یعنی برای اضافه‌کردن
 *     یک زیرمنوی جدید به یک آیتم موجود، هرگز نیازی به دست‌کاری جداگانه
 *     این check نیست.
 *   ownPageCheck (اختیاری، فقط برای آیتم‌های دارای children): اگر خودِ
 *     مسیر والد (نه یکی از فرزندانش) به یک مجوز مشخص و محدودتر از
 *     «هر فرزندی» نیاز دارد (مثلاً صفحه /access فقط با can_manage_users
 *     باز می‌شود، نه با هرکدام از پنج مجوز فرزندانش)، اینجا مشخص کنید -
 *     Layout.jsx در این حالت اگر ownPageCheck کاربر را رد کند ولی
 *     حداقل یک فرزند در دسترس باشد، کلیک روی والد را به همان اولین
 *     فرزند در‌دسترس هدایت می‌کند (نه به یک مسیر بسته).
 *   children (اختیاری): آرایه‌ای از همین شکل (بدون children تودرتوی بیشتر)
 */
export const NAV_ITEMS = [
  { label: "داشبورد", path: "/", icon: <DashboardOutlinedIcon />, adminOnly: true },
  {
    label: "پرسنل",
    path: "/employees",
    icon: <GroupOutlinedIcon />,
    check: (u) => u?.can_view_employees || u?.can_update_employees || u?.can_create_employees,
  },
  {
    label: "سایت‌ها",
    path: "/sites",
    icon: <ApartmentOutlinedIcon />,
    check: (u) => u?.can_view_sites,
  },
  {
    label: "همگام‌سازی دیتابیس",
    path: "/sync",
    icon: <SyncOutlinedIcon />,
    check: (u) => u?.can_manage_sync || u?.can_view_sync || u?.can_run_sync,
  },
  { label: "اطلاعیه‌ها", path: "/notices", icon: <CampaignOutlinedIcon /> },
  {
    label: "ثبت ورود و خروج",
    path: "/attendance-clock",
    icon: <FingerprintOutlinedIcon />,
    check: (u) => u?.can_clock_in_out,
    hiddenForAdmin: true,
  },
  {
    label: "گزارش اطلاعیه‌ها",
    path: "/notice-reports",
    icon: <AssessmentOutlinedIcon />,
    check: (u) => u?.can_view_site_notice_report,
  },
  {
    label: "انتقادات و پیشنهادات",
    path: "/feedback-report",
    icon: <ForumOutlinedIcon />,
    check: (u) => u?.can_view_feedback,
  },
  {
    label: "مدیریت دسترسی",
    path: "/access",
    icon: <AdminPanelSettingsOutlinedIcon />,
    ownPageCheck: (u) => u?.can_manage_users,
    children: [
      { label: "واحدهای سازمانی", path: "/departments", icon: <CorporateFareOutlinedIcon />, check: (u) => u?.can_manage_sites },
      { label: "رنج‌های IP مجاز", path: "/ip-allowlist", icon: <VpnLockOutlinedIcon />, check: (u) => u?.can_manage_ip_allowlist },
      {
        label: "انتصاب دسته‌جمعی نقش",
        path: "/bulk-role-assignment",
        icon: <GroupAddOutlinedIcon />,
        check: (u) => u?.can_manage_users,
      },
      { label: "مدیریت نقش/مجوز", path: "/role-management", icon: <LockOutlinedIcon />, check: (u) => u?.can_manage_roles },
      {
        label: "تنظیمات سامانه",
        path: "/system-settings",
        icon: <SettingsOutlinedIcon />,
        check: (u) => u?.can_manage_system_settings,
      },
    ],
  },
  {
    label: "پشتیبان‌گیری",
    path: "/backup",
    icon: <CloudDownloadOutlinedIcon />,
    check: (u) => u?.can_manage_backup || u?.can_bust_cache,
  },
  {
    label: "ارزیابی عملکرد",
    path: "/performance/structure",
    icon: <RateReviewOutlinedIcon />,
    ownPageCheck: (u) => u?.can_manage_performance_structure,
    children: [
      {
        label: "ساختار ارزیابی",
        path: "/performance/structure",
        icon: <AccountTreeOutlinedIcon />,
        check: (u) => u?.can_manage_performance_structure,
      },
      {
        label: "دوره‌های ارزیابی",
        path: "/performance/periods",
        icon: <EventOutlinedIcon />,
        check: (u) => u?.can_manage_performance_periods,
      },
      {
        label: "فرم‌های ارزیابی",
        path: "/performance/forms",
        icon: <AssignmentOutlinedIcon />,
        check: (u) => u?.can_manage_performance_forms,
      },
    ],
  },
  { label: "بررسی و اعمال آپدیت", path: "/update", icon: <SystemUpdateAltOutlinedIcon />, adminOnly: true },
  {
    label: "پرسنل آنلاین",
    path: "/presence-report",
    icon: <ScienceOutlinedIcon />,
    check: (u) => u?.can_view_attendance_logs,
  },
  {
    label: "گزارش ورود و خروج",
    path: "/clock-in-out-report",
    icon: <FingerprintOutlinedIcon />,
    check: (u) => u?.can_view_clock_records,
  },
  {
    label: "پیام‌های تبریک تولد",
    path: "/birthday-messages",
    icon: <CakeOutlinedIcon />,
    check: (u) => u?.can_manage_birthday_messages,
  },
  {
    label: "خودروهای پرسنل",
    path: "/vehicle-report",
    icon: <DirectionsCarFilledOutlinedIcon />,
    check: (u) => u?.can_view_vehicles_report,
  },
];

/** آیا این آیتم (صرف‌نظر از فرزندانش) برای این کاربر مجاز است؟ */
export function isItemVisible(item, user) {
  if (item.adminOnly && !user?.is_superuser) return false;
  if (item.hiddenForAdmin && user?.is_superuser) return false;
  if (item.check) return Boolean(item.check(user));
  if (item.children?.length) return item.children.some((child) => isItemVisible(child, user));
  return true;
}
