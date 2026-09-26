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
import HealthAndSafetyOutlinedIcon from "@mui/icons-material/HealthAndSafetyOutlined";
import InsightsOutlinedIcon from "@mui/icons-material/InsightsOutlined";
import WifiTetheringOutlinedIcon from "@mui/icons-material/WifiTetheringOutlined";
import PersonOutlineIcon from "@mui/icons-material/PersonOutline";
import EventNoteOutlinedIcon from "@mui/icons-material/EventNoteOutlined";
import SupervisorAccountOutlinedIcon from "@mui/icons-material/SupervisorAccountOutlined";
import DnsOutlinedIcon from "@mui/icons-material/DnsOutlined";
import AssessmentOutlinedIcon from "@mui/icons-material/AssessmentOutlined";
import ForumOutlinedIcon from "@mui/icons-material/ForumOutlined";

/**
 * منبع واحد همه‌ی مقصدهای منوی برنامه.
 * Layout.jsx (منوی کناری/نوار پایین Admin) و ProfilePage.jsx («دسترسی‌های ویژه» کاربران غیر Admin)
 * هر دو از همین آرایه می‌خوانند؛ ProfilePage.jsx آیتم‌های دارای children را مسطح (Flatten) می‌کند
 * چون آن‌جا زیرمنو وجود ندارد. هر مقصد جدید فقط یک‌بار همین‌جا اضافه می‌شود.
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
 *   groupOnly (اختیاری، فقط برای آیتم‌های دارای children): عنوان گروه صفحه
 *     مستقل ندارد؛ در Layout.jsx کلیک روی آن همیشه به اولین زیرمنوی
 *     در‌دسترس همین کاربر می‌رود (مسیر path فقط کلید باز/بسته‌بودن گروه است).
 *   children (اختیاری): آرایه‌ای از همین شکل (بدون children تودرتوی بیشتر)
 */
export const NAV_ITEMS = [
  // ترتیب گروه‌ها از کارهای روزمره (پرسنل، تردد، اطلاعیه) به سمت کارهای فنی و کم‌تکرار (دسترسی، سامانه)؛
  // داخل هر گروه پرکاربردترین اول و تنظیمات آخر. گروه‌ها (groupOnly) صفحه‌ی مستقل ندارند و
  // کلیک روی عنوان گروه به اولین زیرمنوی در‌دسترس کاربر می‌رود.
  // داشبورد مدیریتی (فقط ادمین اصلی)
  { label: "داشبورد", path: "/", icon: <DashboardOutlinedIcon />, adminOnly: true },
  // گروه پرسنل و سازمان: فهرست پرسنل، واحدها، خودروها و بیمه‌ی تکمیلی
  {
    label: "پرسنل و سازمان",
    path: "/employees",
    icon: <GroupOutlinedIcon />,
    groupOnly: true,
    children: [
      {
        label: "پرسنل",
        path: "/employees",
        icon: <PersonOutlineIcon />,
        check: (u) => u?.can_view_employees || u?.can_update_employees || u?.can_create_employees,
      },
      { label: "واحدهای سازمانی", path: "/departments", icon: <CorporateFareOutlinedIcon />, check: (u) => u?.can_manage_sites },
      {
        label: "خودروهای پرسنل",
        path: "/vehicle-report",
        icon: <DirectionsCarFilledOutlinedIcon />,
        check: (u) => u?.can_view_vehicles_report,
      },
      {
        label: "بیمه تکمیلی",
        path: "/insurance/admin",
        icon: <HealthAndSafetyOutlinedIcon />,
        check: (u) => u?.can_view_insurance,
      },
      {
        label: "گزارش جذب و ترک کار",
        path: "/reports/turnover",
        icon: <InsightsOutlinedIcon />,
        check: (u) => u?.can_view_turnover_report || u?.can_manage_turnover_categories,
      },
    ],
  },
  // گروه حضور و غیاب: گزارش تردد، پرسنل آنلاین، ثبت ورود/خروج و مرخصی/ماموریت
  {
    label: "حضور و غیاب",
    path: "/clock-in-out-report",
    icon: <FingerprintOutlinedIcon />,
    groupOnly: true,
    children: [
      {
        label: "گزارش ورود و خروج",
        path: "/clock-in-out-report",
        icon: <FingerprintOutlinedIcon />,
        check: (u) => u?.can_view_clock_records,
      },
      {
        label: "پرسنل آنلاین",
        path: "/presence-report",
        icon: <WifiTetheringOutlinedIcon />,
        check: (u) => u?.can_view_attendance_logs,
      },
      {
        label: "ثبت ورود و خروج",
        path: "/attendance-clock",
        icon: <FingerprintOutlinedIcon />,
        check: (u) => u?.can_clock_in_out, // فقط کاربران دارای مجوز ثبت تردد؛ برای ادمین اصلی مخفی است
        hiddenForAdmin: true,
      },
      {
        label: "درخواست‌های مرخصی/ماموریت",
        path: "/leave-requests/all",
        icon: <EventNoteOutlinedIcon />,
        check: (u) => u?.can_view_leave_requests || u?.can_manage_leave_requests,
      },
      {
        label: "تنظیمات مرخصی/ماموریت",
        path: "/leave-requests/settings",
        icon: <SettingsOutlinedIcon />,
        check: (u) => u?.can_manage_sites,
      },
    ],
  },
  // گروه ارتباطات: اطلاعیه‌ها و گزارش آن‌ها، انتقادات و پیشنهادات، پیام‌های تبریک تولد
  {
    label: "ارتباطات",
    path: "/notices",
    icon: <CampaignOutlinedIcon />,
    groupOnly: true,
    children: [
      { label: "اطلاعیه‌ها", path: "/notices", icon: <CampaignOutlinedIcon /> },
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
        label: "پیام‌های تبریک تولد",
        path: "/birthday-messages",
        icon: <CakeOutlinedIcon />,
        check: (u) => u?.can_manage_birthday_messages,
      },
    ],
  },
  // گروه ارزیابی عملکرد: ساختار، فرم‌ها، دوره‌ها و گزارش‌های مدیریتی
  {
    label: "ارزیابی عملکرد",
    path: "/performance/structure",
    icon: <RateReviewOutlinedIcon />,
    groupOnly: true,
    children: [
      {
        label: "ساختار ارزیابی",
        path: "/performance/structure",
        icon: <AccountTreeOutlinedIcon />,
        check: (u) => u?.can_manage_performance_structure,
      },
      {
        label: "فرم‌های ارزیابی",
        path: "/performance/forms",
        icon: <AssignmentOutlinedIcon />,
        check: (u) => u?.can_manage_performance_forms,
      },
      {
        label: "دوره‌های ارزیابی",
        path: "/performance/periods",
        icon: <EventOutlinedIcon />,
        check: (u) => u?.can_manage_performance_periods,
      },
      {
        label: "گزارش‌های مدیریتی",
        path: "/performance/reports",
        icon: <AssessmentOutlinedIcon />,
        check: (u) => u?.can_view_performance_reports,
      },
    ],
  },
  // گروه کاربران و دسترسی: کاربران، نقش/مجوز، انتصاب گروهی و رنج‌های IP مجاز
  {
    label: "کاربران و دسترسی",
    path: "/access",
    icon: <AdminPanelSettingsOutlinedIcon />,
    groupOnly: true,
    children: [
      {
        label: "کاربران و دسترسی‌ها",
        path: "/access",
        icon: <SupervisorAccountOutlinedIcon />,
        check: (u) => u?.can_manage_users,
      },
      { label: "مدیریت نقش/مجوز", path: "/role-management", icon: <LockOutlinedIcon />, check: (u) => u?.can_manage_roles },
      {
        label: "انتصاب دسته‌جمعی نقش",
        path: "/bulk-role-assignment",
        icon: <GroupAddOutlinedIcon />,
        check: (u) => u?.can_manage_users,
      },
      { label: "رنج‌های IP مجاز", path: "/ip-allowlist", icon: <VpnLockOutlinedIcon />, check: (u) => u?.can_manage_ip_allowlist },
    ],
  },
  // گروه سامانه: سایت‌ها، همگام‌سازی، تنظیمات، پشتیبان‌گیری و به‌روزرسانی
  {
    label: "سامانه",
    path: "/sites",
    icon: <DnsOutlinedIcon />,
    groupOnly: true,
    children: [
      { label: "سایت‌ها", path: "/sites", icon: <ApartmentOutlinedIcon />, check: (u) => u?.can_view_sites },
      {
        label: "همگام‌سازی دیتابیس",
        path: "/sync",
        icon: <SyncOutlinedIcon />,
        check: (u) => u?.can_manage_sync || u?.can_view_sync || u?.can_run_sync,
      },
      {
        label: "تنظیمات سامانه",
        path: "/system-settings",
        icon: <SettingsOutlinedIcon />,
        check: (u) => u?.can_manage_system_settings,
      },
      {
        label: "پشتیبان‌گیری",
        path: "/backup",
        icon: <CloudDownloadOutlinedIcon />,
        check: (u) => u?.can_manage_backup || u?.can_bust_cache,
      },
      { label: "بررسی و اعمال آپدیت", path: "/update", icon: <SystemUpdateAltOutlinedIcon />, adminOnly: true },
    ],
  },
];

/**
 * بررسی نمایش یک آیتم منو برای کاربر. ورودی: آیتم و کاربر جاری؛ خروجی: boolean.
 * ابتدا adminOnly/hiddenForAdmin، سپس check آیتم؛ اگر check نداشت ولی فرزند داشت،
 * نمایش داده می‌شود اگر حداقل یکی از فرزندان قابل مشاهده باشد.
 */
export function isItemVisible(item, user) {
  if (item.adminOnly && !user?.is_superuser) return false;
  if (item.hiddenForAdmin && user?.is_superuser) return false;
  if (item.check) return Boolean(item.check(user));
  if (item.children?.length) return item.children.some((child) => isItemVisible(child, user));
  return true;
}
