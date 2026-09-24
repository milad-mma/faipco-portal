/**
 * صفحه تنظیم رنج‌های IP مجاز برای ورود به پرتال.
 * شامل کلید فعال/غیرفعال، ویرایشگر متنی فهرست رنج‌ها (با دکمه پاک‌سازی که فقط IP/CIDR معتبر را نگه می‌دارد)
 * و ویرایش متن پیامی که به کاربر مسدودشده در صفحه ورود نمایش داده می‌شود.
 */
import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CircularProgress,
  Divider,
  FormControlLabel,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import AutoFixHighOutlinedIcon from "@mui/icons-material/AutoFixHighOutlined";
import {
  fetchIpAllowlistState,
  fetchIpBlockedMessage,
  saveIpAllowlistState,
  updateIpBlockedMessage,
} from "../api/system";
import { monoFontSx } from "../theme";

// الگوی IPv4 با CIDR اختیاری؛ همان منطق سمت سرور، برای پاک‌سازی فوری متن در مرورگر بدون درخواست به سرور
const IPV4_PATTERN = /\b(?:\d{1,3}\.){3}\d{1,3}(?:\/\d{1,2})?\b/g;

// ورودی: متن خام (مثلاً خروجی کامل فایروال). همه IPv4ها را استخراج، IP تکی را به /32 تبدیل،
// تکراری‌ها را حذف و مرتب می‌کند. خروجی: یک رنج در هر خط
function cleanExtractText(rawText) {
  const matches = rawText.match(IPV4_PATTERN) || [];
  const normalized = new Set();
  for (const m of matches) {
    normalized.add(m.includes("/") ? m : `${m}/32`);
  }
  return Array.from(normalized).sort().join("\n");
}

// کامپوننت صفحه؛ وضعیت فهرست IP و متن پیام مسدودسازی را بارگذاری و ذخیره می‌کند
export default function IpAllowlistPage() {
  const [enabled, setEnabled] = useState(false);
  const [text, setText] = useState(null); // null = هنوز بارگذاری نشده
  const [count, setCount] = useState(0);  // تعداد رنج‌های ذخیره‌شده در سرور
  const [isSaving, setIsSaving] = useState(false);
  const [saveResult, setSaveResult] = useState(null);  // { success, message } نتیجه ذخیره فهرست | null

  const [message, setMessage] = useState(null);  // متن پیام کاربر مسدودشده؛ null = در حال بارگذاری
  const [isSavingMessage, setIsSavingMessage] = useState(false);
  const [messageResult, setMessageResult] = useState(null);  // { success, text } نتیجه ذخیره متن پیام | null

  // بارگذاری اولیه وضعیت فهرست IP و متن پیام مسدودسازی
  useEffect(() => {
    fetchIpAllowlistState().then((state) => {
      setEnabled(state.enabled);
      setText(state.text);
      setCount(state.count);
    });
    fetchIpBlockedMessage().then(setMessage);
  }, []);

  // متن ویرایشگر را با خروجی cleanExtractText جایگزین می‌کند
  function handleClean() {
    setText((current) => cleanExtractText(current));
  }

  // وضعیت کلید و متن رنج‌ها را ذخیره می‌کند و مقادیر نرمال‌شده برگشتی از سرور را جایگزین می‌کند
  async function handleSave() {
    setSaveResult(null);
    setIsSaving(true);
    try {
      const state = await saveIpAllowlistState({ enabled, text });
      setText(state.text);
      setCount(state.count);
      setEnabled(state.enabled);
      setSaveResult({ success: true, message: `ذخیره شد — ${state.count} رنج ثبت‌شده.` });
    } catch (err) {
      setSaveResult({ success: false, message: err.response?.data?.detail || "ذخیره با خطا مواجه شد." });
    } finally {
      setIsSaving(false);
    }
  }

  // متن پیام مسدودسازی را ذخیره می‌کند
  async function handleSaveMessage() {
    setIsSavingMessage(true);
    setMessageResult(null);
    try {
      const saved = await updateIpBlockedMessage(message);
      setMessage(saved);
      setMessageResult({ success: true, text: "ذخیره شد." });
    } catch (err) {
      setMessageResult({ success: false, text: err.response?.data?.detail || "ذخیره با خطا مواجه شد." });
    } finally {
      setIsSavingMessage(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 760, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        رنج‌های IP مجاز برای ورود
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        اگر فعال باشد و حداقل یک رنج ثبت شده باشد، ورود به پرتال فقط از همان رنج‌ها امکان‌پذیر است —
        هرکسی از بیرون آن‌ها (مثلاً با VPN) بخواهد وارد شود، پیام پایین صفحه را می‌بیند.
      </Typography>

      {text === null ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          {/* کارت فهرست رنج‌ها: کلید فعال‌سازی، هشدار، ویرایشگر و دکمه‌ها */}
          <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }} flexWrap="wrap" rowGap={1}>
              <FormControlLabel
                control={<Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />}
                label={enabled ? "این محدودیت فعال است" : "این محدودیت غیرفعال است"}
              />
              <Typography variant="caption" color="text.secondary">
                در حال حاضر {count} رنج ثبت‌شده
              </Typography>
            </Stack>

            {/* هشدار: کلید روشن است ولی فهرست خالی است، پس محدودیت عملاً اعمال نمی‌شود */}
            {enabled && count === 0 && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                کلید فعال است ولی هنوز هیچ رنجی ذخیره نشده — تا وقتی حداقل یک رنج پایین اضافه و ذخیره
                نکنید، این محدودیت عملاً هیچ‌کس را مسدود نمی‌کند (برای جلوگیری از قفل‌شدن تصادفی همه).
              </Alert>
            )}

            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
              فهرست رنج‌ها (هر IP یا رنج در یک خط)
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              مثل یک ویرایشگر متن معمولی عمل کنید — می‌توانید چند خط را انتخاب و حذف کنید، یا کل محتوای
              یک فایل (حتی یک فایروال کامل با هزاران خط) را همین‌جا Paste کنید و روی «پاک‌سازی متن» بزنید
              تا فقط IP/رنج‌های معتبر باقی بمانند.
            </Typography>

            {/* ویرایشگر چپ‌به‌راست با فونت monospace، یک رنج در هر خط */}
            <TextField
              value={text}
              onChange={(e) => setText(e.target.value)}
              multiline
              minRows={10}
              maxRows={24}
              fullWidth
              disabled={isSaving}
              placeholder={"203.0.113.5/32\n192.168.1.0/24"}
              sx={{
                direction: "ltr",
                "& textarea": { textAlign: "left", ...monoFontSx, fontSize: 13, lineHeight: 1.7 },
              }}
            />

            {saveResult && (
              <Alert severity={saveResult.success ? "success" : "error"} sx={{ mt: 2, mb: 2 }}>
                {saveResult.message}
              </Alert>
            )}
            <Stack direction="row" spacing={1.5}>
              <Button
                variant="outlined"
                startIcon={<AutoFixHighOutlinedIcon />}
                onClick={handleClean}
                disabled={isSaving}
              >
                پاک‌سازی متن
              </Button>
              <Button
                variant="contained"
                startIcon={isSaving ? <CircularProgress size={18} color="inherit" /> : <SaveOutlinedIcon />}
                onClick={handleSave}
                disabled={isSaving}
              >
                ذخیره تغییرات
              </Button>
            </Stack>
          </Card>

          {/* کارت ویرایش متن پیام کاربر مسدودشده */}
          <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1 }}>
              متنی که به کاربر مسدودشده نمایش داده می‌شود
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              این متن دقیقاً همان چیزی است که در Dialog صفحه ورود، به کاربری که از یک IP غیرمجاز وارد
              می‌شود، نمایش داده می‌شود.
            </Typography>
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
                {messageResult && (
                  <Alert severity={messageResult.success ? "success" : "error"}>{messageResult.text}</Alert>
                )}
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
