/**
 * کارت «کلید رمزنگاری بکاپ» (docs/backup.md؛ سند اتوماسیون بخش ۱۰.۴).
 * - نمایش کلید فعال (حالت، اثرانگشت، تاریخ) و کلیدهای قدیمی‌تر.
 * - ساخت کلید تازه (backup.key_manage): «کلید بیرون از سرور» — کلید خصوصی فقط یک بار نمایش داده می‌شود؛ یا «کلید محافظت‌شده
 *   روی سرور» — بازیابی بدون ورود کلید، بدون جداسازی اختیار.
 * - بسته‌ی امن کلید با عبارت عبور (حالت دوم) و وارد کردن آن روی سرور جایگزین.
 */
import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import KeyOutlinedIcon from "@mui/icons-material/KeyOutlined";
import { createBackupKey, exportKeyPackage, fetchBackupKeys, importKeyPackage } from "../api/backup";
import { saveBlob } from "../utils/family";

function errorText(err, fallback) {
  const detail = err?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

async function blobErrorText(err, fallback) {
  try {
    const text = await err.response.data.text();
    return JSON.parse(text).detail || fallback;
  } catch {
    return errorText(err, fallback);
  }
}

function fmtDate(v) {
  return v ? new Date(v).toLocaleString("fa-IR", { dateStyle: "short", timeStyle: "short" }) : "—";
}

const MODE_HELP = {
  external:
    "کلید خصوصی فقط همین یک بار نمایش داده می‌شود و روی سرور ذخیره نمی‌شود؛ هنگام بازیابی باید آن را وارد کنید. مدیر فنی بدون این کلید نمی‌تواند محتوای بکاپ را بخواند. اگر کلید گم شود، بکاپ‌های آن غیرقابل بازیابی‌اند.",
  server_protected:
    "کلید خصوصی رمزنگاری‌شده روی همین سرور ذخیره می‌شود و بازیابی از پنل بدون ورود کلید انجام می‌شود. جداسازی اختیار فراهم نیست: هر کس به سرور و تنظیمات آن دسترسی مستقیم داشته باشد می‌تواند محتوای بکاپ را بخواند. برای خرابی کامل سرور، «بسته‌ی امن کلید» را بگیرید و جای امن نگه دارید.",
};

export default function BackupKeyCard({ canManage, onChanged }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState(null); // "create" | "package" | "import"
  const [mode, setMode] = useState("external");
  const [privateKeyOnce, setPrivateKeyOnce] = useState("");
  const [saved, setSaved] = useState(false);
  const [passphrase, setPassphrase] = useState("");
  const [importFile, setImportFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState("");

  const load = useCallback(() => {
    fetchBackupKeys()
      .then(setData)
      .catch((err) => setError(errorText(err, "دریافت کلیدها با خطا مواجه شد.")));
  }, []);
  useEffect(load, [load]);

  function close() {
    if (privateKeyOnce && !saved) return; // تا تأیید ذخیره، پنجره بسته نمی‌شود
    setDialog(null);
    setPrivateKeyOnce("");
    setSaved(false);
    setPassphrase("");
    setImportFile(null);
    setDialogError("");
  }

  async function handleCreate() {
    setBusy(true);
    setDialogError("");
    try {
      const row = await createBackupKey(mode);
      if (row.private_key_once) setPrivateKeyOnce(row.private_key_once);
      else setDialog(null);
      load();
      onChanged?.();
    } catch (err) {
      setDialogError(errorText(err, "ساخت کلید با خطا مواجه شد."));
    } finally {
      setBusy(false);
    }
  }

  async function handlePackage() {
    setBusy(true);
    setDialogError("");
    try {
      const blob = await exportKeyPackage(passphrase);
      saveBlob(blob, `faipco-backup-key-${data.keys.find((k) => k.active)?.key_id || "key"}.json`);
      close();
    } catch (err) {
      setDialogError(await blobErrorText(err, "ساخت بسته‌ی کلید با خطا مواجه شد."));
    } finally {
      setBusy(false);
    }
  }

  async function handleImport() {
    setBusy(true);
    setDialogError("");
    try {
      await importKeyPackage(importFile, passphrase, "server_protected");
      close();
      load();
      onChanged?.();
    } catch (err) {
      setDialogError(errorText(err, "وارد کردن کلید با خطا مواجه شد."));
    } finally {
      setBusy(false);
    }
  }

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!data) return <CircularProgress size={22} />;
  const active = data.keys.find((k) => k.active);
  const old = data.keys.filter((k) => !k.active);

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
        <KeyOutlinedIcon fontSize="small" />
        <Typography variant="subtitle1" fontWeight={700}>
          کلید رمزنگاری بکاپ
        </Typography>
      </Stack>
      {!data.age_available && (
        <Alert severity="warning" sx={{ mb: 1.5 }}>
          ابزار age روی سرور نصب نیست؛ تا یک بار آپدیت پرتال، کلید ساخته نمی‌شود و بکاپ‌ها رمزنگاری نمی‌شوند.
        </Alert>
      )}
      {active ? (
        <Stack spacing={0.5} sx={{ mb: 1.5 }}>
          <Typography variant="body2">
            کلید فعال: <Chip size="small" label={active.mode_label} color="success" variant="outlined" /> — اثرانگشت{" "}
            <Box component="span" dir="ltr" sx={{ fontFamily: "monospace" }}>{active.key_id}</Box> — ساخته‌شده {fmtDate(active.created_at)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {MODE_HELP[active.mode]}
          </Typography>
        </Stack>
      ) : (
        <Alert severity="warning" sx={{ mb: 1.5 }}>
          هیچ کلیدی ساخته نشده است؛ بکاپ‌ها بدون رمزنگاری ساخته می‌شوند.
        </Alert>
      )}
      {old.length > 0 && (
        <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 1.5 }}>
          کلیدهای قبلی (برای بازیابی بکاپ‌های قدیمی نگه داشته شده‌اند):{" "}
          {old.map((k) => `${k.key_id} (${k.mode_label}${k.has_server_copy ? "" : "، بدون نسخه روی سرور"})`).join("، ")}
        </Typography>
      )}
      {canManage && (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <Button variant="contained" onClick={() => setDialog("create")} disabled={!data.age_available} sx={{ height: 40 }}>
            {active ? "ساخت کلید تازه (چرخش)" : "ساخت کلید"}
          </Button>
          {active?.has_server_copy && (
            <Button variant="outlined" onClick={() => setDialog("package")} sx={{ height: 40 }}>
              بسته‌ی امن کلید
            </Button>
          )}
          <Button variant="text" onClick={() => setDialog("import")} disabled={!data.age_available} sx={{ height: 40 }}>
            وارد کردن بسته‌ی کلید
          </Button>
        </Stack>
      )}

      <Dialog open={dialog === "create"} onClose={close} maxWidth="sm" fullWidth>
        <DialogTitle>{privateKeyOnce ? "کلید خصوصی را ذخیره کنید" : "ساخت کلید رمزنگاری"}</DialogTitle>
        <DialogContent>
          {privateKeyOnce ? (
            <Stack spacing={1.5} sx={{ mt: 1 }}>
              <Alert severity="error">
                این کلید فقط همین یک بار نمایش داده می‌شود و روی سرور ذخیره نشده است. بدون آن، بکاپ‌های ساخته‌شده با این کلید قابل
                بازیابی نیستند. آن را دانلود کنید و جای امن (بیرون از این سرور) نگه دارید.
              </Alert>
              <Box component="pre" dir="ltr" sx={{ p: 1.5, bgcolor: "action.hover", borderRadius: 1, fontSize: 13, wordBreak: "break-all", whiteSpace: "pre-wrap", m: 0 }}>
                {privateKeyOnce}
              </Box>
              <Button
                variant="outlined"
                onClick={() => saveBlob(new Blob([`${privateKeyOnce}\n`], { type: "text/plain" }), "faipco-backup-key.txt")}
              >
                دانلود کلید
              </Button>
              <FormControlLabel
                control={<Checkbox checked={saved} onChange={(e) => setSaved(e.target.checked)} />}
                label="کلید را در جای امن ذخیره کردم"
              />
            </Stack>
          ) : (
            <Stack spacing={1.5} sx={{ mt: 1 }}>
              <TextField select size="small" label="حالت کلید" value={mode} onChange={(e) => setMode(e.target.value)}>
                <MenuItem value="external">کلید بیرون از سرور (امن‌تر)</MenuItem>
                <MenuItem value="server_protected">کلید محافظت‌شده روی سرور (راحت‌تر)</MenuItem>
              </TextField>
              <Typography variant="body2" color="text.secondary">
                {MODE_HELP[mode]}
              </Typography>
              {active && (
                <Alert severity="info">
                  کلید فعلی کنار گذاشته می‌شود ولی حذف نمی‌شود؛ بکاپ‌های قبلی همچنان با همان کلید بازیابی می‌شوند.
                </Alert>
              )}
              {dialogError && <Alert severity="error">{dialogError}</Alert>}
            </Stack>
          )}
        </DialogContent>
        <DialogActions>
          {privateKeyOnce ? (
            <Button variant="contained" disabled={!saved} onClick={close}>
              بستن
            </Button>
          ) : (
            <>
              <Button onClick={close}>انصراف</Button>
              <Button variant="contained" onClick={handleCreate} disabled={busy}>
                ساخت و فعال کردن
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>

      <Dialog open={dialog === "package"} onClose={close} maxWidth="xs" fullWidth>
        <DialogTitle>بسته‌ی امن کلید</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            کلید خصوصی با یک عبارت عبور رمزنگاری و دانلود می‌شود. برای خرابی کامل سرور، فایل و عبارت عبور را جدا از هم و بیرون
            از سرور نگه دارید.
          </Typography>
          <TextField fullWidth type="password" size="small" label="عبارت عبور (حداقل ۱۲ نویسه)" value={passphrase}
            onChange={(e) => setPassphrase(e.target.value)} />
          {dialogError && <Alert severity="error" sx={{ mt: 1.5 }}>{dialogError}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={close}>انصراف</Button>
          <Button variant="contained" onClick={handlePackage} disabled={busy || passphrase.length < 12}>
            دانلود بسته
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={dialog === "import"} onClose={close} maxWidth="xs" fullWidth>
        <DialogTitle>وارد کردن بسته‌ی کلید</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            برای سرور جایگزین: بسته‌ی امن کلید را وارد کنید تا بکاپ‌های آن کلید از پنل قابل بازیابی شوند. کلید به‌عنوان «کلید
            محافظت‌شده روی سرور» فعال می‌شود.
          </Typography>
          <Stack spacing={1.5}>
            <Button component="label" variant="outlined">
              {importFile ? importFile.name : "انتخاب فایل بسته (json)"}
              <input hidden type="file" accept=".json,application/json" onChange={(e) => setImportFile(e.target.files?.[0] || null)} />
            </Button>
            <TextField type="password" size="small" label="عبارت عبور" value={passphrase} onChange={(e) => setPassphrase(e.target.value)} />
            {dialogError && <Alert severity="error">{dialogError}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={close}>انصراف</Button>
          <Button variant="contained" onClick={handleImport} disabled={busy || !importFile || !passphrase}>
            وارد کردن
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
