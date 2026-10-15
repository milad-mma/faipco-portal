/**
 * دیالوگ «دستگاه‌های من» (پنل کاربری): فهرست دستگاه‌هایی که با حساب کاربر جاری وارد شده‌اند،
 * با امکان خروج از راه دور یک دستگاه یا همه‌ی دستگاه‌های دیگر. دستگاه جاری قابل خروج نیست.
 * ورودی: open، onClose.
 */
import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import DevicesOutlinedIcon from "@mui/icons-material/DevicesOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import {
  fetchMySessions,
  revokeMySession,
  revokeOtherSessions,
  setMySessionLimit,
} from "../api/auth";
import { errText, formatDateTime } from "./loans/LoanShared";
import ResultDialog from "./ResultDialog";
import { monoFontSx } from "../theme";

export default function MyDevicesDialog({ open, onClose }) {
  const [data, setData] = useState(null); // { items, max_sessions } یا null = در حال بارگذاری
  const [savingLimit, setSavingLimit] = useState(false);
  const saveLimit = async (n) => {
    setSavingLimit(true);
    try {
      const res = await setMySessionLimit(n);
      setData((d) => (d ? { ...d, max_sessions: res.max_sessions } : d));
    } catch (e) {
      setResult({
        severity: "error",
        text: errText(e, "ذخیره‌ی سقف دستگاه ناموفق بود"),
      });
    } finally {
      setSavingLimit(false);
    }
  };
  const [loadError, setLoadError] = useState("");
  const [confirm, setConfirm] = useState(null); // { id } برای یک دستگاه یا { all: true } برای همه‌ی دیگران؛ null = بسته
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const load = useCallback(async () => {
    setLoadError("");
    try {
      setData(await fetchMySessions());
    } catch (err) {
      setLoadError(errText(err, "دریافت فهرست دستگاه‌ها ناموفق بود."));
    }
  }, []);

  // هر بار باز شدن دیالوگ فهرست تازه خوانده می‌شود
  useEffect(() => {
    if (!open) return;
    setData(null);
    load();
  }, [open, load]);

  const items = data?.items || [];
  const others = items.filter((s) => !s.current);

  async function handleConfirm() {
    if (!confirm) return;
    setBusy(true);
    try {
      if (confirm.all) await revokeOtherSessions();
      else await revokeMySession(confirm.id);
      setConfirm(null);
      setResult({
        severity: "success",
        text: confirm.all
          ? "از همه‌ی دستگاه‌های دیگر خارج شدید."
          : "دستگاه از حساب شما خارج شد.",
      });
      await load();
    } catch (err) {
      setConfirm(null);
      setResult({
        severity: "error",
        text: errText(err, "خروج از دستگاه ناموفق بود."),
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
        <DialogTitle>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <DevicesOutlinedIcon color="primary" />
            <span>دستگاه‌های من</span>
          </Stack>
        </DialogTitle>
        <DialogContent>
          {data?.max_sessions && (
            <Stack
              direction="row"
              spacing={1.5}
              alignItems="flex-end"
              sx={{ mb: 1.5 }}
              flexWrap="wrap"
              useFlexGap
            >
              {/* هر کاربر سقف دستگاه‌های هم‌زمان خودش را تعیین می‌کند؛ از ورود بعدی اعمال می‌شود */}
              <TextField
                select
                size="small"
                label="حداکثر دستگاه هم‌زمان من"
                value={data.max_sessions}
                disabled={savingLimit}
                onChange={(e) => saveLimit(Number(e.target.value))}
                sx={{ minWidth: 200 }}
              >
                {[1, 2, 3].map((n) => (
                  <MenuItem key={n} value={n}>
                    {n.toLocaleString("fa-IR")} دستگاه
                  </MenuItem>
                ))}
              </TextField>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ pb: 1 }}
              >
                با ورود دستگاه جدید بیش از این تعداد، قدیمی‌ترین دستگاه خارج
                می‌شود.
              </Typography>
            </Stack>
          )}
          {loadError && (
            <Alert severity="error" sx={{ mb: 1.5 }}>
              {loadError}
            </Alert>
          )}
          {data === null && !loadError ? (
            <Box sx={{ py: 3, textAlign: "center" }}>
              <CircularProgress size={24} />
            </Box>
          ) : (
            <Stack divider={<Divider />} spacing={1.5}>
              {items.map((s) => (
                <Stack
                  key={s.id}
                  direction="row"
                  spacing={1.5}
                  alignItems="center"
                  justifyContent="space-between"
                >
                  <Box sx={{ minWidth: 0 }}>
                    <Stack
                      direction="row"
                      spacing={1}
                      alignItems="center"
                      flexWrap="wrap"
                      useFlexGap
                    >
                      <Typography variant="body2" fontWeight={700}>
                        {s.device || "دستگاه نامشخص"}
                      </Typography>
                      {s.current && (
                        <Chip size="small" color="success" label="این دستگاه" />
                      )}
                      {s.client_app === "android" && (
                        <Chip
                          size="small"
                          variant="outlined"
                          label="اپ اندروید"
                        />
                      )}
                    </Stack>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: "block", mt: 0.5 }}
                    >
                      IP:{" "}
                      <Box component="span" sx={monoFontSx}>
                        {s.ip || "—"}
                      </Box>
                    </Typography>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: "block" }}
                    >
                      ورود: {formatDateTime(s.created_at)} — آخرین فعالیت:{" "}
                      {formatDateTime(s.last_seen_at)}
                    </Typography>
                  </Box>
                  {!s.current && (
                    <Button
                      size="small"
                      color="error"
                      startIcon={<LogoutOutlinedIcon />}
                      onClick={() => setConfirm({ id: s.id })}
                      sx={{ flexShrink: 0 }}
                    >
                      خروج
                    </Button>
                  )}
                </Stack>
              ))}
              {data !== null && items.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  دستگاهی ثبت نشده است.
                </Typography>
              )}
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2.5, justifyContent: "space-between" }}>
          {/* فقط وقتی بیش از یک دستگاه (یعنی دستگاه دیگری جز این) هست */}
          {others.length > 0 ? (
            <Button
              color="error"
              startIcon={<LogoutOutlinedIcon />}
              onClick={() => setConfirm({ all: true })}
            >
              خروج از همه‌ی دستگاه‌های دیگر
            </Button>
          ) : (
            <span />
          )}
          <Button onClick={onClose}>بستن</Button>
        </DialogActions>
      </Dialog>

      {/* تأیید خروج از راه دور (یک دستگاه یا همه‌ی دیگران) */}
      <Dialog
        open={Boolean(confirm)}
        onClose={() => !busy && setConfirm(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>
          {confirm?.all
            ? "خروج از همه‌ی دستگاه‌های دیگر"
            : "خروج از این دستگاه"}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            {confirm?.all
              ? "همه‌ی دستگاه‌های دیگر از حساب شما خارج می‌شوند و باید دوباره وارد شوند. ادامه می‌دهید؟"
              : "این دستگاه از حساب شما خارج می‌شود و برای استفاده باید دوباره وارد شود. ادامه می‌دهید؟"}
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2.5 }}>
          <Button onClick={() => setConfirm(null)} disabled={busy}>
            انصراف
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleConfirm}
            disabled={busy}
            startIcon={
              busy ? <CircularProgress size={16} color="inherit" /> : null
            }
          >
            خروج
          </Button>
        </DialogActions>
      </Dialog>

      <ResultDialog result={result} onClose={() => setResult(null)} />
    </>
  );
}
