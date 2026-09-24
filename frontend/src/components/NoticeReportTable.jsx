/**
 * جدول گزارش اطلاعیه‌های ارسالی با صفحه‌بندی سمت سرور؛ در موبایل به‌صورت کارت‌های بازشونده نمایش داده می‌شود.
 * شامل کامپوننت داخلی SentNoticeCard (کارت موبایل) و کامپوننت اصلی NoticeReportTable.
 */
import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Card,
  Chip,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
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
  useMediaQuery,
  useTheme,
} from "@mui/material";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import ArticleOutlinedIcon from "@mui/icons-material/ArticleOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { monoFontSx } from "../theme";
import { deleteNotice } from "../api/notices";
import NoticeReadersDialog from "./NoticeReadersDialog";

// برچسب فارسی سطوح اولویت اطلاعیه
const PRIORITY_LABELS = {
  low: "کم",
  normal: "عادی",
  high: "بالا",
  urgent: "فوری",
};

const ROWS_PER_PAGE = 10;  // تعداد اطلاعیه در هر صفحه (سمت سرور)
// حداکثر تعداد Chip مقصد داخل سطر جدول؛ مقصدهای بیشتر با کلیک روی «و N مورد دیگر»
// در یک Dialog قابل‌اسکرول نمایش داده می‌شوند تا سطر بیش‌ازحد بزرگ نشود.
const INLINE_TARGET_LIMIT = 3;

/**
 * کارت یک اطلاعیه‌ی ارسالی در موبایل (هم‌الگو با ReceivedNoticeCard صفحه‌ی «دریافتی»).
 * ورودی: notice، showSender، allowDelete، onShowReaders(id)، onDelete(notice)، isDeleting و renderTargets(notice).
 * به‌طور پیش‌فرض فقط هدر خلاصه (عنوان، تاریخ، اولویت) دیده می‌شود؛ با کلیک، متن، مقصدها،
 * تعداد مخاطب/دیده‌شده و دکمه‌های عملیات باز می‌شوند.
 */
function SentNoticeCard({ notice: n, showSender, allowDelete, onShowReaders, onDelete, isDeleting, renderTargets }) {
  const [expanded, setExpanded] = useState(false);  // باز/بسته بودن بدنه‌ی کارت

  return (
    <Card variant="outlined" sx={{ borderRadius: 2, overflow: "hidden", opacity: n.is_deleted ? 0.6 : 1 }}>
      {/* هدر خلاصه‌ی کارت؛ کلیک روی آن بدنه را باز/بسته می‌کند */}
      <Box
        onClick={() => setExpanded((v) => !v)}
        sx={{
          p: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          cursor: "pointer",
          gap: 1.5,
          "&:hover": { backgroundColor: "action.hover" },
        }}
      >
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography variant="subtitle2" fontWeight={700} sx={{ wordBreak: "break-word" }}>
            {n.title}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={monoFontSx}>
            {new Date(n.publish_at || n.created_at).toLocaleString("fa-IR")}
          </Typography>
        </Box>
        <Stack direction="row" spacing={0.5} alignItems="center" sx={{ flexShrink: 0 }}>
          <Chip size="small" label={PRIORITY_LABELS[n.priority] || n.priority} />
          <ExpandMoreIcon
            fontSize="small"
            color="action"
            sx={{ transform: expanded ? "rotate(180deg)" : "none", transition: "transform 0.15s" }}
          />
        </Stack>
      </Box>

      {/* بدنه‌ی بازشونده: فرستنده، متن، مقصدها، آمار و دکمه‌ها */}
      <Collapse in={expanded}>
        <Box sx={{ px: 2, pb: 2 }}>
          <Stack spacing={1}>
            {showSender && (
              <Typography variant="caption" color="text.secondary">
                فرستنده: {n.sender_name}
              </Typography>
            )}

            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
            >
              {n.body}
            </Typography>

            {renderTargets(n)}

            {/* تعداد مخاطبان، تعداد دیده‌شده و وضعیت حذف */}
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap alignItems="center">
              <Typography variant="caption" sx={monoFontSx}>
                مخاطبان: {n.audience_count}
              </Typography>
              <Typography variant="caption" sx={monoFontSx}>
                دیده‌شده: {n.read_count}/{n.audience_count}
              </Typography>
              {n.is_deleted ? (
                <Chip size="small" color="error" variant="outlined" label="حذف شده" />
              ) : (
                <Chip size="small" color="success" variant="outlined" label="فعال" />
              )}
            </Stack>

            <Divider />

            {/* دکمه‌های مشاهده‌ی خوانندگان و حذف */}
            <Stack direction="row" spacing={0.5} justifyContent="flex-end" alignItems="center">
              <Button size="small" startIcon={<VisibilityOutlinedIcon />} onClick={() => onShowReaders(n.id)}>
                چه کسانی دیدند
              </Button>
              {allowDelete && !n.is_deleted && (
                <Tooltip title="حذف اطلاعیه">
                  <span>
                    <IconButton size="small" color="error" disabled={isDeleting} onClick={() => onDelete(n)}>
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </span>
                </Tooltip>
              )}
            </Stack>
          </Stack>
        </Box>
      </Collapse>
    </Card>
  );
}

/**
 * جدول گزارش اطلاعیه‌ها؛ هم برای «ارسالی من» و هم برای «گزارش کامل ادمین» استفاده می‌شود.
 * ورودی: fetchPage(page, pageSize) که Promise با {items, total} برای همان صفحه برمی‌گرداند (صفحه‌بندی سمت سرور)،
 * showSender (نمایش ستون فرستنده)، allowDelete (امکان حذف) و reloadKey (تغییرش = بارگذاری مجدد و بازگشت به صفحه‌ی اول).
 * حذف همیشه Soft-Delete است: اطلاعیه از پنل مخاطبان کنار می‌رود ولی ردیفش در گزارش با برچسب «حذف شده» می‌ماند.
 * Backend حذف را برای فرستنده‌ی اطلاعیه یا ادمین مجاز می‌کند.
 */
export default function NoticeReportTable({ fetchPage, showSender = false, allowDelete = false, reloadKey }) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));  // زیر breakpoint sm نمای کارتی به‌جای جدول

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);  // تعداد کل اطلاعیه‌ها برای صفحه‌بندی
  const [page, setPage] = useState(0);  // ایندکس صفحه از صفر (سرور از ۱ می‌شمارد)
  const [isLoading, setIsLoading] = useState(true);

  const [readersNoticeId, setReadersNoticeId] = useState(null);  // اطلاعیه‌ای که دیالوگ خوانندگانش باز است
  const [bodyNotice, setBodyNotice] = useState(null);  // اطلاعیه‌ای که دیالوگ متن کاملش باز است
  const [targetsNotice, setTargetsNotice] = useState(null);  // اطلاعیه‌ای که دیالوگ فهرست کامل مقصدهایش باز است
  const [deletingId, setDeletingId] = useState(null);  // شناسه‌ی اطلاعیه‌ی در حال حذف (برای غیرفعال کردن دکمه)

  // یک صفحه از سرور می‌خواند (ایندکس صفر‌پایه به شماره‌ی ۱‌پایه تبدیل می‌شود) و items/total را به‌روز می‌کند
  function loadPage(pageIndex) {
    setIsLoading(true);
    return fetchPage(pageIndex + 1, ROWS_PER_PAGE)
      .then(({ items: pageItems, total: pageTotal }) => {
        setItems(pageItems);
        setTotal(pageTotal);
      })
      .finally(() => setIsLoading(false));
  }

  // با تغییر صفحه یا reloadKey، داده دوباره بارگذاری می‌شود
  useEffect(() => {
    loadPage(page);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, reloadKey]);

  useEffect(() => {
    // با تغییر فیلتر بیرونی (مثلاً انتخاب سایت) به صفحه‌ی اول برمی‌گردد تا روی صفحه‌ی بدون داده نماند
    setPage(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey]);

  // پس از تأیید، اطلاعیه را حذف (Soft-Delete) و صفحه را به‌روز می‌کند
  async function handleDelete(notice) {
    if (!window.confirm(`اطلاعیه «${notice.title}» حذف شود؟ این اطلاعیه فوراً از پنل همه دریافت‌کنندگان حذف می‌شود.`)) {
      return;
    }
    setDeletingId(notice.id);
    try {
      await deleteNotice(notice.id);
      // اگر آخرین ردیف صفحه حذف شد و صفحه‌ی اول نیست، یک صفحه به عقب می‌رود؛
      // وگرنه همین صفحه دوباره از سرور خوانده می‌شود.
      if (items.length === 1 && page > 0) {
        setPage((p) => p - 1);
      } else {
        await loadPage(page);
      }
    } catch (err) {
      alert(err.response?.data?.detail || "حذف اطلاعیه با خطا مواجه شد");
    } finally {
      setDeletingId(null);
    }
  }

  // Chipهای مقصد یک اطلاعیه را می‌سازد (مشترک بین جدول دسکتاپ و کارت موبایل)؛
  // اگر تعداد از INLINE_TARGET_LIMIT بیشتر باشد، بقیه در Chip «و N مورد دیگر» خلاصه می‌شوند.
  function renderTargets(n) {
    if (n.targets.length <= INLINE_TARGET_LIMIT) {
      return (
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
          {n.targets.map((t, i) => (
            <Chip key={i} size="small" variant="outlined" label={t.label} />
          ))}
        </Stack>
      );
    }
    return (
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
    );
  }

  if (!isLoading && items.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
        هنوز اطلاعیه‌ای ثبت نشده.
      </Typography>
    );
  }

  // حالت موبایل: هر اطلاعیه یک کارت عمودی است تا جدول چندستونی نیاز به اسکرول افقی نداشته باشد
  if (isMobile) {
    return (
      <>
        <Stack spacing={1.5}>
          {items.map((n) => (
            <SentNoticeCard
              key={n.id}
              notice={n}
              showSender={showSender}
              allowDelete={allowDelete}
              onShowReaders={setReadersNoticeId}
              onDelete={handleDelete}
              isDeleting={deletingId === n.id}
              renderTargets={renderTargets}
            />
          ))}
        </Stack>

        {/* صفحه‌بندی سمت سرور با اندازه‌ی ثابت صفحه */}
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

        {/* دیالوگ فهرست کامل مقصدهای یک اطلاعیه (قابل‌اسکرول) */}
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

  // حالت دسکتاپ/تبلت: جدول کامل

  return (
    <>
      <TableContainer>
        <Table size="small">
          {/* سرستون‌ها؛ ستون فرستنده و حذف شرطی‌اند */}
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
                  {renderTargets(n)}
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

      {/* صفحه‌بندی سمت سرور با اندازه‌ی ثابت صفحه */}
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

      {/* دیالوگ نمایش متن کامل اطلاعیه */}
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

      {/* دیالوگ فهرست کامل مقصدهای یک اطلاعیه؛ خودِ دیالوگ اسکرول می‌شود تا سطر جدول بزرگ نشود */}
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
