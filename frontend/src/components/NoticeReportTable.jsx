import { useState } from "react";
import {
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import ArticleOutlinedIcon from "@mui/icons-material/ArticleOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { monoFontSx } from "../theme";
import { deleteNotice } from "../api/notices";
import NoticeReadersDialog from "./NoticeReadersDialog";

const PRIORITY_LABELS = {
  low: "کم",
  normal: "عادی",
  high: "بالا",
  urgent: "فوری",
};

/**
 * جدول گزارش اطلاعیه‌ها — هم برای «ارسالی من» (با قابلیت حذف) و هم برای
 * «گزارش کامل Admin» (فقط مشاهده) استفاده می‌شود.
 * allowDelete=true فقط در تب «ارسالی من» پاس داده می‌شود؛ حذف همیشه Soft-Delete
 * است: اطلاعیه از پنل مخاطبان کنار می‌رود ولی خودِ این ردیف در گزارش با برچسب
 * «حذف شده» باقی می‌ماند (به‌جای این‌که ناپدید شود) — پس بعد از حذف موفق، فقط
 * وضعیت ردیف به‌روزرسانی می‌شود، نه حذف آن از جدول.
 */
export default function NoticeReportTable({ notices, showSender = false, allowDelete = false, onChanged }) {
  const [readersNoticeId, setReadersNoticeId] = useState(null);
  const [bodyNotice, setBodyNotice] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  async function handleDelete(notice) {
    if (!window.confirm(`اطلاعیه «${notice.title}» حذف شود؟ این اطلاعیه فوراً از پنل همه دریافت‌کنندگان حذف می‌شود.`)) {
      return;
    }
    setDeletingId(notice.id);
    try {
      await deleteNotice(notice.id);
      onChanged?.();
    } finally {
      setDeletingId(null);
    }
  }

  if (notices.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
        هنوز اطلاعیه‌ای ثبت نشده.
      </Typography>
    );
  }

  return (
    <>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>تاریخ و ساعت ارسال</TableCell>
              {showSender && <TableCell>فرستنده</TableCell>}
              <TableCell>عنوان</TableCell>
              <TableCell align="center">متن</TableCell>
              <TableCell>اولویت</TableCell>
              <TableCell>مقصد(ها)</TableCell>
              <TableCell align="center">مخاطبان</TableCell>
              <TableCell align="center">دیده‌شده</TableCell>
              <TableCell align="center">وضعیت</TableCell>
              <TableCell align="center">جزئیات</TableCell>
              {allowDelete && <TableCell align="center">حذف</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {notices.map((n) => (
              <TableRow key={n.id} hover sx={n.is_deleted ? { opacity: 0.6 } : undefined}>
                <TableCell sx={monoFontSx}>
                  {new Date(n.publish_at || n.created_at).toLocaleString("fa-IR")}
                </TableCell>
                {showSender && <TableCell>{n.sender_name}</TableCell>}
                <TableCell>{n.title}</TableCell>
                <TableCell align="center">
                  <Tooltip title="مشاهده متن کامل">
                    <IconButton size="small" onClick={() => setBodyNotice(n)}>
                      <ArticleOutlinedIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
                <TableCell>
                  <Chip size="small" label={PRIORITY_LABELS[n.priority] || n.priority} />
                </TableCell>
                <TableCell>
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    {n.targets.map((t, i) => (
                      <Chip key={i} size="small" variant="outlined" label={t.label} />
                    ))}
                  </Stack>
                </TableCell>
                <TableCell sx={monoFontSx} align="center">
                  {n.audience_count}
                </TableCell>
                <TableCell sx={monoFontSx} align="center">
                  {n.read_count} / {n.audience_count}
                </TableCell>
                <TableCell align="center">
                  {n.is_deleted ? (
                    <Chip size="small" color="error" variant="outlined" label="حذف شده" />
                  ) : (
                    <Chip size="small" color="success" variant="outlined" label="فعال" />
                  )}
                </TableCell>
                <TableCell align="center">
                  <Button
                    size="small"
                    startIcon={<VisibilityOutlinedIcon />}
                    onClick={() => setReadersNoticeId(n.id)}
                  >
                    چه کسانی دیدند
                  </Button>
                </TableCell>
                {allowDelete && (
                  <TableCell align="center">
                    {!n.is_deleted && (
                      <Tooltip title="حذف اطلاعیه">
                        <span>
                          <IconButton
                            size="small"
                            color="error"
                            disabled={deletingId === n.id}
                            onClick={() => handleDelete(n)}
                          >
                            <DeleteOutlineIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    )}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <NoticeReadersDialog noticeId={readersNoticeId} onClose={() => setReadersNoticeId(null)} />

      <Dialog open={Boolean(bodyNotice)} onClose={() => setBodyNotice(null)} fullWidth maxWidth="sm">
        <DialogTitle>{bodyNotice?.title}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
            {bodyNotice?.body}
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setBodyNotice(null)}>بستن</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
