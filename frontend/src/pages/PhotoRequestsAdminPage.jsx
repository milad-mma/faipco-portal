// «عکس پرسنل» — بررسی درخواست‌های بارگذاری/حذف عکس پرسنلی توسط منابع انسانی (مجوز photo.approve، سایت‌محور).
// تأیید = ثبت در جدول عکس دیتابیس منبع (کاراوب) دقیقاً مثل خود کاراوب و نمایش فوری در پرتال.
import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  Pagination,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";
import DefaultPersonAvatar from "../components/DefaultPersonAvatar";
import { approvePhotoRequest, fetchPhotoRequestBlob, fetchPhotoRequests, rejectPhotoRequest } from "../api/profilePhoto";
import { useAuth } from "../context/AuthContext";
import ModuleNotificationTemplates from "../components/ModuleNotificationTemplates";
import { toPersianDigits } from "../utils/searchText";

const fmt = (d) => (d ? new Date(d).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "");
const STATUS = { approved: { label: "تأیید شد", color: "success" }, rejected: { label: "رد شد", color: "error" } };

function PhotoBox({ requestId, kind, available, label, crossed }) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!available) return undefined;
    let u = null;
    let alive = true;
    fetchPhotoRequestBlob(requestId, kind)
      .then((blob) => {
        if (!alive) return;
        u = URL.createObjectURL(blob);
        setUrl(u);
      })
      .catch(() => {});
    return () => {
      alive = false;
      if (u) URL.revokeObjectURL(u);
    };
  }, [requestId, kind, available]);
  return (
    <Stack alignItems="center" spacing={0.5}>
      <Box
        sx={{
          width: 110,
          height: 110,
          borderRadius: "50%",
          overflow: "hidden",
          bgcolor: "grey.200",
          color: "grey.500",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
          opacity: crossed ? 0.45 : 1,
        }}
      >
        {url ? (
          <Box component="img" src={url} alt="" draggable={false} onContextMenu={(e) => e.preventDefault()} sx={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <DefaultPersonAvatar size="60%" />
        )}
      </Box>
      <Typography variant="caption" color={crossed ? "error" : "text.secondary"}>
        {label}
      </Typography>
    </Stack>
  );
}

function RequestCard({ item, onDone }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = item.status === "pending";

  async function act(fn) {
    setBusy(true);
    setError("");
    try {
      await fn();
      onDone();
    } catch (err) {
      setError(err.response?.data?.detail || "انجام نشد.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card variant="outlined" sx={{ borderRadius: 3, p: 2 }}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ xs: "stretch", sm: "center" }}>
        <Stack direction="row" spacing={2} justifyContent="center">
          {pending && <PhotoBox requestId={item.id} kind="current" available={item.has_current_photo} label="عکس فعلی" crossed={item.action === "delete"} />}
          {pending && item.action === "upload" && <PhotoBox requestId={item.id} kind="image" available label="عکس جدید" />}
        </Stack>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap">
            <Typography fontWeight={700}>{item.employee_name}</Typography>
            <Chip size="small" color={item.action === "delete" ? "error" : "primary"} variant="outlined" label={item.action === "delete" ? "حذف عکس" : "بارگذاری عکس"} />
            {STATUS[item.status] && <Chip size="small" color={STATUS[item.status].color} label={STATUS[item.status].label} />}
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            کد پرسنلی: {item.personnel_code ? toPersianDigits(item.personnel_code) : "—"}
            {item.department ? ` — ${item.department}` : ""}
            {item.site ? ` — ${item.site}` : ""}
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            ثبت: {fmt(item.created_at)}
            {item.image_size ? ` — حجم عکس: ${toPersianDigits(Math.round(item.image_size / 1024))} کیلوبایت` : ""}
          </Typography>
          {!pending && (
            <Typography variant="caption" color="text.secondary" display="block">
              {STATUS[item.status]?.label} توسط {item.decided_by_name || "—"} — {fmt(item.decided_at)}
              {item.reject_reason ? ` — دلیل: ${item.reject_reason}` : ""}
            </Typography>
          )}
          {error && <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert>}
          {pending && !rejecting && (
            <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
              <Button variant="contained" color="success" startIcon={busy ? <CircularProgress size={16} color="inherit" /> : <CheckIcon />} disabled={busy} onClick={() => act(() => approvePhotoRequest(item.id))} sx={{ height: 40 }}>
                تأیید و ثبت
              </Button>
              <Button variant="outlined" color="error" startIcon={<CloseIcon />} disabled={busy} onClick={() => setRejecting(true)} sx={{ height: 40 }}>
                رد
              </Button>
            </Stack>
          )}
          {pending && rejecting && (
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 1.5 }}>
              <TextField size="small" autoFocus placeholder="دلیل رد (به پرسنل نمایش داده می‌شود)" value={reason} onChange={(e) => setReason(e.target.value)} sx={{ flex: 1 }} />
              <Button variant="contained" color="error" disabled={busy || !reason.trim()} onClick={() => act(() => rejectPhotoRequest(item.id, reason))} sx={{ height: 40 }}>
                ثبت رد
              </Button>
              <Button variant="text" color="inherit" disabled={busy} onClick={() => setRejecting(false)} sx={{ height: 40 }}>
                انصراف
              </Button>
            </Stack>
          )}
        </Box>
      </Stack>
    </Card>
  );
}

export default function PhotoRequestsAdminPage() {
  const { refetchUser } = useAuth();
  const [box, setBox] = useState("pending");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    setData(null);
    setError("");
    fetchPhotoRequests(box, page)
      .then(setData)
      .catch((err) => setError(err.response?.data?.detail || "دریافت درخواست‌ها ناموفق بود."));
  }, [box, page, reload]);

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 1 }}>
        عکس پرسنل
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        با تأیید، عکس در دیتابیس کاراوب (مثل ثبت از خود کاراوب) و پرتال ثبت یا حذف می‌شود.
      </Typography>
      <Tabs value={box} onChange={(_, v) => { setBox(v); setPage(1); }} sx={{ mb: 2 }}>
        <Tab value="pending" label="در انتظار بررسی" />
        <Tab value="done" label="بررسی‌شده" />
      </Tabs>
      {error && <Alert severity="error">{error}</Alert>}
      {!data && !error && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      )}
      {data && data.items.length === 0 && <Alert severity="info">{box === "pending" ? "درخواستی در انتظار نیست." : "موردی نیست."}</Alert>}
      {data && data.items.length > 0 && (
        <Stack spacing={1.5}>
          {data.items.map((it) => (
            <RequestCard
              key={it.id}
              item={it}
              onDone={() => {
                setReload((r) => r + 1);
                refetchUser?.();
              }}
            />
          ))}
        </Stack>
      )}
      {data && pages > 1 && (
        <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
          <Pagination count={pages} page={page} onChange={(_, p) => setPage(p)} />
        </Box>
      )}
      <ModuleNotificationTemplates module="photo" title="متن اعلان‌های عکس پرسنلی" />
    </Box>
  );
}
