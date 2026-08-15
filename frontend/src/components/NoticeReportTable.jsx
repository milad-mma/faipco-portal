import { useEffect, useState } from "react";
import {
  Box,
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
  TablePagination,
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

const ROWS_PER_PAGE = 10;
// بیش از این تعداد Chip داخل خودِ سطر جدول نمایش داده نمی‌شود — مقصدهای بیشتر
// فقط با کلیک روی «و N مورد دیگر» داخل یک Dialog قابل‌اسکرول دیده می‌شوند، تا
// سطر جدول بیش‌ازحد بزرگ نشود و لود گزارش کند نشود.
const INLINE_TARGET_LIMIT = 3;

/**
 * جدول گزارش اطلاعیه‌ها — هم برای «ارسالی من» و هم برای «گزارش کامل Admin»
 * استفاده می‌شود. برخلاف قبل، این کامپوننت خودش صفحه‌بندی سمت سرور را مدیریت
 * می‌کند (نه گرفتن کل لیست از والد و برش آن در فرانت‌اند) — چون واکشی و
 * پردازش هم‌زمان همه اطلاعیه‌های سیستم در یک درخواست، با رشد تعدادشان به‌شدت
 * کند می‌شد. کافی است تابع fetchPage(page, pageSize) داده شود که یک Promise
 * برگرداند شامل {items, total} برای همان صفحه.
 *
 * در هر دو استفاده با allowDelete=true قابلیت حذف فعال است (Backend اجازه
 * می‌دهد: خودِ فرستنده هر اطلاعیه، یا Admin برای اطلاعیه هرکسی). حذف همیشه
 * Soft-Delete است: اطلاعیه از پنل مخاطبان کنار می‌رود ولی خودِ این ردیف در
 * گزارش با برچسب «حذف شده» باقی می‌ماند (به‌جای این‌که ناپدید شود).
 */
export default function NoticeReportTable({ fetchPage, showSender = false, allowDelete = false, reloadKey }) {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  const [readersNoticeId, setReadersNoticeId] = useState(null);
  const [bodyNotice, setBodyNotice] = useState(null);
  const [targetsNotice, setTargetsNotice] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  function loadPage(pageIndex) {
    setIsLoading(true);
    return fetchPage(pageIndex + 1, ROWS_PER_PAGE)
      .then(({ items: pageItems, total: pageTotal }) => {
        setItems(pageItems);
        setTotal(pageTotal);
      })
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    loadPage(page);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, reloadKey]);

  async function handleDelete(notice) {
    if (!window.confirm(`اطلاعیه «${notice.title}» حذف شود؟ این اطلاعیه فوراً از پنل همه دریافت‌کنندگان حذف می‌شود.`)) {
      return;
    }
    setDeletingId(notice.id);
    try {
      await deleteNotice(notice.id);
      // اگر آخرین ردیف همین صفحه حذف شد و صفحه اول نیست، یک صفحه به عقب برو؛
      // وگرنه همین صفحه را دوباره از سرور بخوان.
      if (items.length === 1 && page > 0) {
        setPage((p) => p - 1);
      } else {
        await loadPage(page);
      }
    } catch (err) {
      alert(err.response?.data?.detail || "حذف اطلاعیه ناموفق بود");
    } finally {
      setDeletingId(null);
    }
  }

  if (!isLoading && items.length === 0) {
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
            {items.map((n) => (
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
                <TableCell sx={{ maxWidth: 260 }}>
                  {n.targets.length <= INLINE_TARGET_LIMIT ? (
                    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                      {n.targets.map((t, i) => (
                        <Chip key={i} size="small" variant="outlined" label={t.label} />
                      ))}
                    </Stack>
                  ) : (
                    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap alignItems="center">
                      {n.targets.slice(0, INLINE_TARGET_LIMIT - 1).map((t, i) => (
                        <Chip key={i} size="small" variant="outlined" label={t.label} />
                      ))}
                      <Chip
                        size="small"
                        color="primary"
                        variant="outlined"
                        clickable
                        onClick={() => setTargetsNotice(n)}
                        label={`و ${n.targets.length - (INLINE_TARGET_LIMIT - 1)} مورد دیگر`}
                      />
                    </Stack>
                  )}
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

      <TablePagination
        component="div"
        count={total}
        page={page}
        onPageChange={(_, newPage) => setPage(newPage)}
        rowsPerPage={ROWS_PER_PAGE}
        rowsPerPageOptions={[ROWS_PER_PAGE]}
        labelRowsPerPage="سطر در هر صفحه"
        labelDisplayedRows={({ from, to, count }) => `${from}–${to} از ${count}`}
      />

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

      {/* Dialog: فهرست کامل مقصدهای یک اطلاعیه — وقتی تعداد زیاد است، خودِ این
          Dialog اسکرول می‌شود تا سطر جدول اصلی بزرگ و کند نشود. */}
      <Dialog open={Boolean(targetsNotice)} onClose={() => setTargetsNotice(null)} fullWidth maxWidth="xs">
        <DialogTitle>
          مقصدهای اطلاعیه «{targetsNotice?.title}»
          <Typography variant="caption" color="text.secondary" display="block">
            {targetsNotice?.targets.length} مورد
          </Typography>
        </DialogTitle>
        <DialogContent dividers sx={{ maxHeight: 400, overflowY: "auto" }}>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
            {targetsNotice?.targets.map((t, i) => (
              <Chip key={i} size="small" variant="outlined" label={t.label} />
            ))}
          </Box>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setTargetsNotice(null)}>بستن</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
