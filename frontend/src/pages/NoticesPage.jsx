import { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  Collapse,
  Stack,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import MailOutlineIcon from "@mui/icons-material/MailOutline";
import DraftsOutlinedIcon from "@mui/icons-material/DraftsOutlined";
import PictureAsPdfOutlinedIcon from "@mui/icons-material/PictureAsPdfOutlined";
import {
  fetchAvailableTargets,
  fetchMyNotices,
  fetchMyPayrollReceiptBlob,
  fetchSentByMe,
  markNoticeRead,
} from "../api/notices";
import NoticeReportTable from "../components/NoticeReportTable";
import { useAuth } from "../context/AuthContext";
import { monoFontSx } from "../theme";

const PRIORITY_LABELS = {
  low: { label: "کم", color: "default" },
  normal: { label: "عادی", color: "info" },
  high: { label: "بالا", color: "warning" },
  urgent: { label: "فوری", color: "error" },
};

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

function ReceivedNoticeCard({ notice, onOpened }) {
  const [expanded, setExpanded] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const isUnread = !notice.is_read;
  const isPayroll = notice.notice_type === "payroll";

  function handleToggle() {
    if (!expanded && isUnread) {
      markNoticeRead(notice.id).catch(() => {});
      onOpened?.(notice.id);
    }
    setExpanded((v) => !v);
  }

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        overflow: "hidden",
        borderInlineStart: isUnread ? "4px solid" : "4px solid transparent",
        borderInlineStartColor: isUnread ? "secondary.main" : "transparent",
        backgroundColor: isUnread ? "rgba(224, 164, 88, 0.06)" : "transparent",
      }}
    >
      <Box
        onClick={handleToggle}
        sx={{
          p: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          cursor: "pointer",
          gap: 2,
          "&:hover": { backgroundColor: "action.hover" },
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center" sx={{ minWidth: 0 }}>
          {isUnread ? <MailOutlineIcon color="secondary" /> : <DraftsOutlinedIcon color="disabled" />}
          <Box sx={{ minWidth: 0 }}>
            <Typography
              variant="body1"
              fontWeight={isUnread ? 700 : 400}
              color={isUnread ? "text.primary" : "text.secondary"}
              noWrap
            >
              {notice.title}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {new Date(notice.created_at).toLocaleString("fa-IR")}
            </Typography>
          </Box>
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center">
          {isPayroll && <Chip size="small" label="فیش حقوقی" color="secondary" variant="outlined" />}
          <Chip
            size="small"
            label={PRIORITY_LABELS[notice.priority]?.label}
            color={PRIORITY_LABELS[notice.priority]?.color}
          />
        </Stack>
      </Box>
      <Collapse in={expanded}>
        <Box sx={{ px: 2, pb: 2 }}>
          {notice.body && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: isPayroll ? 1.5 : 0 }}>
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
          <Box sx={{ mt: 1.5, pt: 1.5, borderTop: "1px solid", borderColor: "divider" }}>
            <Typography variant="caption" color="text.secondary" display="block">
              فرستنده: {notice.sender_name}
            </Typography>
            {notice.sender_department_name && (
              <Typography variant="caption" color="text.secondary" display="block">
                واحد: {notice.sender_department_name}
              </Typography>
            )}
          </Box>
        </Box>
      </Collapse>
    </Card>
  );
}

export default function NoticesPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState("received");
  const [notices, setNotices] = useState([]);
  const [sentReloadKey, setSentReloadKey] = useState(0);
  const [availableTargets, setAvailableTargets] = useState(null);

  function loadNotices() {
    fetchMyNotices().then(setNotices);
  }

  useEffect(() => {
    loadNotices();
    fetchAvailableTargets().then(setAvailableTargets);
  }, []);

  // پیام از Service Worker وقتی یک Push جدید می‌رسد — لیست را بدون Reload
  // صفحه، دوباره از سرور می‌خوانیم (چه در تب دریافتی، چه ارسالی من).
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    function handleMessage(event) {
      if (event.data?.type === "faipco-notice-push") {
        loadNotices();
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
      availableTargets.can_upload_payroll);

  function handleMarkedRead(noticeId) {
    setNotices((prev) => prev.map((n) => (n.id === noticeId ? { ...n, is_read: true } : n)));
  }

  return (
    <Box>
      {/* باکس اطلاعات شخصی/سازمانی کاربر جاری — بالای عنوان اطلاعیه‌ها؛ فقط
          برای پرسنلی که به یک رکورد Employee سینک‌شده وصل هستند؛ کاربران
          مدیریتی محض (بدون employee_id، مثل admin) این باکس را نمی‌بینند
          چون داده‌ای برایش ندارند. */}
      {user?.employee_id && (
        <Card variant="outlined" sx={{ p: 2.5, borderRadius: 3, mb: 3 }}>
          <Stack direction="row" spacing={4} flexWrap="wrap" useFlexGap rowGap={2}>
            <Box>
              <Typography variant="caption" color="text.secondary" display="block">
                نام و نام خانوادگی
              </Typography>
              <Typography variant="body2" fontWeight={600}>
                {user.first_name} {user.last_name}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary" display="block">
                کد پرسنلی
              </Typography>
              <Typography variant="body2" fontWeight={600} sx={monoFontSx}>
                {user.personnel_code}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary" display="block">
                سایت
              </Typography>
              <Typography variant="body2" fontWeight={600}>
                {user.site_name || "—"}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary" display="block">
                واحد سازمانی
              </Typography>
              <Typography variant="body2" fontWeight={600}>
                {user.department_name || "—"}
              </Typography>
            </Box>
          </Stack>
        </Card>
      )}

      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, flexWrap: "wrap", gap: 2 }}>
        <Box>
          <Typography variant="h5" fontWeight={700}>
            اطلاعیه‌ها
          </Typography>
        </Box>
        {canCreateAnything && (
          <Button
            variant="contained"
            startIcon={<AddOutlinedIcon />}
            component={RouterLink}
            to="/notices/new"
          >
            اطلاعیه جدید
          </Button>
        )}
      </Box>

      {canCreateAnything && (
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
          <Tab value="received" label="دریافتی" />
          <Tab value="sent" label="ارسالی" />
        </Tabs>
      )}

      {tab === "received" && (
        <Stack spacing={1.5}>
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
    </Box>
  );
}
