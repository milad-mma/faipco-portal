// کارت «نامه‌ها» در داشبورد شخصی — هم‌شکل کارت «اطلاعیه‌های اخیر»:
// عنوان + «کارتابل»، سه شمارنده (خوانده‌نشده، در انتظار اقدام، معوق)، حداکثر سه مورد اولویت‌دار و دکمه‌ی «نامه‌ی جدید».
// فقط از نامه‌هایی که خود شخص به آن‌ها دسترسی دارد (سند مرجع بخش ۱۳).
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Box, Button, Card, Chip, Stack, Typography } from "@mui/material";
import EditNoteOutlinedIcon from "@mui/icons-material/EditNoteOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import { createDraft, fetchOaDashboard } from "../../api/automationLetters";
import { swr } from "../../api/swrCache";
import { toPersianDigits } from "../../utils/searchText";

const fmt = (d) => (d ? new Date(d).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "");

function Counter({ label, value, color, onClick }) {
  return (
    <Box
      onClick={onClick}
      sx={{
        flex: 1,
        borderRadius: 2,
        bgcolor: "action.hover",
        py: 1,
        textAlign: "center",
        cursor: "pointer",
        "&:hover": { bgcolor: "action.selected" },
      }}
    >
      <Typography fontWeight={800} fontSize={18} color={value ? color : "text.disabled"} sx={{ lineHeight: 1.3 }}>
        {toPersianDigits(value || 0)}
      </Typography>
      <Typography variant="caption" color="text.secondary" sx={{ fontSize: 11 }}>
        {label}
      </Typography>
    </Box>
  );
}

export default function DashboardLettersCard({ user }) {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    swr("dashboard:oa", fetchOaDashboard, setData).catch(() => setData((prev) => prev ?? { counters: null, items: [] }));
  }, []);

  // شمارنده‌ها از پاسخ تازه؛ تا رسیدن پاسخ، شمارنده‌های /me
  const c = data?.counters || { unread: user?.oa_unread || 0, pending: user?.oa_pending || 0, overdue: user?.oa_overdue || 0 };
  const items = data?.items || [];

  async function newLetter(e) {
    e.stopPropagation();
    setCreating(true);
    try {
      const d = await createDraft({});
      navigate(`/automation/drafts/${d.id}`);
    } catch {
      navigate("/automation/drafts");
    }
  }

  return (
    <Card variant="outlined" sx={{ borderRadius: 2, p: 1.75 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
        <Typography fontWeight={800} fontSize={14}>
          نامه‌ها
        </Typography>
        <Chip label="کارتابل" size="small" onClick={() => navigate("/automation/cartable")} sx={{ fontSize: 10, height: 20, cursor: "pointer" }} />
      </Stack>

      <Stack direction="row" spacing={1} sx={{ mb: 1.25 }}>
        <Counter label="خوانده‌نشده" value={c.unread} color="secondary.main" onClick={() => navigate("/automation/cartable")} />
        <Counter label="در انتظار اقدام" value={c.pending} color="warning.main" onClick={() => navigate("/automation/cartable?box=pending")} />
        <Counter label="معوق" value={c.overdue} color="error.main" onClick={() => navigate("/automation/cartable?box=pending")} />
      </Stack>

      {data === null ? (
        <Typography variant="caption" color="text.secondary">
          در حال بارگذاری...
        </Typography>
      ) : items.length === 0 ? (
        <Typography variant="caption" color="text.secondary">
          موردی در انتظار اقدام ندارید.
        </Typography>
      ) : (
        <Stack spacing={1}>
          {items.map((it) => (
            <Stack
              key={`${it.reason}-${it.letter_id}`}
              direction="row"
              justifyContent="space-between"
              alignItems="center"
              spacing={1}
              onClick={() => navigate(it.origin === "revision" ? `/automation/drafts/${it.letter_id}` : `/automation/letters/${it.letter_id}`)}
              sx={{ cursor: "pointer" }}
            >
              <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 0 }}>
                <Box
                  sx={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    flexShrink: 0,
                    bgcolor: it.overdue || it.urgency === "immediate" ? "error.main" : it.urgency === "urgent" ? "warning.main" : "primary.main",
                  }}
                />
                {it.confidentiality === "confidential" && <LockOutlinedIcon sx={{ fontSize: 13 }} color="error" />}
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="caption" noWrap component="div" fontWeight={it.reason === "pending" ? 700 : 400}>
                    {it.subject || "(بدون موضوع)"}
                  </Typography>
                  <Typography variant="caption" color={it.overdue ? "error" : "text.secondary"} noWrap component="div" sx={{ fontSize: 10 }}>
                    {it.reason === "pending" ? (it.kind === "revision" ? "برگشت برای اصلاح" : it.kind === "info" ? "برای اطلاع" : "در انتظار اقدام") : "خوانده‌نشده"}
                    {it.from ? ` — ${it.from}` : ""}
                    {it.due_at ? ` — مهلت ${fmt(it.due_at)}` : ""}
                  </Typography>
                </Box>
              </Stack>
              <Typography variant="caption" color="text.secondary" sx={{ flexShrink: 0, fontSize: 10 }}>
                {fmt(it.at)}
              </Typography>
            </Stack>
          ))}
        </Stack>
      )}

      <Stack direction="row" justifyContent="flex-end" sx={{ mt: 1.25 }}>
        <Button size="small" variant="outlined" startIcon={<EditNoteOutlinedIcon />} onClick={newLetter} disabled={creating} sx={{ borderRadius: 999 }}>
          نامه‌ی جدید
        </Button>
      </Stack>
    </Card>
  );
}
