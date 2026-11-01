// مقصدهای بکاپ «پوشه/دیسک محلی»، «SFTP» و «فضای ابری S3» داخل تنظیمات زمان‌بندی بکاپ (BackupScheduleSettings).
// فرم در والد نگه داشته می‌شود (form/updateForm)؛ این کامپوننت فقط فیلدها و دکمه‌های تست را رسم می‌کند.
// SFTP: «تست اتصال» کلید سرور را برمی‌گرداند؛ با «ذخیره تنظیمات» ثبت می‌شود و از آن به بعد اتصال با کلید دیگر رد می‌شود.
import { useState } from "react";
import { Alert, Box, Button, Checkbox, CircularProgress, Divider, FormControlLabel, Stack, TextField, Typography } from "@mui/material";
import { testBackupDestination } from "../api/backup";

const fieldSx = { minWidth: 200 };

function TestButton({ label, onClick, busy, disabled }) {
  return (
    <Box>
      <Button
        variant="outlined"
        onClick={onClick}
        disabled={busy || disabled}
        startIcon={busy ? <CircularProgress size={14} /> : null}
        sx={{ height: 40 }}
      >
        {label}
      </Button>
    </Box>
  );
}

export default function BackupExtraDestinations({ form, settings, updateForm }) {
  const [busy, setBusy] = useState(null); // "local" | "sftp" | "s3" | null
  const [results, setResults] = useState({}); // { kind: { success, message } }

  async function runTest(kind, payload, onOk) {
    setBusy(kind);
    setResults((r) => ({ ...r, [kind]: null }));
    try {
      const data = await testBackupDestination(kind, payload);
      setResults((r) => ({ ...r, [kind]: { success: true, message: data.message } }));
      onOk?.(data);
    } catch (err) {
      setResults((r) => ({ ...r, [kind]: { success: false, message: err.response?.data?.detail || "تست ناموفق بود." } }));
    } finally {
      setBusy(null);
    }
  }

  const result = (kind) =>
    results[kind] && <Alert severity={results[kind].success ? "success" : "error"}>{results[kind].message}</Alert>;

  return (
    <>
      {/* پوشه یا دیسک متصل به همین سرور */}
      <Stack spacing={2}>
        <FormControlLabel
          control={<Checkbox checked={Boolean(form.local_enabled)} onChange={(e) => updateForm({ local_enabled: e.target.checked })} />}
          label="ذخیره‌ی بکاپ در یک پوشه یا دیسک متصل به همین سرور"
        />
        {form.local_enabled && (
          <Stack spacing={2} sx={{ pr: 3 }}>
            <TextField
              size="small"
              label="مسیر پوشه روی سرور"
              value={form.local_path || ""}
              onChange={(e) => updateForm({ local_path: e.target.value })}
              placeholder="/mnt/backup/faipco"
              inputProps={{ dir: "ltr" }}
              sx={{ maxWidth: 360 }}
              helperText="مثلاً یک دیسک دوم یا هارد شبکه که روی سرور Mount شده است. پرتال باید اجازه‌ی نوشتن در آن را داشته باشد."
            />
            {result("local")}
            <TestButton
              label="تست نوشتن در پوشه"
              busy={busy === "local"}
              disabled={!form.local_path}
              onClick={() => runTest("local", { local_path: form.local_path })}
            />
          </Stack>
        )}
      </Stack>

      <Divider />

      {/* SFTP */}
      <Stack spacing={2}>
        <FormControlLabel
          control={<Checkbox checked={Boolean(form.sftp_enabled)} onChange={(e) => updateForm({ sftp_enabled: e.target.checked })} />}
          label="ارسال بکاپ به سرور SFTP"
        />
        {form.sftp_enabled && (
          <Stack spacing={2} sx={{ pr: 3 }}>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              <TextField size="small" label="آدرس سرور (Host)" value={form.sftp_host || ""}
                onChange={(e) => updateForm({ sftp_host: e.target.value, sftp_host_key: "", sftp_fingerprint: "" })} inputProps={{ dir: "ltr" }} sx={fieldSx} />
              <TextField size="small" type="number" label="پورت" value={form.sftp_port ?? 22}
                onChange={(e) => updateForm({ sftp_port: Number(e.target.value), sftp_host_key: "", sftp_fingerprint: "" })} sx={{ width: 110 }} />
              <TextField size="small" label="مسیر (اختیاری)" value={form.sftp_path || ""}
                onChange={(e) => updateForm({ sftp_path: e.target.value })} placeholder="backups/faipco"
                inputProps={{ dir: "ltr" }} sx={fieldSx} />
            </Stack>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              <TextField size="small" label="نام کاربری" value={form.sftp_username || ""}
                onChange={(e) => updateForm({ sftp_username: e.target.value })} inputProps={{ dir: "ltr" }} sx={{ minWidth: 160 }} />
              <TextField size="small" type="password" label="رمز عبور" value={form.sftp_password || ""}
                onChange={(e) => updateForm({ sftp_password: e.target.value })}
                placeholder={settings?.sftp_has_password ? "برای حفظ رمز قبلی خالی بگذارید" : ""} sx={fieldSx} />
            </Stack>
            <Typography variant="caption" color="text.secondary">
              {form.sftp_host_key
                ? `کلید سرور ${form.sftp_host_key === settings?.sftp_host_key ? "ثبت‌شده" : "(تازه؛ با ذخیره ثبت می‌شود)"}: ${form.sftp_fingerprint || ""}`
                : "کلید امنیتی سرور هنوز ثبت نشده؛ «تست اتصال SFTP» را بزنید و بعد «ذخیره تنظیمات»."}
            </Typography>
            {results.sftp && !results.sftp.success && String(results.sftp.message).includes("کلید") && (
              <FormControlLabel
                control={<Checkbox checked={Boolean(form.sftp_accept_new_key)} onChange={(e) => updateForm({ sftp_accept_new_key: e.target.checked })} />}
                label="سرور را عوض کرده‌ام؛ کلید جدید پذیرفته شود"
              />
            )}
            {result("sftp")}
            <TestButton
              label="تست اتصال SFTP"
              busy={busy === "sftp"}
              disabled={!form.sftp_host || !form.sftp_username}
              onClick={() =>
                runTest(
                  "sftp",
                  {
                    sftp_host: form.sftp_host,
                    sftp_port: form.sftp_port,
                    sftp_username: form.sftp_username,
                    sftp_password: form.sftp_password || undefined,
                    sftp_path: form.sftp_path,
                    sftp_host_key: form.sftp_host_key || undefined,
                    sftp_accept_new_key: Boolean(form.sftp_accept_new_key),
                  },
                  (data) => updateForm({ sftp_host_key: data.host_key, sftp_fingerprint: data.fingerprint, sftp_accept_new_key: false }),
                )
              }
            />
          </Stack>
        )}
      </Stack>

      <Divider />

      {/* S3 و سرویس‌های سازگار */}
      <Stack spacing={2}>
        <FormControlLabel
          control={<Checkbox checked={Boolean(form.s3_enabled)} onChange={(e) => updateForm({ s3_enabled: e.target.checked })} />}
          label="ارسال بکاپ به فضای ابری S3 (یا سرویس سازگار مثل MinIO و ابر آروان)"
        />
        {form.s3_enabled && (
          <Stack spacing={2} sx={{ pr: 3 }}>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              <TextField size="small" label="آدرس سرویس (Endpoint)" value={form.s3_endpoint || ""}
                onChange={(e) => updateForm({ s3_endpoint: e.target.value })} placeholder="https://s3.example.com"
                inputProps={{ dir: "ltr" }} sx={{ minWidth: 260 }} />
              <TextField size="small" label="Region (اختیاری)" value={form.s3_region || ""}
                onChange={(e) => updateForm({ s3_region: e.target.value })} placeholder="us-east-1"
                inputProps={{ dir: "ltr" }} sx={{ width: 160 }} />
            </Stack>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              <TextField size="small" label="نام Bucket" value={form.s3_bucket || ""}
                onChange={(e) => updateForm({ s3_bucket: e.target.value })} inputProps={{ dir: "ltr" }} sx={fieldSx} />
              <TextField size="small" label="پوشه داخل Bucket (اختیاری)" value={form.s3_prefix || ""}
                onChange={(e) => updateForm({ s3_prefix: e.target.value })} placeholder="faipco"
                inputProps={{ dir: "ltr" }} sx={fieldSx} />
            </Stack>
            <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
              <TextField size="small" label="Access Key" value={form.s3_access_key || ""}
                onChange={(e) => updateForm({ s3_access_key: e.target.value })} inputProps={{ dir: "ltr" }} sx={fieldSx} />
              <TextField size="small" type="password" label="Secret Key" value={form.s3_secret_key || ""}
                onChange={(e) => updateForm({ s3_secret_key: e.target.value })}
                placeholder={settings?.s3_has_secret ? "برای حفظ کلید قبلی خالی بگذارید" : ""} sx={fieldSx} />
            </Stack>
            <FormControlLabel
              control={<Checkbox checked={form.s3_path_style !== false} onChange={(e) => updateForm({ s3_path_style: e.target.checked })} />}
              label="آدرس‌دهی مسیری (Path-style) — برای MinIO و بیشتر سرویس‌های داخلی روشن بماند"
            />
            {result("s3")}
            <TestButton
              label="تست اتصال S3"
              busy={busy === "s3"}
              disabled={!form.s3_endpoint || !form.s3_bucket || !form.s3_access_key}
              onClick={() =>
                runTest("s3", {
                  s3_endpoint: form.s3_endpoint,
                  s3_region: form.s3_region,
                  s3_bucket: form.s3_bucket,
                  s3_prefix: form.s3_prefix,
                  s3_access_key: form.s3_access_key,
                  s3_secret_key: form.s3_secret_key || undefined,
                  s3_path_style: form.s3_path_style !== false,
                })
              }
            />
          </Stack>
        )}
      </Stack>
    </>
  );
}
