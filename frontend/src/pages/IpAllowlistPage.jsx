import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Checkbox,
  CircularProgress,
  Divider,
  IconButton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import ContentPasteSearchOutlinedIcon from "@mui/icons-material/ContentPasteSearchOutlined";
import WifiOffOutlinedIcon from "@mui/icons-material/WifiOffOutlined";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import {
  addIpAllowlistEntry,
  bulkAddIpAllowlist,
  deleteIpAllowlistEntry,
  extractIpAllowlistCandidates,
  fetchIpAllowlist,
  fetchIpBlockedMessage,
  updateIpBlockedMessage,
} from "../api/system";
import { monoFontSx } from "../theme";

export default function IpAllowlistPage() {
  const [entries, setEntries] = useState(null);
  const [cidr, setCidr] = useState("");
  const [label, setLabel] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  // --- افزودن دسته‌ای از متن (Paste از فایل txt یا لاگ) ---
  const [bulkText, setBulkText] = useState("");
  const [bulkLabel, setBulkLabel] = useState("");
  const [candidates, setCandidates] = useState(null); // null یعنی هنوز استخراج نشده
  const [checkedCidrs, setCheckedCidrs] = useState(new Set());
  const [isExtracting, setIsExtracting] = useState(false);
  const [isBulkSaving, setIsBulkSaving] = useState(false);
  const [bulkResult, setBulkResult] = useState(null);
  const [bulkError, setBulkError] = useState("");

  // --- پیام نمایش‌داده‌شده به کاربر مسدودشده ---
  const [message, setMessage] = useState(null);
  const [isSavingMessage, setIsSavingMessage] = useState(false);
  const [messageResult, setMessageResult] = useState(null);

  function load() {
    fetchIpAllowlist().then(setEntries);
  }

  useEffect(() => {
    load();
    fetchIpBlockedMessage().then(setMessage);
  }, []);

  async function handleAdd() {
    setError("");
    if (!cidr.trim()) {
      setError("رنج/IP را وارد کنید.");
      return;
    }
    setIsSaving(true);
    try {
      await addIpAllowlistEntry({ cidr: cidr.trim(), label: label.trim() });
      setCidr("");
      setLabel("");
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "افزودن ناموفق بود.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete(id) {
    if (!window.confirm("این رنج حذف شود؟")) return;
    await deleteIpAllowlistEntry(id);
    load();
  }

  async function handleExtract() {
    setBulkError("");
    setBulkResult(null);
    if (!bulkText.trim()) {
      setBulkError("متنی را که می‌خواهید ازش IP استخراج بشه Paste کنید.");
      return;
    }
    setIsExtracting(true);
    try {
      const found = await extractIpAllowlistCandidates(bulkText);
      setCandidates(found);
      // پیش‌فرض: همه‌ی مواردی که قبلاً ثبت نشده‌اند، تیک‌خورده باشند
      setCheckedCidrs(new Set(found.filter((c) => !c.already_exists).map((c) => c.cidr)));
    } catch (err) {
      setBulkError(err.response?.data?.detail || "استخراج ناموفق بود.");
    } finally {
      setIsExtracting(false);
    }
  }

  function toggleCandidate(cidrValue) {
    setCheckedCidrs((prev) => {
      const next = new Set(prev);
      if (next.has(cidrValue)) next.delete(cidrValue);
      else next.add(cidrValue);
      return next;
    });
  }

  async function handleConfirmBulkAdd() {
    setBulkError("");
    setIsBulkSaving(true);
    try {
      const result = await bulkAddIpAllowlist({ cidrs: Array.from(checkedCidrs), label: bulkLabel.trim() });
      setBulkResult(result);
      setCandidates(null);
      setBulkText("");
      setBulkLabel("");
      load();
    } catch (err) {
      setBulkError(err.response?.data?.detail || "ثبت دسته‌ای ناموفق بود.");
    } finally {
      setIsBulkSaving(false);
    }
  }

  async function handleSaveMessage() {
    setIsSavingMessage(true);
    setMessageResult(null);
    try {
      const saved = await updateIpBlockedMessage(message);
      setMessage(saved);
      setMessageResult({ success: true, text: "ذخیره شد." });
    } catch (err) {
      setMessageResult({ success: false, text: err.response?.data?.detail || "ذخیره ناموفق بود." });
    } finally {
      setIsSavingMessage(false);
    }
  }

  const isEnforced = entries && entries.length > 0;

  return (
    <Box sx={{ maxWidth: 720, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        رنج‌های IP مجاز برای ورود
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        اگر حداقل یک رنج اینجا ثبت کنید، ورود به پرتال فقط از همان رنج‌ها امکان‌پذیر می‌شود — هرکسی
        از بیرون آن‌ها (مثلاً با VPN) بخواهد وارد شود، پیام زیر را می‌بیند.
      </Typography>

      {entries === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          <Alert severity={isEnforced ? "warning" : "info"} sx={{ mb: 3 }}>
            {isEnforced
              ? "این محدودیت الان فعال است — فقط IP های زیر اجازه ورود دارند."
              : "الان هیچ رنجی ثبت نشده، پس این محدودیت غیرفعال است و همه می‌توانند از هر جایی وارد شوند."}
          </Alert>

          {/* ---------- افزودن تکی ---------- */}
          <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2 }}>
              افزودن یک رنج
            </Typography>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            <Stack spacing={2}>
              <TextField
                label="IP یا رنج (CIDR)"
                placeholder="مثال: 203.0.113.5/32 یا 192.168.1.0/24"
                value={cidr}
                onChange={(e) => setCidr(e.target.value)}
                disabled={isSaving}
                sx={{ direction: "ltr", "& input": { textAlign: "left", ...monoFontSx } }}
              />
              <TextField
                label="برچسب (اختیاری)"
                placeholder="مثال: دفتر مرکزی"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                disabled={isSaving}
              />
              <Box>
                <Button
                  variant="contained"
                  startIcon={isSaving ? <CircularProgress size={18} color="inherit" /> : <AddOutlinedIcon />}
                  onClick={handleAdd}
                  disabled={isSaving}
                >
                  افزودن
                </Button>
              </Box>
            </Stack>
          </Card>

          {/* ---------- افزودن دسته‌ای از متن ---------- */}
          <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
              افزودن دسته‌ای از یک متن (Paste از فایل txt یا لاگ)
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              کل محتوای یک فایل (حتی یک لاگ کامل با تاریخ/دستورهای اضافه) را همین‌جا Paste کنید — هر
              چیزی که شبیه IP باشد پیدا می‌شود. چون گاهی چیزهای غیرمرتبط (مثلاً شماره نسخه مرورگر) هم
              ممکن است شبیه IP باشند، قبل از ثبت نهایی، فهرست پیدا‌شده را برای تأیید نشان می‌دهیم.
            </Typography>

            {bulkError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {bulkError}
              </Alert>
            )}
            {bulkResult && (
              <Alert severity="success" sx={{ mb: 2 }}>
                {bulkResult.added_count} مورد اضافه شد
                {bulkResult.duplicate_count > 0 && ` (${bulkResult.duplicate_count} مورد تکراری نادیده گرفته شد)`}.
              </Alert>
            )}

            {candidates === null ? (
              <Stack spacing={2}>
                <TextField
                  label="متن را اینجا Paste کنید"
                  value={bulkText}
                  onChange={(e) => setBulkText(e.target.value)}
                  multiline
                  minRows={5}
                  maxRows={12}
                  disabled={isExtracting}
                  sx={{ direction: "ltr", "& textarea": { textAlign: "left", ...monoFontSx, fontSize: 13 } }}
                />
                <Box>
                  <Button
                    variant="outlined"
                    startIcon={
                      isExtracting ? <CircularProgress size={18} /> : <ContentPasteSearchOutlinedIcon />
                    }
                    onClick={handleExtract}
                    disabled={isExtracting}
                  >
                    استخراج IP ها از متن
                  </Button>
                </Box>
              </Stack>
            ) : (
              <Stack spacing={2}>
                {candidates.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    هیچ IP معتبری در این متن پیدا نشد.
                  </Typography>
                ) : (
                  <>
                    <Stack direction="row" alignItems="center" justifyContent="space-between" flexWrap="wrap" rowGap={1}>
                      <Typography variant="caption" color="text.secondary">
                        {candidates.length} مورد پیدا شد ({checkedCidrs.size} انتخاب‌شده) — موردهایی که از قبل
                        ثبت شده بودند، به‌صورت پیش‌فرض تیک ندارند.
                      </Typography>
                      <Stack direction="row" spacing={1}>
                        <Button
                          size="small"
                          onClick={() => setCheckedCidrs(new Set(candidates.map((c) => c.cidr)))}
                        >
                          انتخاب همه
                        </Button>
                        <Button size="small" onClick={() => setCheckedCidrs(new Set())}>
                          لغو انتخاب همه
                        </Button>
                      </Stack>
                    </Stack>
                    <Card variant="outlined" sx={{ maxHeight: 260, overflowY: "auto" }}>
                      {candidates.map((c, index) => (
                        <Box key={c.cidr}>
                          {index > 0 && <Divider />}
                          <Stack
                            direction="row"
                            alignItems="center"
                            spacing={1}
                            sx={{ px: 1.5, py: 0.5, opacity: c.already_exists ? 0.5 : 1 }}
                          >
                            <Checkbox
                              size="small"
                              checked={checkedCidrs.has(c.cidr)}
                              onChange={() => toggleCandidate(c.cidr)}
                            />
                            <Typography variant="body2" sx={{ ...monoFontSx, direction: "ltr" }}>
                              {c.cidr}
                            </Typography>
                            {c.already_exists && (
                              <Typography variant="caption" color="text.secondary">
                                (از قبل ثبت شده)
                              </Typography>
                            )}
                          </Stack>
                        </Box>
                      ))}
                    </Card>
                    <TextField
                      label="برچسب برای همه موارد انتخاب‌شده (اختیاری)"
                      value={bulkLabel}
                      onChange={(e) => setBulkLabel(e.target.value)}
                      disabled={isBulkSaving}
                    />
                    <Stack direction="row" spacing={1.5}>
                      <Button
                        variant="contained"
                        startIcon={isBulkSaving ? <CircularProgress size={18} color="inherit" /> : <AddOutlinedIcon />}
                        onClick={handleConfirmBulkAdd}
                        disabled={isBulkSaving || checkedCidrs.size === 0}
                      >
                        ثبت {checkedCidrs.size} مورد انتخاب‌شده
                      </Button>
                      <Button onClick={() => setCandidates(null)} disabled={isBulkSaving}>
                        انصراف
                      </Button>
                    </Stack>
                  </>
                )}
                {candidates.length === 0 && <Button onClick={() => setCandidates(null)}>بازگشت</Button>}
              </Stack>
            )}
          </Card>

          {/* ---------- فهرست فعلی ---------- */}
          <Card variant="outlined" sx={{ borderRadius: 3, mb: 3 }}>
            {entries.length === 0 ? (
              <Box sx={{ p: 4, textAlign: "center" }}>
                <WifiOffOutlinedIcon sx={{ fontSize: 32, color: "text.secondary", mb: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  هنوز هیچ رنجی ثبت نشده.
                </Typography>
              </Box>
            ) : (
              entries.map((entry, index) => (
                <Box key={entry.id}>
                  {index > 0 && <Divider />}
                  <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ p: 2 }}>
                    <Box>
                      <Typography variant="body2" fontWeight={600} sx={{ ...monoFontSx, direction: "ltr" }}>
                        {entry.cidr}
                      </Typography>
                      {entry.label && (
                        <Typography variant="caption" color="text.secondary">
                          {entry.label}
                        </Typography>
                      )}
                    </Box>
                    <IconButton size="small" color="error" onClick={() => handleDelete(entry.id)}>
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </Stack>
                </Box>
              ))
            )}
          </Card>

          {/* ---------- پیام نمایش‌داده‌شده به کاربر مسدودشده ---------- */}
          <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
              متنی که به کاربر مسدودشده نمایش داده می‌شود
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              این متن دقیقاً همان چیزی است که در Dialog صفحه ورود، به کاربری که از یک IP غیرمجاز وارد
              می‌شود، نمایش داده می‌شود.
            </Typography>
            {messageResult && (
              <Alert severity={messageResult.success ? "success" : "error"} sx={{ mb: 2 }}>
                {messageResult.text}
              </Alert>
            )}
            {message === null ? (
              <CircularProgress size={20} />
            ) : (
              <Stack spacing={2}>
                <TextField
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  multiline
                  minRows={3}
                  disabled={isSavingMessage}
                />
                <Box>
                  <Button
                    variant="contained"
                    startIcon={isSavingMessage ? <CircularProgress size={18} color="inherit" /> : <SaveOutlinedIcon />}
                    onClick={handleSaveMessage}
                    disabled={isSavingMessage}
                  >
                    ذخیره متن پیام
                  </Button>
                </Box>
              </Stack>
            )}
          </Card>
        </>
      )}
    </Box>
  );
}
