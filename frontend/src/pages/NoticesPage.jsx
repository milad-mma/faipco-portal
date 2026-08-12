import { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  Chip,
  Collapse,
  Divider,
  Stack,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import MailOutlineIcon from "@mui/icons-material/MailOutline";
import DraftsOutlinedIcon from "@mui/icons-material/DraftsOutlined";
import PictureAsPdfOutlinedIcon from "@mui/icons-material/PictureAsPdfOutlined";
import ApartmentOutlinedIcon from "@mui/icons-material/ApartmentOutlined";
import CorporateFareOutlinedIcon from "@mui/icons-material/CorporateFareOutlined";
import WorkOutlineOutlinedIcon from "@mui/icons-material/WorkOutlineOutlined";
import {
  fetchAvailableTargets,
  fetchMyAttendanceCardBlob,
  fetchMyNotices,
  fetchMyPayrollReceiptBlob,
  fetchSentByMe,
  markNoticeRead,
} from "../api/notices";
import NoticeReportTable from "../components/NoticeReportTable";
import { fetchEmployeePhotoThumbnailBlob } from "../api/employees";
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

function InfoField({ icon, label, value }) {
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, minWidth: 0 }}>
      <Box
        sx={{
          width: 36,
          height: 36,
          borderRadius: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "rgba(22, 50, 79, 0.08)",
          color: "primary.main",
          flexShrink: 0,
        }}
      >
        {icon}
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="caption" color="text.secondary" display="block">
          {label}
        </Typography>
        <Typography variant="body2" fontWeight={600} noWrap>
          {value || "—"}
        </Typography>
      </Box>
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
          {isAttendanceCard && <Chip size="small" label="فیش کارکرد" color="info" variant="outlined" />}
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
            <Typography variant="body2" color="text.secondary" sx={{ mb: isPayroll || isAttendanceCard ? 1.5 : 0 }}>
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
  const { user } = useAuth();
  const [tab, setTab] = useState("received");
  const [notices, setNotices] = useState([]);
  const [sentReloadKey, setSentReloadKey] = useState(0);
  const [availableTargets, setAvailableTargets] = useState(null);
  const [photoUrl, setPhotoUrl] = useState(null);

  function loadNotices() {
    fetchMyNotices().then(setNotices);
  }

  useEffect(() => {
    loadNotices();
    fetchAvailableTargets().then(setAvailableTargets);
  }, []);

  // عکس پرسنلی — فقط اگر واقعاً برای این کاربر ثبت شده باشد (has_photo از
  // /auth/me)، تا برای اکثر افراد که هنوز عکسشان Sync نشده، یک درخواست
  // ۴۰۴ اضافه به سرور نزنیم. Object URL موقع خروج از صفحه آزاد می‌شود تا
  // حافظه مرورگر نشتی نداشته باشد.
  useEffect(() => {
    if (!user?.employee_id || !user?.has_photo) {
      setPhotoUrl(null);
      return;
    }
    let objectUrl = null;
    fetchEmployeePhotoThumbnailBlob(user.employee_id)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setPhotoUrl(objectUrl);
      })
      .catch(() => setPhotoUrl(null));
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [user?.employee_id, user?.has_photo]);

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
      availableTargets.can_upload_payroll ||
      availableTargets.can_upload_attendance_card);

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
        <Card
          variant="outlined"
          sx={{
            p: 2.5,
            borderRadius: 3,
            mb: 3,
            background: "linear-gradient(135deg, rgba(22, 50, 79, 0.04) 0%, rgba(224, 164, 88, 0.05) 100%)",
          }}
        >
          <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2.5 }}>
            <Avatar
              src={photoUrl || undefined}
              sx={{ width: 72, height: 72, bgcolor: "primary.main", fontSize: 26, fontWeight: 700 }}
            >
              {(user.first_name?.[0] || "") + (user.last_name?.[0] || "")}
            </Avatar>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="subtitle1" fontWeight={700} noWrap>
                {user.first_name} {user.last_name}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={monoFontSx}>
                کد پرسنلی: {user.personnel_code}
              </Typography>
            </Box>
          </Stack>

          <Divider sx={{ mb: 2.5 }} />

          <Stack direction="row" spacing={3} flexWrap="wrap" useFlexGap rowGap={2.5}>
            <InfoField icon={<ApartmentOutlinedIcon fontSize="small" />} label="سایت" value={user.site_name} />
            <InfoField
              icon={<CorporateFareOutlinedIcon fontSize="small" />}
              label="واحد سازمانی"
              value={user.department_name}
            />
            <InfoField
              icon={<WorkOutlineOutlinedIcon fontSize="small" />}
              label="سمت"
              value={user.position_title}
            />
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
