import { useEffect, useState } from "react";
import { Link as RouterLink, useSearchParams } from "react-router-dom";
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

const PRIORITY_LABELS = {
  // رنگ‌بندی دقیقاً طبق personnel_portal.html: «عادی»=Teal/Secondary این
  // پروژه، «بالا»=قرمز (Danger) — «کم» و «فوری» در نمونه HTML تعریف
  // نشده بودند (فقط ۲ نمونه داشت)، پس با همان منطق تعمیم داده شدند: کم →
  // خاکستری خنثی، فوری → همان قرمز «بالا» (هردو یعنی نیاز به توجه فوری).
  low: { label: "کم", bg: "action.selected", color: "text.secondary" },
  normal: { label: "عادی", bg: "secondary.main", color: "secondary.contrastText" },
  high: { label: "بالا", bg: "error.main", color: "error.contrastText" },
  urgent: { label: "فوری", bg: "error.main", color: "error.contrastText" },
};

const NOTICE_TYPE_META = {
  payroll: { label: "فیش‌های حقوقی من", chipLabel: "فیش حقوقی", chipColor: "secondary" },
  attendance_card: { label: "فیش‌های کارکرد من", chipLabel: "فیش کارکرد", chipColor: "info" },
};

const TABS = [
  { key: "received", label: "دریافتی", icon: <InboxOutlinedIcon fontSize="small" /> },
  { key: "sent", label: "ارسالی", icon: <SendOutlinedIcon fontSize="small" /> },
  { key: "archive", label: "آرشیو", icon: <ArchiveOutlinedIcon fontSize="small" /> },
];

async function downloadPayrollReceipt(noticeId, setDownloadError) {
  setDownloadError("");
  try {
    const blob = await fetchMyPayrollReceiptBlob(noticeId);
    const url = window.URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
  } catch (err) {
    setDownloadError(
      err.response?.status === 404
        ? "فیشی برای شما در این اطلاعیه یافت نشد."
        : "دانلود فیش ناموفق بود."
    );
  }
}

async function downloadAttendanceCard(noticeId, setDownloadError) {
  setDownloadError("");
  try {
    const blob = await fetchMyAttendanceCardBlob(noticeId);
    const url = window.URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
  } catch (err) {
    setDownloadError(
      err.response?.status === 404
        ? "کارتی برای شما در این اطلاعیه یافت نشد."
        : "دانلود کارت ناموفق بود."
    );
  }
}

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

function ReceivedNoticeCard({ notice, onOpened, onArchiveChange, isArchiveView }) {
  const [expanded, setExpanded] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const [archiveBusy, setArchiveBusy] = useState(false);
  const isUnread = !notice.is_read;
  const isPayroll = notice.notice_type === "payroll";
  const isAttendanceCard = notice.notice_type === "attendance_card";
  const typeMeta = NOTICE_TYPE_META[notice.notice_type];

  function handleToggle() {
    if (!expanded && isUnread) {
      markNoticeRead(notice.id).catch(() => {});
      onOpened?.(notice.id);
    }
    setExpanded((v) => !v);
  }

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
          display: "grid",
          // آیکون پاکت راست (اول)، عنوان وسط، نشان اولویت + برچسب نوع چپ (آخر)
          gridTemplateColumns: "46px 1fr auto",
          alignItems: "center",
          gap: 1.25,
          cursor: "pointer",
          "&:hover": { backgroundColor: "action.hover" },
        }}
      >
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
        <Box sx={{ minWidth: 0 }}>
          <Typography
            fontSize={14}
            fontWeight={isUnread ? 800 : 500}
            color={isUnread ? "text.primary" : "text.secondary"}
            sx={{
              lineHeight: 1.7,
              // قبلاً یک‌خطی با ... بریده می‌شد — حالا کامل نمایش داده می‌شود
              wordBreak: "break-word",
              minWidth: 0,
            }}
          >
            {notice.title}
          </Typography>
          <Typography fontSize={10} color="text.secondary" sx={{ direction: "ltr", textAlign: "right", mt: 0.25 }}>
            {new Date(notice.created_at).toLocaleString("fa-IR")}
          </Typography>
        </Box>
        {/* طبق درخواست: برچسب فیش حقوقی/کارکرد کنار نشان اولویت — نه کنار
            عنوان — همیشه دیده می‌شود، نه فقط وقتی کارت باز است */}
        <Stack spacing={0.5} alignItems="flex-end">
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
          {isPayroll && (
            <>
              {notice.has_my_payroll_receipt ? (
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<PictureAsPdfOutlinedIcon />}
                  onClick={(e) => {
                    e.stopPropagation();
                    downloadPayrollReceipt(notice.id, setDownloadError);
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
          {isAttendanceCard && (
            <>
              {notice.has_my_attendance_card ? (
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<PictureAsPdfOutlinedIcon />}
                  onClick={(e) => {
                    e.stopPropagation();
                    downloadAttendanceCard(notice.id, setDownloadError);
                  }}
                >
                  دانلود کارت کارکرد من (PDF)
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
            direction="row"
            spacing={1}
            flexWrap="wrap"
            useFlexGap
            alignItems="center"
            justifyContent="space-between"
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
            <Button
              size="small"
              color={isArchiveView ? "primary" : "inherit"}
              disabled={archiveBusy}
              startIcon={
                notice.is_archived ? <UnarchiveOutlinedIcon fontSize="small" /> : <ArchiveOutlinedIcon fontSize="small" />
              }
              onClick={handleArchiveToggle}
            >
              {notice.is_archived ? "بازگرداندن از آرشیو" : "آرشیو کردن"}
            </Button>
          </Stack>
        </Box>
      </Collapse>
    </Card>
  );
}

export default function NoticesPage() {
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
  const [noticesPage, setNoticesPage] = useState(1);
  const NOTICES_PAGE_SIZE = 10;
  const [sentReloadKey, setSentReloadKey] = useState(0);
  const [availableTargets, setAvailableTargets] = useState(null);
  const [archivedNotices, setArchivedNotices] = useState(null);
  const [archivedTotal, setArchivedTotal] = useState(0);
  const [archivedPage, setArchivedPage] = useState(1);

  function loadNotices(page = noticesPage) {
    fetchMyNotices({ page, pageSize: NOTICES_PAGE_SIZE, noticeType: typeFilter || undefined }).then((data) => {
      setNotices(data.items);
      setNoticesTotal(data.total);
    });
  }

  function loadArchived(page = archivedPage) {
    fetchMyNotices({ page, pageSize: NOTICES_PAGE_SIZE, archived: true }).then((data) => {
      setArchivedNotices(data.items);
      setArchivedTotal(data.total);
    });
  }

  useEffect(() => {
    loadNotices(1);
    setNoticesPage(1);
    if (!isFilteredView) fetchAvailableTargets().then(setAvailableTargets);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typeFilter]);

  useEffect(() => {
    if (tab === "archive" && archivedNotices === null) loadArchived(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  // پیام از Service Worker وقتی یک Push جدید می‌رسد — لیست را بدون Reload
  // صفحه، دوباره از سرور می‌خوانیم (چه در تب دریافتی، چه ارسالی من). چون
  // اطلاعیه جدید همیشه بالای لیست می‌آید، صفحه‌بندی «دریافتی» را هم به
  // صفحه اول برمی‌گردانیم تا همان‌جا دیده شود.
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

  const canCreateAnything =
    availableTargets &&
    (availableTargets.can_target_all ||
      availableTargets.site_ids.length > 0 ||
      availableTargets.department_ids.length > 0 ||
      availableTargets.can_target_employee ||
      availableTargets.can_upload_payroll ||
      availableTargets.can_upload_attendance_card);

  function handleMarkedRead(noticeId) {
    setNotices((prev) => prev.map((n) => (n.id === noticeId ? { ...n, is_read: true } : n)));
  }

  // بعد از آرشیو/بازگرداندن یک اطلاعیه، آن اطلاعیه دیگر در لیست فعلی جایی
  // ندارد (چه در «دریافتی» چه در «آرشیو» — چون فیلتر مقابل شد) — پس فقط
  // همان لیست را دوباره می‌خوانیم، به‌جای این‌که سعی کنیم وضعیت را محلی
  // Patch کنیم (که پیچیده و مستعد خطا می‌شد).
  function handleArchiveChange() {
    if (tab === "archive") {
      loadArchived(archivedPage);
    } else {
      loadNotices(noticesPage);
    }
  }

  const pageTitle = isFilteredView ? NOTICE_TYPE_META[typeFilter].label : "اطلاعیه‌ها";

  return (
    <Box>
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

      {/* در نمای فیلترشده (فیش حقوقی/کارکرد از داشبورد) اصلاً تب نشان داده
          نمی‌شود — این یک نمای تک‌منظوره است، نه صفحه کامل اطلاعیه‌ها.
          ⚠️ عمداً به canCreateAnything وابسته نیست: هر کاربر لاگین‌شده‌ای،
          حتی بدون هیچ مجوز ارسالی، اطلاعیه دریافت می‌کند و باید بتواند
          آرشیوشان کند — این تب‌ها (از جمله «آرشیو») باید همیشه دیده شوند،
          نه فقط برای کسانی که اجازه ارسال دارند (که قبلاً یک باگ واقعی بود:
          پرسنل بدون نقش خاص، اصلاً هیچ‌کدام از تب‌ها را نمی‌دید). */}
      {!isFilteredView && (
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            bgcolor: "action.hover",
            borderRadius: 999,
            p: 0.5,
            mb: 3,
            gap: 0.5,
          }}
        >
          {TABS.map((t) => (
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
