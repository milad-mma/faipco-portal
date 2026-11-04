// «کارتابل من» — اتوماسیون اداری: دریافتی، در انتظار اقدام، ارسالی، انجام‌شده (و پیوند پیش‌نویس‌ها).
// ظاهر مثل صفحه‌ی «اطلاعیه‌ها»: تب‌های قرصی، کارت با آیکون پاکت (خوانده‌نشده پررنگ)، تاریخ زیر عنوان و نشان فوریت.
// فقط نامه‌هایی که خود شخص به آن‌ها دسترسی دارد؛ صفحه‌بندی و جست‌وجو در سرور.
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  IconButton,
  Pagination,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import AttachFileOutlinedIcon from "@mui/icons-material/AttachFileOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import EditNoteOutlinedIcon from "@mui/icons-material/EditNoteOutlined";
import NotificationsActiveOutlinedIcon from "@mui/icons-material/NotificationsActiveOutlined";
import SupervisorAccountOutlinedIcon from "@mui/icons-material/SupervisorAccountOutlined";
import MailOutlineIcon from "@mui/icons-material/MailOutline";
import DraftsOutlinedIcon from "@mui/icons-material/DraftsOutlined";
import InboxOutlinedIcon from "@mui/icons-material/InboxOutlined";
import PendingActionsOutlinedIcon from "@mui/icons-material/PendingActionsOutlined";
import SendOutlinedIcon from "@mui/icons-material/SendOutlined";
import TaskAltOutlinedIcon from "@mui/icons-material/TaskAltOutlined";
import BackLink from "../components/BackLink";
import NotificationPrefsDialog from "../components/oa/NotificationPrefsDialog";
import SecretariesDialog from "../components/oa/SecretariesDialog";
import { fetchCartable } from "../api/automationLetters";
import { useAuth } from "../context/AuthContext";
import { toPersianDigits } from "../utils/searchText";

const BOXES = [
  { key: "inbox", label: "دریافتی", icon: <InboxOutlinedIcon fontSize="small" /> },
  { key: "pending", label: "در انتظار اقدام", icon: <PendingActionsOutlinedIcon fontSize="small" /> },
  { key: "sent", label: "ارسالی", icon: <SendOutlinedIcon fontSize="small" /> },
  { key: "done", label: "انجام‌شده", icon: <TaskAltOutlinedIcon fontSize="small" /> },
];
// نشان فوریت مثل نشان اولویت اطلاعیه‌ها
const URGENCY = {
  normal: { label: "عادی", bg: "secondary.main", color: "secondary.contrastText" },
  urgent: { label: "فوری", bg: "error.light", color: "common.white" },
  immediate: { label: "آنی", bg: "error.main", color: "error.contrastText" },
};
const ROLE = { recipient: "گیرنده", cc: "رونوشت", referral: "ارجاع" };
const KIND = { action: "اقدام", info: "اطلاع", paraph: "پاراف", approve: "تأیید", sign: "امضا" };

const fmt = (d) => (d ? new Date(d).toLocaleString("fa-IR") : "");

function UrgencyBadge({ urgency }) {
  const cfg = URGENCY[urgency] || URGENCY.normal;
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

function LetterCard({ it, box, onOpen }) {
  // در «دریافتی» خوانده‌نشده‌ها پررنگ؛ در «در انتظار اقدام» همه برجسته؛ بقیه حالت خوانده‌شده
  const highlight = box === "pending" || (box === "inbox" && it.unread);
  const from =
    box === "sent"
      ? null
      : it.task_from && it.task_from !== it.sender
        ? `ارجاع از ${it.task_from}`
        : `از ${it.sender || "—"}`;
  return (
    <Card variant="outlined" sx={{ borderRadius: 2, overflow: "hidden" }}>
      <Box
        onClick={onOpen}
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
        <Stack direction="row" spacing={1.25} sx={{ minWidth: 0, flex: 1 }}>
          <Box
            sx={{
              width: 42,
              height: 42,
              borderRadius: "50%",
              bgcolor: highlight ? "secondary.main" : "action.hover",
              color: highlight ? "secondary.contrastText" : "text.disabled",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {box === "inbox" && !it.unread ? <DraftsOutlinedIcon fontSize="small" /> : <MailOutlineIcon fontSize="small" />}
          </Box>
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Stack direction="row" alignItems="center" gap={0.5} sx={{ minWidth: 0 }}>
              {it.confidentiality === "confidential" && <LockOutlinedIcon sx={{ fontSize: 16 }} color="error" titleAccess="محرمانه" />}
              <Typography
                fontSize={14}
                fontWeight={highlight ? 800 : 500}
                color={highlight ? "text.primary" : "text.secondary"}
                sx={{ lineHeight: 1.7, wordBreak: "break-word", minWidth: 0 }}
              >
                {it.subject || "(بدون موضوع)"}
              </Typography>
            </Stack>
            <Typography fontSize={11} color="text.secondary" sx={{ mt: 0.25 }}>
              {[
                from,
                it.official_number ? `شماره ${toPersianDigits(it.official_number)}` : null,
                it.instruction ? `دستور: ${it.instruction}` : null,
                box === "done" && it.result_note ? `نتیجه: ${it.result_note}` : null,
              ]
                .filter(Boolean)
                .join(" — ")}
            </Typography>
            {/* تاریخ زیر عنوان مثل اطلاعیه‌ها (textAlign left با افزونه‌ی RTL راست‌چین می‌شود) */}
            <Typography fontSize={10} color="text.secondary" sx={{ direction: "ltr", textAlign: "left", mt: 0.25 }}>
              {fmt(it.at)}
            </Typography>
            {it.due_at && box === "pending" && (
              <Typography fontSize={11} color={it.overdue ? "error" : "text.secondary"} sx={{ mt: 0.25 }}>
                مهلت: {fmt(it.due_at)}
                {it.overdue ? " (معوق)" : ""}
              </Typography>
            )}
          </Box>
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ flexShrink: 0 }}>
          {it.status === "cancelled" && <Chip size="small" color="error" label="ابطال" sx={{ height: 18, fontSize: 10 }} />}
          {it.kind && <Chip size="small" variant="outlined" color="info" label={KIND[it.kind]} sx={{ height: 18, fontSize: 10 }} />}
          {(it.roles || [])
            .filter((r) => ROLE[r])
            .map((r) => (
              <Chip key={r} size="small" variant="outlined" label={ROLE[r]} sx={{ height: 18, fontSize: 10, display: { xs: "none", sm: "inline-flex" } }} />
            ))}
          {it.attachments > 0 && <AttachFileOutlinedIcon fontSize="small" sx={{ color: "text.secondary" }} titleAccess="دارای پیوست" />}
          <UrgencyBadge urgency={it.urgency} />
        </Stack>
      </Box>
    </Card>
  );
}

export default function OaCartablePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const box = BOXES.some((b) => b.key === params.get("box")) ? params.get("box") : "inbox";
  const page = Number(params.get("page")) || 1;
  const [q, setQ] = useState(params.get("q") || "");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [prefsOpen, setPrefsOpen] = useState(false);
  const [secretariesOpen, setSecretariesOpen] = useState(false);

  useEffect(() => {
    setData(null);
    setError("");
    fetchCartable(box, params.get("q") || "", page)
      .then(setData)
      .catch((err) => setError(err.response?.data?.detail || "دریافت کارتابل ناموفق بود."));
  }, [box, page, params]);

  // جست‌وجو با تأخیر کوتاه
  useEffect(() => {
    const t = setTimeout(() => {
      if ((params.get("q") || "") !== q) setParams({ box, q, page: 1 });
    }, 400);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const count = (key) => (key === "inbox" ? user?.oa_unread : key === "pending" ? user?.oa_pending : 0);

  return (
    <Box sx={{ maxWidth: { xs: "100%", md: 1100 }, mx: "auto" }}>
      {!user?.is_superuser && <BackLink to="/my-dashboard" />}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, flexWrap: "wrap", gap: 2 }}>
        <Typography variant="h5" fontWeight={800}>
          کارتابل من
        </Typography>
        <Stack direction="row" alignItems="center" gap={1}>
          <Tooltip title="منشی‌ها">
            <IconButton onClick={() => setSecretariesOpen(true)}><SupervisorAccountOutlinedIcon /></IconButton>
          </Tooltip>
          <Tooltip title="تنظیمات اعلان">
            <IconButton onClick={() => setPrefsOpen(true)}><NotificationsActiveOutlinedIcon /></IconButton>
          </Tooltip>
          {user?.can_oa_access && (
            <Button
              variant="contained"
              startIcon={<EditNoteOutlinedIcon />}
              onClick={() => navigate("/automation/drafts")}
              sx={{ borderRadius: 999 }}
            >
              پیش‌نویس‌ها و نامه‌ی جدید
            </Button>
          )}
        </Stack>
      </Box>

      {/* تب‌های قرصی مثل صفحه‌ی اطلاعیه‌ها */}
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "repeat(2, 1fr)", sm: `repeat(${BOXES.length}, 1fr)` },
          bgcolor: "action.hover",
          borderRadius: { xs: 3, sm: 999 },
          p: 0.5,
          mb: 2,
          gap: 0.5,
        }}
      >
        {BOXES.map((b) => {
          const n = count(b.key);
          return (
            <Box
              key={b.key}
              onClick={() => setParams({ box: b.key, q, page: 1 })}
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
                color: box === b.key ? "primary.main" : "text.secondary",
                bgcolor: box === b.key ? "background.paper" : "transparent",
                boxShadow: box === b.key ? 1 : "none",
              }}
            >
              {b.icon}
              {b.label}
              {n ? ` (${toPersianDigits(n)})` : ""}
            </Box>
          );
        })}
      </Box>

      <TextField
        size="small"
        placeholder="جست‌وجو در موضوع، فرستنده و شماره"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        sx={{ mb: 2, width: { xs: "100%", sm: 360 }, "& .MuiInputBase-root": { height: 40 } }}
      />

      {error && <Alert severity="error">{error}</Alert>}
      {!data && !error && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      )}
      {data && data.items.length === 0 && (
        <Card variant="outlined" sx={{ p: 4, borderRadius: 2, textAlign: "center" }}>
          <Typography variant="body2" color="text.secondary">
            {box === "pending" ? "موردی در انتظار اقدام ندارید." : "نامه‌ای نیست."}
          </Typography>
        </Card>
      )}
      {data && data.items.length > 0 && (
        <Stack spacing={1.5}>
          {data.items.map((it) => (
            <LetterCard key={`${it.letter_id}-${it.task_id || ""}`} it={it} box={box} onOpen={() => navigate(`/automation/letters/${it.letter_id}`)} />
          ))}
        </Stack>
      )}
      {data && pages > 1 && (
        <Stack alignItems="center" sx={{ pt: 1.5 }}>
          <Pagination count={pages} page={page} onChange={(_, p) => setParams({ box, q, page: p })} color="primary" />
        </Stack>
      )}
      <NotificationPrefsDialog open={prefsOpen} onClose={() => setPrefsOpen(false)} />
      <SecretariesDialog open={secretariesOpen} onClose={() => setSecretariesOpen(false)} />
    </Box>
  );
}
