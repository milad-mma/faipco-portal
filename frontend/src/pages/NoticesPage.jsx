/**
 * صفحه اطلاعیه‌های پرسنل با سه تب: «دریافتی»، «ارسالی» (فقط برای دارندگان مجوز ارسال) و «آرشیو».
 * هر اطلاعیه یک کارت بازشونده است (علامت‌گذاری خوانده‌شده، دانلود فیش حقوقی/کارکرد، آرشیو).
 * با ?type=payroll یا ?type=attendance_card نمای اختصاصی «فقط فیش‌های من» بدون تب نمایش داده می‌شود.
 * با رسیدن Push جدید از Service Worker، فهرست بدون Reload صفحه تازه می‌شود.
 */
import { useEffect, useState } from "react";
import { Link as RouterLink, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import BackLink from "../components/BackLink";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Collapse,
  Pagination,
  Stack,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import AccessGateDialog from "../components/AccessGateDialog";
import MailOutlineIcon from "@mui/icons-material/MailOutline";
import DraftsOutlinedIcon from "@mui/icons-material/DraftsOutlined";
import PictureAsPdfOutlinedIcon from "@mui/icons-material/PictureAsPdfOutlined";
import InboxOutlinedIcon from "@mui/icons-material/InboxOutlined";
import SendOutlinedIcon from "@mui/icons-material/SendOutlined";
import ArchiveOutlinedIcon from "@mui/icons-material/ArchiveOutlined";
import UnarchiveOutlinedIcon from "@mui/icons-material/UnarchiveOutlined";
import {
  archiveNotice,
  fetchAvailableTargets,
  fetchMyAttendanceCardBlob,
  fetchMyNotices,
  fetchMyPayrollReceiptBlob,
  fetchSentByMe,
  markNoticeRead,
  unarchiveNotice,
} from "../api/notices";
import NoticeReportTable from "../components/NoticeReportTable";

// برچسب و رنگ نشان اولویت هر اطلاعیه
const PRIORITY_LABELS = {
  // کم = خاکستری خنثی، عادی = رنگ Secondary پروژه، بالا = قرمز کم‌رنگ، فوری = قرمز کامل
  // (بالا و فوری رنگ متفاوت دارند تا از هم قابل تشخیص باشند)
  low: { label: "کم", bg: "action.selected", color: "text.secondary" },
  normal: { label: "عادی", bg: "secondary.main", color: "secondary.contrastText" },
  high: { label: "بالا", bg: "error.light", color: "common.white" },
  urgent: { label: "فوری", bg: "error.main", color: "error.contrastText" },
};

// عنوان صفحه و برچسب Chip برای اطلاعیه‌های نوع فیش حقوقی/کارکرد
const NOTICE_TYPE_META = {
  payroll: { label: "فیش‌های حقوقی من", chipLabel: "فیش حقوقی", chipColor: "secondary" },
  attendance_card: { label: "فیش‌های کارکرد من", chipLabel: "فیش کارکرد", chipColor: "info" },
};

// تعریف تب‌های صفحه
const TABS = [
  { key: "received", label: "دریافتی", icon: <InboxOutlinedIcon fontSize="small" /> },
  { key: "sent", label: "ارسالی", icon: <SendOutlinedIcon fontSize="small" /> },
  { key: "archive", label: "آرشیو", icon: <ArchiveOutlinedIcon fontSize="small" /> },
];

/**
 * یک Blob را با نام فایل داده‌شده دانلود می‌کند (لینک موقت با خصیصه download).
 * این روش به‌جای window.open استفاده می‌شود چون در PWA نصب‌شده (Standalone) تب جدیدی
 * برای نمایش PDF وجود ندارد؛ فایل مستقیماً در پوشه Download دستگاه ذخیره می‌شود.
 * URL موقت پس از ۶۰ ثانیه آزاد می‌شود.
 */
function triggerBlobDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
}

// فیش حقوقی کاربر برای یک اطلاعیه را دانلود می‌کند.
// ورودی: شناسه اطلاعیه، setter پیام خطا و تابعی برای باز کردن دیالوگ پیش‌نیاز دسترسی (در پاسخ ۴۰۳)
async function downloadPayrollReceipt(noticeId, setDownloadError, onGateBlocked) {
  setDownloadError("");
  try {
    const blob = await fetchMyPayrollReceiptBlob(noticeId);
    triggerBlobDownload(blob, `فیش-حقوقی-${noticeId}.pdf`);
  } catch (err) {
    // ۴۰۳ یعنی پیش‌نیاز دسترسی انجام نشده؛ به‌جای پیام خطای عمومی، دیالوگ راهنما باز می‌شود
    if (err.response?.status === 403) {
      // پیام سرور پاس داده می‌شود؛ اگر سرور دلیلی نداد null (نه رشته خالی) فرستاده می‌شود
      // تا دیالوگ متن عمومی و بدون عدد نشان دهد
      onGateBlocked?.(err.response?.data?.detail || null);
      return;
    }
    setDownloadError(
      err.response?.status === 404
        ? "فیشی برای شما در این اطلاعیه یافت نشد."
        : "دانلود فیش با خطا مواجه شد."
    );
  }
}

// فیش کارکرد کاربر برای یک اطلاعیه را دانلود می‌کند؛ ورودی‌ها و رفتار خطا مانند downloadPayrollReceipt
async function downloadAttendanceCard(noticeId, setDownloadError, onGateBlocked) {
  setDownloadError("");
  try {
    const blob = await fetchMyAttendanceCardBlob(noticeId);
    triggerBlobDownload(blob, `فیش-کارکرد-${noticeId}.pdf`);
  } catch (err) {
    // ۴۰۳ یعنی پیش‌نیاز دسترسی انجام نشده؛ به‌جای پیام خطای عمومی، دیالوگ راهنما باز می‌شود
    if (err.response?.status === 403) {
      // پیام سرور پاس داده می‌شود؛ اگر سرور دلیلی نداد null (نه رشته خالی) فرستاده می‌شود
      // تا دیالوگ متن عمومی و بدون عدد نشان دهد
      onGateBlocked?.(err.response?.data?.detail || null);
      return;
    }
    setDownloadError(
      err.response?.status === 404
        ? "فیشی برای شما در این اطلاعیه یافت نشد."
        : "دانلود فیش با خطا مواجه شد."
    );
  }
}

// نشان گرد اولویت اطلاعیه؛ ورودی: priority (low/normal/high/urgent، پیش‌فرض normal)
function PriorityBadge({ priority }) {
  const cfg = PRIORITY_LABELS[priority] || PRIORITY_LABELS.normal;
  return (
    <Box
      sx={{
        borderRadius: 999,
        bgcolor: cfg.bg,
        color: cfg.color,
        height: 28,
        minWidth: 44,
        px: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 12,
        fontWeight: 800,
        flexShrink: 0,
      }}
    >
      {cfg.label}
    </Box>
  );
}

/**
 * کارت بازشونده یک اطلاعیه دریافتی/آرشیوشده.
 * ورودی: notice، onOpened (پس از اولین باز شدنِ اطلاعیه خوانده‌نشده)، onArchiveChange (پس از آرشیو/بازگردانی)
 * و isArchiveView. شامل متن، دکمه دانلود فیش، اطلاعات فرستنده و دکمه آرشیو است.
 */
function ReceivedNoticeCard({ notice, onOpened, onArchiveChange, isArchiveView }) {
  const [expanded, setExpanded] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const [archiveBusy, setArchiveBusy] = useState(false);  // درخواست آرشیو/بازگردانی در جریان است
  // وضعیت دیالوگ پیش‌نیاز دسترسی: پیام ۴۰۳ خود سرور نگه داشته می‌شود تا دیالوگ همان دلیل
  // و تعداد واقعی را نشان دهد. «باز بودن» از «متن پیام» جداست، چون null در gateMessage
  // یعنی «سرور متنی نداد» و دیالوگ باید در این حالت هم باز شود.
  const [gateOpen, setGateOpen] = useState(false);
  const [gateMessage, setGateMessage] = useState(null);

  // دیالوگ پیش‌نیاز دسترسی را با پیام سرور (یا null برای متن عمومی) باز می‌کند
  function openGate(message) {
    setGateMessage(message || null);
    setGateOpen(true);
  }
  const isUnread = !notice.is_read;
  const isPayroll = notice.notice_type === "payroll";
  const isAttendanceCard = notice.notice_type === "attendance_card";
  const typeMeta = NOTICE_TYPE_META[notice.notice_type];  // برای اطلاعیه‌های عادی undefined است

  // باز/بسته کردن کارت؛ اولین باز شدن اطلاعیه خوانده‌نشده آن را در سرور «خوانده‌شده» ثبت می‌کند
  function handleToggle() {
    if (!expanded && isUnread) {
      markNoticeRead(notice.id).catch(() => {});
      onOpened?.(notice.id);
    }
    setExpanded((v) => !v);
  }

  // آرشیو یا بازگردانی اطلاعیه (بسته به وضعیت فعلی) و اطلاع به والد برای تازه کردن فهرست‌ها
  async function handleArchiveToggle(e) {
    e.stopPropagation();
    setArchiveBusy(true);
    try {
      if (notice.is_archived) {
        await unarchiveNotice(notice.id);
      } else {
        await archiveNotice(notice.id);
      }
      onArchiveChange?.(notice.id);
    } finally {
      setArchiveBusy(false);
    }
  }

  return (
    <Card variant="outlined" sx={{ borderRadius: 2, overflow: "hidden" }}>
      <Box
        onClick={handleToggle}
        sx={{
          minHeight: 70,
          p: 1.5,
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 1.25,
          cursor: "pointer",
          "&:hover": { backgroundColor: "action.hover" },
        }}
      >
        {/* سمت راست: آیکون پاکت (باز/بسته بسته به خوانده شدن)، سپس عنوان و زیرش تاریخ/ساعت */}
        <Stack direction="row" spacing={1.25} sx={{ minWidth: 0, flex: 1 }}>
          <Box
            sx={{
              width: 42,
              height: 42,
              borderRadius: "50%",
              bgcolor: isUnread ? "secondary.main" : "action.hover",
              color: isUnread ? "secondary.contrastText" : "text.disabled",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {isUnread ? <MailOutlineIcon fontSize="small" /> : <DraftsOutlinedIcon fontSize="small" />}
          </Box>
          {/* flex:1 لازم است تا این Box کل عرض باقی‌مانده را بگیرد و تاریخ زیر عنوان
              فضای کافی برای راست‌چین شدن داشته باشد (نه فقط به اندازه عرض عنوان). */}
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography
              fontSize={14}
              fontWeight={isUnread ? 800 : 500}
              color={isUnread ? "text.primary" : "text.secondary"}
              sx={{
                lineHeight: 1.7,
                wordBreak: "break-word",
                minWidth: 0,
              }}
            >
              {notice.title}
            </Typography>
            {/* تاریخ و ساعت — زیر عنوان، راست‌چین */}
            {/* textAlign برابر "left" است چون stylis-plugin-rtl مقادیر left/right را خودکار
                قرینه می‌کند و در خروجی نهایی به راست‌چین تبدیل می‌شود؛ همین الگو در
                BackupPage.jsx/UpdatePage.jsx هم برای محتوای LTR استفاده شده است. */}
            <Typography fontSize={10} color="text.secondary" sx={{ direction: "ltr", textAlign: "left", mt: 0.25 }}>
              {new Date(notice.created_at).toLocaleString("fa-IR")}
            </Typography>
          </Box>
        </Stack>
        {/* سمت چپ: برچسب فیش حقوقی/کارکرد، و در انتها (آخرین/دورترین) اولویت */}
        <Stack direction="row" spacing={1} alignItems="center" sx={{ flexShrink: 0 }}>
          {typeMeta && (
            <Chip
              size="small"
              label={typeMeta.chipLabel}
              color={typeMeta.chipColor}
              variant="outlined"
              sx={{ height: 18, fontSize: 10 }}
            />
          )}
          <PriorityBadge priority={notice.priority} />
        </Stack>
      </Box>
      {/* بخش بازشونده: متن، دکمه دانلود فیش، فرستنده و دکمه آرشیو */}
      <Collapse in={expanded}>
        <Box sx={{ px: 2, pb: 2 }}>
          {notice.body && (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{
                mb: isPayroll || isAttendanceCard ? 1.5 : 0,
                whiteSpace: "pre-line",
                wordBreak: "break-word",
              }}
            >
              {notice.body}
            </Typography>
          )}
          {/* دانلود فیش حقوقی (اگر برای این کاربر فیشی در اطلاعیه وجود دارد) */}
          {isPayroll && (
            <>
              {notice.has_my_payroll_receipt ? (
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<PictureAsPdfOutlinedIcon />}
                  onClick={(e) => {
                    e.stopPropagation();
                    downloadPayrollReceipt(notice.id, setDownloadError, openGate);
                  }}
                >
                  دانلود فیش من (PDF)
                </Button>
              ) : (
                <Typography variant="caption" color="text.secondary">
                  فیشی برای شما در این اطلاعیه یافت نشد.
                </Typography>
              )}
              {downloadError && (
                <Alert severity="error" sx={{ mt: 1 }}>
                  {downloadError}
                </Alert>
              )}
            </>
          )}
          {/* دانلود فیش کارکرد (اگر برای این کاربر کارتی در اطلاعیه وجود دارد) */}
          {isAttendanceCard && (
            <>
              {notice.has_my_attendance_card ? (
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<PictureAsPdfOutlinedIcon />}
                  onClick={(e) => {
                    e.stopPropagation();
                    downloadAttendanceCard(notice.id, setDownloadError, openGate);
                  }}
                >
                  دانلود فیش کارکرد من (PDF)
                </Button>
              ) : (
                <Typography variant="caption" color="text.secondary">
                  کارتی برای شما در این اطلاعیه یافت نشد.
                </Typography>
              )}
              {downloadError && (
                <Alert severity="error" sx={{ mt: 1 }}>
                  {downloadError}
                </Alert>
              )}
            </>
          )}
          <Stack
            spacing={1}
            sx={{ mt: 1.5, pt: 1.5, borderTop: "1px solid", borderColor: "divider" }}
          >
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip size="small" variant="outlined" color="info" label={`فرستنده: ${notice.sender_name}`} />
              {notice.sender_department_name && (
                <Chip
                  size="small"
                  variant="outlined"
                  color="info"
                  label={`واحد: ${notice.sender_department_name}`}
                />
              )}
            </Stack>
            {/* دکمه آرشیو در ردیف مستقل قرار دارد تا محلش به طول Chipهای بالا وابسته نباشد */}
            <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
              <Button
                size="small"
                color={isArchiveView ? "primary" : "inherit"}
                disabled={archiveBusy}
                startIcon={
                  notice.is_archived ? <UnarchiveOutlinedIcon fontSize="small" /> : <ArchiveOutlinedIcon fontSize="small" />
                }
                onClick={handleArchiveToggle}
              >
                {notice.is_archived ? "بازگرداندن از آرشیو" : "انتقال به آرشیو"}
              </Button>
            </Box>
          </Stack>
        </Box>
      </Collapse>

      {/* دیالوگ پیش‌نیاز دسترسی: وقتی سرور برای دانلود فیش ۴۰۳ می‌دهد باز می‌شود و
          راه رفع را نشان می‌دهد. */}
      <AccessGateDialog
        open={gateOpen}
        message={gateMessage}
        onClose={() => setGateOpen(false)}
      />
    </Card>
  );
}

// کامپوننت اصلی صفحه؛ تب فعال، فهرست‌های دریافتی/آرشیو و صفحه‌بندی آن‌ها را مدیریت می‌کند
export default function NoticesPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  // اگر با ?type=payroll یا ?type=attendance_card باز شود (از دکمه‌های
  // «فیش حقوقی»/«فیش کارکرد» در داشبورد شخصی)، فقط همان نوع فیلتر می‌شود
  // و تب‌های ارسالی/آرشیو مخفی می‌شوند — چون در آن حالت این یک نمای
  // اختصاصی («فقط فیش‌های من») است، نه صفحه کامل اطلاعیه‌ها.
  const typeFilter = searchParams.get("type");
  const isFilteredView = typeFilter === "payroll" || typeFilter === "attendance_card";

  const [tab, setTab] = useState("received");
  const [notices, setNotices] = useState(null);
  const [noticesTotal, setNoticesTotal] = useState(0);
  const [noticesPage, setNoticesPage] = useState(1);  // صفحه فعلی تب دریافتی (از ۱)
  const NOTICES_PAGE_SIZE = 10;
  const [sentReloadKey, setSentReloadKey] = useState(0);  // افزایش آن جدول «ارسالی» را دوباره بارگذاری می‌کند
  const [availableTargets, setAvailableTargets] = useState(null);  // مقصدها/مجوزهای ارسال اطلاعیه کاربر؛ null = هنوز لود نشده
  const [archivedNotices, setArchivedNotices] = useState(null);  // null = هنوز بارگذاری نشده (فقط با اولین ورود به تب آرشیو لود می‌شود)
  const [archivedTotal, setArchivedTotal] = useState(0);
  const [archivedPage, setArchivedPage] = useState(1);

  // یک صفحه از اطلاعیه‌های دریافتی (با فیلتر نوع در نمای اختصاصی) را بارگذاری می‌کند
  function loadNotices(page = noticesPage) {
    fetchMyNotices({ page, pageSize: NOTICES_PAGE_SIZE, noticeType: typeFilter || undefined }).then((data) => {
      setNotices(data.items);
      setNoticesTotal(data.total);
    });
  }

  // یک صفحه از اطلاعیه‌های آرشیوشده را بارگذاری می‌کند
  function loadArchived(page = archivedPage) {
    fetchMyNotices({ page, pageSize: NOTICES_PAGE_SIZE, archived: "only" }).then((data) => {
      setArchivedNotices(data.items);
      setArchivedTotal(data.total);
    });
  }

  // با تغییر فیلتر نوع: بارگذاری صفحه اول دریافتی و (در نمای کامل) مجوزهای ارسال
  useEffect(() => {
    loadNotices(1);
    setNoticesPage(1);
    if (!isFilteredView) fetchAvailableTargets().then(setAvailableTargets);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typeFilter]);

  // بارگذاری تنبل آرشیو: فقط در اولین ورود به تب آرشیو
  useEffect(() => {
    if (tab === "archive" && archivedNotices === null) loadArchived(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  // با رسیدن پیام Push جدید از Service Worker، فهرست دریافتی (و در تب ارسالی، جدول ارسالی)
  // بدون Reload صفحه دوباره خوانده می‌شود؛ صفحه‌بندی دریافتی به صفحه اول برمی‌گردد چون
  // اطلاعیه جدید همیشه بالای فهرست است.
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    function handleMessage(event) {
      if (event.data?.type === "faipco-notice-push") {
        setNoticesPage(1);
        loadNotices(1);
        if (tab === "sent") setSentReloadKey((k) => k + 1);
      }
    }
    navigator.serviceWorker.addEventListener("message", handleMessage);
    return () => navigator.serviceWorker.removeEventListener("message", handleMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  // کاربر حداقل یک نوع مجوز ارسال اطلاعیه/فیش دارد
  const canCreateAnything =
    availableTargets &&
    (availableTargets.can_target_all ||
      availableTargets.site_ids.length > 0 ||
      availableTargets.department_ids.length > 0 ||
      availableTargets.can_target_employee ||
      availableTargets.can_upload_payroll ||
      availableTargets.can_upload_attendance_card);

  // تب «ارسالی» فقط برای دارنده مجوز ارسال اطلاعیه نشان داده می‌شود؛ «دریافتی»/«آرشیو» برای همه
  const visibleTabs = TABS.filter((t) => t.key !== "sent" || canCreateAnything);

  // اگر تب «ارسالی» فعال باشد ولی کاربر مجوز ارسال نداشته باشد (مثلاً پس از بارگذاری
  // availableTargets)، به تب «دریافتی» برمی‌گردد تا روی تب مخفی نماند.
  useEffect(() => {
    if (tab === "sent" && availableTargets && !canCreateAnything) {
      setTab("received");
    }
  }, [tab, availableTargets, canCreateAnything]);

  // اطلاعیه را در فهرست محلی «خوانده‌شده» علامت می‌زند
  function handleMarkedRead(noticeId) {
    setNotices((prev) => prev.map((n) => (n.id === noticeId ? { ...n, is_read: true } : n)));
  }

  // بعد از آرشیو/بازگرداندن یک اطلاعیه، آن اطلاعیه از یک فهرست به فهرست دیگر منتقل می‌شود؛
  // به‌جای تغییر محلی state، هر دو فهرست «دریافتی» و «آرشیو» از سرور دوباره خوانده می‌شوند
  // (ابتدا فهرست تب فعال) تا با جابه‌جایی بین تب‌ها هر دو به‌روز باشند.
  function handleArchiveChange() {
    if (tab === "archive") {
      loadArchived(archivedPage);
      loadNotices(noticesPage);
    } else {
      loadNotices(noticesPage);
      loadArchived(archivedPage);
    }
  }

  const pageTitle = isFilteredView ? NOTICE_TYPE_META[typeFilter].label : "اطلاعیه‌ها";  // در نمای اختصاصی، عنوان نوع فیش

  return (
    <Box sx={{ maxWidth: { xs: "100%", md: 1100 }, mx: "auto" }}>
      {!user?.is_superuser && <BackLink to="/my-dashboard" />}
      {/* عنوان صفحه و دکمه «اطلاعیه جدید» (برای دارندگان مجوز ارسال) */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, flexWrap: "wrap", gap: 2 }}>
        <Typography variant="h5" fontWeight={800}>
          {pageTitle}
        </Typography>
        {canCreateAnything && !isFilteredView && (
          <Button
            variant="contained"
            startIcon={<AddOutlinedIcon />}
            component={RouterLink}
            to="/notices/new"
            sx={{ borderRadius: 999 }}
          >
            اطلاعیه جدید
          </Button>
        )}
      </Box>

      {/* نوار تب‌ها؛ در نمای فیلترشده (فیش حقوقی/کارکرد از داشبورد) نمایش داده نمی‌شود.
          «دریافتی» و «آرشیو» به canCreateAnything وابسته نیستند چون هر کاربر لاگین‌شده
          اطلاعیه دریافت و آرشیو می‌کند؛ «ارسالی» فقط برای دارنده مجوز ارسال نمایش داده می‌شود. */}
      {!isFilteredView && (
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: `repeat(${visibleTabs.length}, 1fr)`,
            bgcolor: "action.hover",
            borderRadius: 999,
            p: 0.5,
            mb: 3,
            gap: 0.5,
          }}
        >
          {visibleTabs.map((t) => (
            <Box
              key={t.key}
              onClick={() => setTab(t.key)}
              sx={{
                height: 34,
                borderRadius: 999,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 0.75,
                cursor: "pointer",
                fontSize: 12,
                fontWeight: 700,
                color: tab === t.key ? "primary.main" : "text.secondary",
                bgcolor: tab === t.key ? "background.paper" : "transparent",
                boxShadow: tab === t.key ? 1 : "none",
              }}
            >
              {t.icon}
              {t.label}
            </Box>
          ))}
        </Box>
      )}

      {/* تب دریافتی (یا نمای اختصاصی فیش‌ها): کارت‌های اطلاعیه و صفحه‌بندی */}
      {(isFilteredView || tab === "received") && (
        <Stack spacing={1.5}>
          {notices === null ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              {notices.length === 0 && (
                <Card variant="outlined" sx={{ p: 4, borderRadius: 2, textAlign: "center" }}>
                  <Typography variant="body2" color="text.secondary">
                    {isFilteredView
                      ? "اطلاعیه‌ای از این نوع برای شما ثبت نشده است."
                      : "در حال حاضر اطلاعیه‌ای برای شما ثبت نشده است."}
                  </Typography>
                </Card>
              )}
              {notices.map((notice) => (
                <ReceivedNoticeCard
                  key={notice.id}
                  notice={notice}
                  onOpened={handleMarkedRead}
                  onArchiveChange={handleArchiveChange}
                />
              ))}
            </>
          )}
          {notices !== null && noticesTotal > NOTICES_PAGE_SIZE && (
            <Stack alignItems="center" sx={{ pt: 1.5 }}>
              <Pagination
                count={Math.ceil(noticesTotal / NOTICES_PAGE_SIZE)}
                page={noticesPage}
                onChange={(_, value) => {
                  setNoticesPage(value);
                  loadNotices(value);
                }}
                color="primary"
              />
            </Stack>
          )}
        </Stack>
      )}

      {/* تب ارسالی: جدول اطلاعیه‌های ارسالی کاربر با امکان حذف */}
      {!isFilteredView && tab === "sent" && (
        <Card variant="outlined" sx={{ borderRadius: 2, p: 1 }}>
          <NoticeReportTable
            fetchPage={fetchSentByMe}
            showSender={false}
            allowDelete
            reloadKey={sentReloadKey}
          />
        </Card>
      )}

      {/* تب آرشیو: کارت‌های اطلاعیه آرشیوشده و صفحه‌بندی */}
      {!isFilteredView && tab === "archive" && (
        <Stack spacing={1.5}>
          {archivedNotices === null ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              {archivedNotices.length === 0 && (
                <Card variant="outlined" sx={{ p: 4, borderRadius: 2, textAlign: "center" }}>
                  <ArchiveOutlinedIcon sx={{ fontSize: 32, color: "text.disabled", mb: 1 }} />
                  <Typography variant="body2" color="text.secondary">
                    آرشیو اطلاعیه‌ها خالی است.
                  </Typography>
                </Card>
              )}
              {archivedNotices.map((notice) => (
                <ReceivedNoticeCard
                  key={notice.id}
                  notice={notice}
                  onOpened={() => {}}
                  onArchiveChange={handleArchiveChange}
                  isArchiveView
                />
              ))}
            </>
          )}
          {archivedNotices !== null && archivedTotal > NOTICES_PAGE_SIZE && (
            <Stack alignItems="center" sx={{ pt: 1.5 }}>
              <Pagination
                count={Math.ceil(archivedTotal / NOTICES_PAGE_SIZE)}
                page={archivedPage}
                onChange={(_, value) => {
                  setArchivedPage(value);
                  loadArchived(value);
                }}
                color="primary"
              />
            </Stack>
          )}
        </Stack>
      )}
    </Box>
  );
}
