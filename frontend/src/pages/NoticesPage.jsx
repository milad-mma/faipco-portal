import { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
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
import {
  fetchAvailableTargets,
  fetchMyAttendanceCardBlob,
  fetchMyNotices,
  fetchMyPayrollReceiptBlob,
  fetchSentByMe,
  markNoticeRead,
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

function ReceivedNoticeCard({ notice, onOpened }) {
  const [expanded, setExpanded] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const isUnread = !notice.is_read;
  const isPayroll = notice.notice_type === "payroll";
  const isAttendanceCard = notice.notice_type === "attendance_card";

  function handleToggle() {
    if (!expanded && isUnread) {
      markNoticeRead(notice.id).catch(() => {});
      onOpened?.(notice.id);
    }
    setExpanded((v) => !v);
  }

  return (
    <Card variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
      <Box
        onClick={handleToggle}
        sx={{
          minHeight: 70,
          p: 1.5,
          display: "grid",
          gridTemplateColumns: "44px 1fr 46px",
          alignItems: "center",
          gap: 1.25,
          cursor: "pointer",
          "&:hover": { backgroundColor: "action.hover" },
        }}
      >
        <PriorityBadge priority={notice.priority} />
        <Box sx={{ minWidth: 0 }}>
          <Typography
            fontSize={14}
            fontWeight={isUnread ? 800 : 500}
            color={isUnread ? "text.primary" : "text.secondary"}
            sx={{
              lineHeight: 1.7,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {notice.title}
          </Typography>
          <Typography fontSize={10} color="text.secondary" sx={{ direction: "ltr", textAlign: "right", mt: 0.25 }}>
            {new Date(notice.created_at).toLocaleString("fa-IR")}
          </Typography>
        </Box>
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
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ px: 2, pb: 2 }}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 1.5 }}>
            {isPayroll && <Chip size="small" label="فیش حقوقی" color="secondary" variant="outlined" />}
            {isAttendanceCard && <Chip size="small" label="فیش کارکرد" color="info" variant="outlined" />}
          </Stack>
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
            sx={{ mt: 1.5, pt: 1.5, borderTop: "1px solid", borderColor: "divider" }}
          >
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
        </Box>
      </Collapse>
    </Card>
  );
}

export default function NoticesPage() {
  const [tab, setTab] = useState("received");
  const [notices, setNotices] = useState(null);
  const [noticesTotal, setNoticesTotal] = useState(0);
  const [noticesPage, setNoticesPage] = useState(1);
  const NOTICES_PAGE_SIZE = 10;
  const [sentReloadKey, setSentReloadKey] = useState(0);
  const [availableTargets, setAvailableTargets] = useState(null);

  function loadNotices(page = noticesPage) {
    fetchMyNotices({ page, pageSize: NOTICES_PAGE_SIZE }).then((data) => {
      setNotices(data.items);
      setNoticesTotal(data.total);
    });
  }

  useEffect(() => {
    loadNotices(1);
    setNoticesPage(1);
    fetchAvailableTargets().then(setAvailableTargets);
  }, []);

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

  return (
    <Box>
      {/* اطلاعات شخصی/سازمانی کاربر حالا در تب «داشبورد» (PersonalDashboardPage)
          نمایش داده می‌شود — طبق personnel_portal.html، صفحه اطلاعیه‌ها فقط
          اطلاعیه‌هاست، بدون تکرار کارت پروفایل. */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, flexWrap: "wrap", gap: 2 }}>
        <Typography variant="h5" fontWeight={800}>
          اطلاعیه‌ها
        </Typography>
        {canCreateAnything && (
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

      {/* کنترل Segmented — دقیقاً طبق personnel_portal.html: کپسول خاکستری
          روشن با ۳ دکمه؛ فعال = پس‌زمینه سفید/Paper + متن رنگی + سایه ملایم،
          به‌جای Tab خط‌زیرین معمول MUI. */}
      {canCreateAnything && (
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

      {tab === "received" && (
        <Stack spacing={1.5}>
          {notices === null ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              {notices.length === 0 && (
                <Card variant="outlined" sx={{ p: 4, borderRadius: 3, textAlign: "center" }}>
                  <Typography variant="body2" color="text.secondary">
                    در حال حاضر اطلاعیه‌ای برای شما ثبت نشده است.
                  </Typography>
                </Card>
              )}
              {notices.map((notice) => (
                <ReceivedNoticeCard key={notice.id} notice={notice} onOpened={handleMarkedRead} />
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

      {tab === "sent" && (
        <Card variant="outlined" sx={{ borderRadius: 3, p: 1 }}>
          <NoticeReportTable
            fetchPage={fetchSentByMe}
            showSender={false}
            allowDelete
            reloadKey={sentReloadKey}
          />
        </Card>
      )}

      {tab === "archive" && (
        <Card variant="outlined" sx={{ p: 4, borderRadius: 3, textAlign: "center" }}>
          <ArchiveOutlinedIcon sx={{ fontSize: 32, color: "text.disabled", mb: 1 }} />
          <Typography variant="body2" color="text.secondary">
            آرشیو اطلاعیه‌ها به‌زودی — این قابلیت هنوز پیاده‌سازی نشده است.
          </Typography>
        </Card>
      )}
    </Box>
  );
}
