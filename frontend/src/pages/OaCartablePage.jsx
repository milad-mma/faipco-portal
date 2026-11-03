// «کارتابل من» — اتوماسیون اداری فاز ۳الف: دریافتی، در انتظار اقدام، ارسالی، انجام‌شده (و پیوند پیش‌نویس‌ها).
// فقط نامه‌هایی که خود شخص به آن‌ها دسترسی دارد؛ ردیف خوانده‌نشده پررنگ. صفحه‌بندی و جست‌وجو در سرور.
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardActionArea,
  Chip,
  CircularProgress,
  IconButton,
  Pagination,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import AttachFileIcon from "@mui/icons-material/AttachFile";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import EditNoteOutlinedIcon from "@mui/icons-material/EditNoteOutlined";
import NotificationsActiveOutlinedIcon from "@mui/icons-material/NotificationsActiveOutlined";
import NotificationPrefsDialog from "../components/oa/NotificationPrefsDialog";
import SecretariesDialog from "../components/oa/SecretariesDialog";
import SupervisorAccountOutlinedIcon from "@mui/icons-material/SupervisorAccountOutlined";
import { fetchCartable } from "../api/automationLetters";
import { useAuth } from "../context/AuthContext";
import { toPersianDigits } from "../utils/searchText";

const BOXES = [
  { key: "inbox", label: "دریافتی" },
  { key: "pending", label: "در انتظار اقدام" },
  { key: "sent", label: "ارسالی" },
  { key: "done", label: "انجام‌شده" },
];
const URGENCY = { urgent: "فوری", immediate: "آنی" };
const ROLE = { recipient: "گیرنده", cc: "رونوشت", referral: "ارجاع" };
const KIND = { action: "اقدام", info: "اطلاع" };

const fmt = (d) => (d ? new Date(d).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "");

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

  return (
    <Box sx={{ maxWidth: 1000, mx: "auto" }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" flexWrap="wrap" gap={1} sx={{ mb: 2 }}>
        <Typography variant="h5" fontWeight={700}>
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
            <Button variant="outlined" startIcon={<EditNoteOutlinedIcon />} onClick={() => navigate("/automation/drafts")} sx={{ height: 40 }}>
              پیش‌نویس‌ها و نامه‌ی جدید
            </Button>
          )}
        </Stack>
      </Stack>

      <Tabs value={box} onChange={(_, v) => setParams({ box: v, q, page: 1 })} variant="scrollable" sx={{ mb: 2 }}>
        {BOXES.map((b) => (
          <Tab
            key={b.key}
            value={b.key}
            label={
              b.key === "inbox" && user?.oa_unread
                ? `${b.label} (${toPersianDigits(user.oa_unread)})`
                : b.key === "pending" && user?.oa_pending
                  ? `${b.label} (${toPersianDigits(user.oa_pending)})`
                  : b.label
            }
          />
        ))}
      </Tabs>

      <TextField size="small" placeholder="جست‌وجو در موضوع، فرستنده و شماره" value={q} onChange={(e) => setQ(e.target.value)} sx={{ mb: 2, width: { xs: "100%", sm: 360 } }} />

      {error && <Alert severity="error">{error}</Alert>}
      {!data && !error && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      )}
      {data && data.items.length === 0 && (
        <Alert severity="info">{box === "pending" ? "موردی در انتظار اقدام ندارید." : "نامه‌ای نیست."}</Alert>
      )}
      {data && data.items.length > 0 && (
        <Stack spacing={1}>
          {data.items.map((it) => (
            <Card key={`${it.letter_id}-${it.task_id || ""}`} variant="outlined" sx={{ borderRadius: 2, ...(it.unread ? { borderInlineStartWidth: "4px", borderInlineStartColor: "primary.main", bgcolor: "action.hover" } : {}) }}>
              <CardActionArea onClick={() => navigate(`/automation/letters/${it.letter_id}`)} sx={{ p: 1.5 }}>
                <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap">
                  {it.confidentiality === "confidential" && <LockOutlinedIcon fontSize="small" color="error" />}
                  <Typography
                    fontWeight={it.unread ? 800 : 400}
                    color={box === "inbox" && !it.unread ? "text.secondary" : "text.primary"}
                    sx={{ flex: 1, minWidth: 0 }}
                    noWrap
                  >
                    {it.subject || "(بدون موضوع)"}
                  </Typography>
                  {URGENCY[it.urgency] && <Chip size="small" color="warning" label={URGENCY[it.urgency]} />}
                  {it.kind && <Chip size="small" variant="outlined" label={KIND[it.kind]} />}
                  {(it.roles || []).map((r) => <Chip key={r} size="small" variant="outlined" label={ROLE[r] || r} />)}
                  {it.overdue && <Chip size="small" color="error" label="معوق" />}
                  {it.attachments > 0 && (
                    <Stack direction="row" alignItems="center" sx={{ color: "text.secondary" }}>
                      <AttachFileIcon sx={{ fontSize: 16 }} />
                      <Typography variant="caption">{toPersianDigits(it.attachments)}</Typography>
                    </Stack>
                  )}
                </Stack>
                <Stack direction="row" gap={2} flexWrap="wrap" sx={{ mt: 0.5 }}>
                  {it.official_number && (
                    <Typography variant="caption" color="text.secondary">
                      <bdi dir="ltr">{toPersianDigits(it.official_number)}</bdi>
                    </Typography>
                  )}
                  <Typography variant="caption" color="text.secondary">
                    {box === "sent" ? "ارسال" : it.task_from && it.task_from !== it.sender ? `ارجاع از ${it.task_from}` : `از ${it.sender || "—"}`} — {fmt(it.at)}
                  </Typography>
                  {it.instruction && (
                    <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: 400 }}>
                      دستور: {it.instruction}
                    </Typography>
                  )}
                  {it.due_at && box === "pending" && (
                    <Typography variant="caption" color={it.overdue ? "error" : "text.secondary"}>
                      مهلت: {fmt(it.due_at)}
                    </Typography>
                  )}
                  {box === "done" && it.result_note && (
                    <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: 400 }}>
                      نتیجه: {it.result_note}
                    </Typography>
                  )}
                </Stack>
              </CardActionArea>
            </Card>
          ))}
        </Stack>
      )}
      {data && pages > 1 && (
        <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
          <Pagination count={pages} page={page} onChange={(_, p) => setParams({ box, q, page: p })} />
        </Box>
      )}
      <NotificationPrefsDialog open={prefsOpen} onClose={() => setPrefsOpen(false)} />
      <SecretariesDialog open={secretariesOpen} onClose={() => setSecretariesOpen(false)} />
    </Box>
  );
}
