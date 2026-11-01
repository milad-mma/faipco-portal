// صفحه‌ی پشتیبان‌گیری و نگهداری پرتال — بکاپ نسخه‌ی ۴ (docs/backup.md):
// ساخت بکاپ (دیتابیس + فایل‌های اتوماسیون، جریانی، رمزنگاری با age)، نسخه‌های روی سرور (دانلود/بازیابی)، تاریخچه،
// کلید رمزنگاری، بازیابی از فایل قدیمی zip، پاک‌کردن کش و زمان‌بندی/مقصدها. هر بخش با مجوز تفکیک‌شده‌ی خودش.
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  IconButton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import WarningAmberOutlinedIcon from "@mui/icons-material/WarningAmberOutlined";
import DeleteSweepOutlinedIcon from "@mui/icons-material/DeleteSweepOutlined";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import RestoreOutlinedIcon from "@mui/icons-material/RestoreOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import RefreshIcon from "@mui/icons-material/Refresh";
import BackupOutlinedIcon from "@mui/icons-material/BackupOutlined";
import {
  downloadLocalBackup,
  fetchBackupOverview,
  fetchRestoreStatus,
  restoreBackupArchive,
  restoreLocalBackup,
  startBackup,
} from "../api/backup";
import { bustAppCache } from "../api/system";
import { monoFontSx } from "../theme";
import BackupScheduleSettings from "../components/BackupScheduleSettings";
import BackupKeyCard from "../components/BackupKeyCard";
import { useAuth } from "../context/AuthContext";
import { saveBlob } from "../utils/family";
import { toPersianDigits } from "../utils/searchText";

const CONFIRM_PHRASE = "RESTORE";
const POLL_INTERVAL_MS = 3000;
const MAX_POLL_ATTEMPTS = 400; // آماده‌سازی بکاپ بزرگ چند دقیقه طول می‌کشد

const STATUS = {
  running: { label: "در حال ساخت", color: "info" },
  success: { label: "موفق", color: "success" },
  partial: { label: "ساخته شد، ارسال ناقص", color: "warning" },
  failed: { label: "ناموفق", color: "error" },
};
const TRIGGER = { manual: "دستی", scheduled: "زمان‌بندی", download: "دانلود" };
const KIND = { v4: "بدون رمز", "v4-encrypted": "رمزنگاری‌شده", v3: "قالب قدیمی (فقط دیتابیس)" };

function fmtBytes(n) {
  if (n == null) return "—";
  const units = ["بایت", "کیلوبایت", "مگابایت", "گیگابایت"];
  let v = Number(n);
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${toPersianDigits(v.toFixed(i ? 1 : 0))} ${units[i]}`;
}

function fmtDate(v) {
  return v ? new Date(v).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "—";
}

function errorText(err, fallback) {
  const d = err?.response?.data?.detail;
  return typeof d === "string" ? d : fallback;
}

function LogBox({ text }) {
  if (!text) return null;
  return (
    <Box
      sx={{ mb: 2, p: 2, borderRadius: 2, backgroundColor: "rgba(22, 50, 79, 0.06)", ...monoFontSx, fontSize: 12,
        whiteSpace: "pre-wrap", maxHeight: 260, overflowY: "auto" }}
      dir="ltr"
      style={{ direction: "ltr", textAlign: "left" }}
    >
      {text}
    </Box>
  );
}

export default function BackupPage() {
  const { user } = useAuth();
  const can = {
    run: Boolean(user?.can_backup_run_view),
    destinations: Boolean(user?.can_backup_destinations),
    download: Boolean(user?.can_backup_download),
    restore: Boolean(user?.can_backup_restore),
    keys: Boolean(user?.can_backup_key_manage),
    cache: Boolean(user?.can_bust_cache),
  };

  const [overview, setOverview] = useState(null);
  const [overviewError, setOverviewError] = useState("");
  const [sendToDestinations, setSendToDestinations] = useState(true);
  const [startMsg, setStartMsg] = useState(null);
  const [starting, setStarting] = useState(false);
  const [downloading, setDownloading] = useState("");

  const [restoreTarget, setRestoreTarget] = useState(null); // ردیف نسخه‌ی روی سرور
  const [confirmText, setConfirmText] = useState("");
  const [privateKey, setPrivateKey] = useState("");
  const [restoreFile, setRestoreFile] = useState(null); // zip قدیمی
  const [legacyConfirm, setLegacyConfirm] = useState("");
  const [isRestoring, setIsRestoring] = useState(false);
  const [restoreResult, setRestoreResult] = useState(null);
  const [restoreLog, setRestoreLog] = useState("");
  const [stageMsg, setStageMsg] = useState("");

  const [isBustingCache, setIsBustingCache] = useState(false);
  const [cacheBustResult, setCacheBustResult] = useState(null);
  const pollTimer = useRef(null);

  const loadOverview = useCallback(() => {
    if (!can.run) return;
    fetchBackupOverview()
      .then((d) => {
        setOverview(d);
        setOverviewError("");
      })
      .catch((err) => setOverviewError(errorText(err, "دریافت وضعیت بکاپ با خطا مواجه شد.")));
  }, [can.run]);

  useEffect(loadOverview, [loadOverview]);

  // تا وقتی بکاپی در حال ساخت است، هر ۵ ثانیه تازه شود
  const running = overview?.runs?.some((r) => r.status === "running");
  useEffect(() => {
    if (!running) return undefined;
    const t = window.setTimeout(loadOverview, 5000);
    return () => window.clearTimeout(t);
  }, [running, overview, loadOverview]);

  useEffect(() => () => window.clearTimeout(pollTimer.current), []);

  async function handleStart() {
    setStarting(true);
    setStartMsg(null);
    try {
      const r = await startBackup(sendToDestinations);
      setStartMsg({ ok: true, text: r.message });
      setTimeout(loadOverview, 1500);
    } catch (err) {
      setStartMsg({ ok: false, text: errorText(err, "شروع بکاپ با خطا مواجه شد.") });
    } finally {
      setStarting(false);
    }
  }

  async function handleDownload(name) {
    setDownloading(name);
    try {
      saveBlob(await downloadLocalBackup(name), name);
    } catch (err) {
      setOverviewError(errorText(err, "دانلود با خطا مواجه شد."));
    } finally {
      setDownloading("");
    }
  }

  function pollRestoreStatus(attemptsLeft) {
    if (attemptsLeft <= 0) {
      setRestoreResult({ success: false, message: "نتیجه‌ی بازیابی مشخص نشد؛ لاگ سرور را بررسی کنید." });
      setIsRestoring(false);
      return;
    }
    const next = () => {
      pollTimer.current = window.setTimeout(() => pollRestoreStatus(attemptsLeft - 1), POLL_INTERVAL_MS);
    };
    fetchRestoreStatus()
      .then((status) => {
        const stage = status.stage;
        if (stage?.phase === "failed") {
          setRestoreResult({ success: false, message: stage.message });
          setIsRestoring(false);
          return;
        }
        setStageMsg(stage?.message || "");
        setRestoreLog(status.log || "");
        if (status.is_finished) {
          setRestoreResult({ success: true, message: "بازیابی با موفقیت انجام شد." });
          setIsRestoring(false);
          setTimeout(() => window.location.reload(), 2000);
          return;
        }
        if (status.is_failed) {
          setRestoreResult({ success: false, message: "بازیابی با خطا مواجه شد — جزئیات در لاگ زیر است." });
          setIsRestoring(false);
          return;
        }
        next();
      })
      .catch(next); // هنگام Stop/Start سرویس پاسخی نمی‌آید؛ دوباره تلاش
  }

  async function handleRestoreLocal() {
    const target = restoreTarget;
    setRestoreTarget(null);
    setRestoreResult(null);
    setRestoreLog("");
    setStageMsg("");
    setIsRestoring(true);
    try {
      await restoreLocalBackup(target.name, confirmText, privateKey.trim());
      pollRestoreStatus(MAX_POLL_ATTEMPTS);
    } catch (err) {
      setRestoreResult({ success: false, message: errorText(err, "بازیابی با خطا مواجه شد.") });
      setIsRestoring(false);
    } finally {
      setConfirmText("");
      setPrivateKey("");
    }
  }

  async function handleRestoreLegacy() {
    setRestoreResult(null);
    setRestoreLog("");
    setStageMsg("");
    setIsRestoring(true);
    try {
      await restoreBackupArchive(restoreFile, legacyConfirm);
      pollRestoreStatus(MAX_POLL_ATTEMPTS);
    } catch (err) {
      setRestoreResult({ success: false, message: errorText(err, "بازیابی با خطا مواجه شد.") });
      setIsRestoring(false);
    }
  }

  async function handleBustCache() {
    setCacheBustResult(null);
    setIsBustingCache(true);
    try {
      const data = await bustAppCache();
      setCacheBustResult({ success: true, message: data.message });
    } catch (err) {
      setCacheBustResult({ success: false, message: errorText(err, "پاک‌کردن کش با خطا مواجه شد.") });
    } finally {
      setIsBustingCache(false);
    }
  }

  const activeKey = overview?.active_key;

  return (
    <Box sx={{ maxWidth: 960, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        پشتیبان‌گیری
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        بکاپ کامل پرتال (دیتابیس و فایل‌های اتوماسیون اداری)؛ قابل بازیابی هماهنگ روی همین سرور.
      </Typography>

      {overviewError && <Alert severity="error" sx={{ mb: 2 }}>{overviewError}</Alert>}
      {overview?.warnings?.map((w) => (
        <Alert key={w} severity="warning" sx={{ mb: 1 }}>{w}</Alert>
      ))}

      {/* وضعیت بازیابی در جریان (مشترک بین بازیابی از سرور و از فایل) */}
      {(isRestoring || restoreResult) && (
        <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3, borderColor: "error.main" }}>
          <Typography variant="subtitle2" fontWeight={700} color="error.main" sx={{ mb: 1.5 }}>
            بازیابی
          </Typography>
          {isRestoring && !restoreResult && (
            <Alert severity="info" icon={<CircularProgress size={18} />} sx={{ mb: 2 }}>
              {stageMsg || "در حال بازیابی…"}
            </Alert>
          )}
          {restoreResult && (
            <Alert severity={restoreResult.success ? "success" : "error"} sx={{ mb: 2 }}>
              {restoreResult.message}
              {restoreResult.success && " — صفحه به‌طور خودکار بازخوانی می‌شود."}
            </Alert>
          )}
          <LogBox text={restoreLog} />
        </Card>
      )}

      {can.run && (
        <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
            <Typography variant="subtitle1" fontWeight={700}>
              ساخت بکاپ
            </Typography>
            <IconButton size="small" onClick={loadOverview} aria-label="به‌روزرسانی">
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            شامل ساختار و همه‌ی داده‌های دیتابیس و همه‌ی فایل‌های اتوماسیون اداری (به‌جز فایل‌های قرنطینه)، با یک لحظه‌ی
            ثابت از دیتابیس و تطبیق هش هر فایل.{" "}
            {activeKey ? (
              <>
                <LockOutlinedIcon sx={{ fontSize: 14, verticalAlign: "middle" }} /> با کلید {activeKey.key_id} رمزنگاری
                می‌شود.
              </>
            ) : (
              "بدون رمزنگاری (کلیدی ساخته نشده)."
            )}
            {overview?.last_success_at && ` آخرین بکاپ سالم: ${fmtDate(overview.last_success_at)}.`}
            {overview?.disk && ` فضای آزاد: ${fmtBytes(overview.disk.free)}.`}
          </Typography>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }}>
            <Button
              variant="contained"
              startIcon={starting || running ? <CircularProgress size={18} color="inherit" /> : <BackupOutlinedIcon />}
              onClick={handleStart}
              disabled={starting || running}
              sx={{ height: 40 }}
            >
              {running ? "بکاپ در حال ساخت…" : "ساخت بکاپ الان"}
            </Button>
            <FormControlLabel
              control={<Checkbox checked={sendToDestinations} onChange={(e) => setSendToDestinations(e.target.checked)} />}
              label="ارسال به مقصدهای فعال (SMB/FTP/ایمیل)"
            />
          </Stack>
          {startMsg && <Alert severity={startMsg.ok ? "info" : "error"} sx={{ mt: 1.5 }}>{startMsg.text}</Alert>}

          <Divider sx={{ my: 2.5 }} />
          <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
            نسخه‌های روی سرور
          </Typography>
          <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 1 }}>
            دو نسخه‌ی آخر روی خود سرور (/var/lib/faipco/backups) نگه داشته می‌شود. فایل بکاپ دیگری را هم می‌توانید با SCP در همان
            پوشه بگذارید تا این‌جا برای بازیابی نمایش داده شود. دانلود دستی، مقصد مستقل خودکار محسوب نمی‌شود.
          </Typography>
          {overview?.local?.length ? (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>فایل</TableCell>
                    <TableCell>زمان</TableCell>
                    <TableCell>حجم</TableCell>
                    <TableCell>نوع</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {overview.local.map((f) => (
                    <TableRow key={f.name}>
                      <TableCell dir="ltr" sx={{ fontFamily: "monospace", fontSize: 12 }}>{f.name}</TableCell>
                      <TableCell>{fmtDate(f.created_at)}</TableCell>
                      <TableCell>{fmtBytes(f.size)}</TableCell>
                      <TableCell>{KIND[f.kind] || f.kind}</TableCell>
                      <TableCell align="left" sx={{ whiteSpace: "nowrap" }}>
                        {can.download && (
                          <Tooltip title="دانلود">
                            <span>
                              <IconButton size="small" onClick={() => handleDownload(f.name)} disabled={downloading === f.name}>
                                {downloading === f.name ? <CircularProgress size={16} /> : <DownloadOutlinedIcon fontSize="small" />}
                              </IconButton>
                            </span>
                          </Tooltip>
                        )}
                        {can.restore && f.kind !== "v3" && (
                          <Tooltip title="بازیابی">
                            <span>
                              <IconButton size="small" color="error" onClick={() => setRestoreTarget(f)} disabled={isRestoring}>
                                <RestoreOutlinedIcon fontSize="small" />
                              </IconButton>
                            </span>
                          </Tooltip>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Typography variant="body2" color="text.secondary">هنوز نسخه‌ای روی سرور نیست.</Typography>
          )}

          <Divider sx={{ my: 2.5 }} />
          <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
            تاریخچه‌ی بکاپ
          </Typography>
          {overview?.runs?.length ? (
            <TableContainer sx={{ maxHeight: 360 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>زمان</TableCell>
                    <TableCell>نوع</TableCell>
                    <TableCell>وضعیت</TableCell>
                    <TableCell>حجم</TableCell>
                    <TableCell>فایل‌ها</TableCell>
                    <TableCell>مقصدها</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {overview.runs.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>{fmtDate(r.started_at)}</TableCell>
                      <TableCell>{TRIGGER[r.trigger] || r.trigger}</TableCell>
                      <TableCell>
                        <Tooltip title={r.message || ""}>
                          <Chip size="small" color={STATUS[r.status]?.color || "default"} label={STATUS[r.status]?.label || r.status} />
                        </Tooltip>
                      </TableCell>
                      <TableCell>{fmtBytes(r.size)}</TableCell>
                      <TableCell>{r.file_count != null ? toPersianDigits(r.file_count) : "—"}</TableCell>
                      <TableCell>
                        {r.destinations && Object.keys(r.destinations).length
                          ? Object.entries(r.destinations).map(([k, v]) => (
                              <Tooltip key={k} title={v.message}>
                                <Chip size="small" variant="outlined" color={v.ok ? "success" : "error"}
                                  label={{ smb: "SMB", ftp: "FTP", email: "ایمیل" }[k] || k} sx={{ ml: 0.5 }} />
                              </Tooltip>
                            ))
                          : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Typography variant="body2" color="text.secondary">هنوز بکاپی با قالب جدید ساخته نشده است.</Typography>
          )}
        </Card>
      )}

      {can.run && (
        <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
          <BackupKeyCard canManage={can.keys} onChanged={loadOverview} />
        </Card>
      )}

      {can.restore && (
        <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3, borderColor: "error.main" }}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
            <WarningAmberOutlinedIcon color="error" fontSize="small" />
            <Typography variant="subtitle2" fontWeight={700} color="error.main">
              بازیابی از فایل بکاپ قدیمی (zip)
            </Typography>
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            فقط برای بکاپ‌های قالب قبلی (فقط دیتابیس، بدون فایل‌های اتوماسیون). بکاپ‌های جدید را از «نسخه‌های روی سرور» بازیابی
            کنید. حجم فایل محدود به سقف آپلود سرور است.
          </Typography>
          <Stack spacing={2}>
            <Button component="label" variant="outlined" startIcon={<CloudUploadOutlinedIcon />} disabled={isRestoring}>
              {restoreFile ? restoreFile.name : "انتخاب فایل بکاپ (zip)"}
              <input type="file" accept=".zip,application/zip" hidden onChange={(e) => setRestoreFile(e.target.files?.[0] || null)} />
            </Button>
            <TextField
              label={`برای تأیید، دقیقاً «${CONFIRM_PHRASE}» را تایپ کنید`}
              value={legacyConfirm}
              onChange={(e) => setLegacyConfirm(e.target.value)}
              disabled={isRestoring}
              inputProps={{ dir: "ltr", style: { textAlign: "center", fontFamily: "monospace", letterSpacing: 2 } }}
            />
            <Box>
              <Button
                variant="contained"
                color="error"
                startIcon={<WarningAmberOutlinedIcon />}
                onClick={handleRestoreLegacy}
                disabled={isRestoring || legacyConfirm !== CONFIRM_PHRASE || !restoreFile}
              >
                بازیابی و جایگزینی کامل داده
              </Button>
            </Box>
          </Stack>
        </Card>
      )}

      {can.cache && (
        <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
          <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1 }}>
            پاک‌کردن کش اپلیکیشن برای همه کاربران
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            اپ در بازدید بعدی هر کاربر تازه بارگذاری می‌شود؛ داده‌ای پاک نمی‌شود. برای وقتی که آیکون یا صفحه‌ی قدیمی روی گوشی
            کسی مانده است.
          </Typography>
          {cacheBustResult && (
            <Alert severity={cacheBustResult.success ? "success" : "error"} sx={{ mb: 2 }}>{cacheBustResult.message}</Alert>
          )}
          <Button
            variant="outlined"
            startIcon={isBustingCache ? <CircularProgress size={18} /> : <DeleteSweepOutlinedIcon />}
            onClick={handleBustCache}
            disabled={isBustingCache}
          >
            {isBustingCache ? "در حال اعمال..." : "پاک‌کردن کش برای همه کاربران"}
          </Button>
        </Card>
      )}

      {can.destinations && (
        <Card variant="outlined" sx={{ p: 3, mb: 3 }}>
          <BackupScheduleSettings />
        </Card>
      )}

      <Dialog open={Boolean(restoreTarget)} onClose={() => setRestoreTarget(null)} maxWidth="sm" fullWidth>
        <DialogTitle>بازیابی از {restoreTarget?.name}</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            همه‌ی داده‌های فعلی دیتابیس و فایل‌های اتوماسیون با محتوای این بکاپ جایگزین می‌شود. اول فایل کامل بررسی می‌شود
            (رمزگشایی و تطبیق همه‌ی هش‌ها)؛ اگر سالم نبود هیچ تغییری داده نمی‌شود. اگر جایگزینی شکست بخورد، داده و فایل‌های قبلی
            برمی‌گردند.
          </Alert>
          <Stack spacing={2}>
            {restoreTarget?.kind === "v4-encrypted" && (
              <TextField
                label="کلید خصوصی (فقط اگر کلید بیرون از سرور است)"
                helperText="برای کلید «محافظت‌شده روی سرور» خالی بگذارید."
                value={privateKey}
                onChange={(e) => setPrivateKey(e.target.value)}
                multiline
                minRows={2}
                inputProps={{ dir: "ltr", style: { fontFamily: "monospace", fontSize: 13 } }}
              />
            )}
            <TextField
              label={`برای تأیید، دقیقاً «${CONFIRM_PHRASE}» را تایپ کنید`}
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              inputProps={{ dir: "ltr", style: { textAlign: "center", fontFamily: "monospace", letterSpacing: 2 } }}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRestoreTarget(null)}>انصراف</Button>
          <Button variant="contained" color="error" onClick={handleRestoreLocal} disabled={confirmText !== CONFIRM_PHRASE}>
            بازیابی
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
