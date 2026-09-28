/**
 * صفحه تنظیم پیام‌های تبریک تولد (مشترک بین ادمین و مدیر منابع انسانی).
 * شامل فهرست متولدین امروز با دکمه ارسال فوری، تنظیمات ارسال خودکار (فعال/غیرفعال و ساعت روزانه)
 * و مدیریت فهرست متن‌های تبریک که هر بار یکی به‌صورت تصادفی ارسال می‌شود.
 */
import { useEffect, useState } from "react";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CircularProgress,
  Divider,
  FormControlLabel,
  IconButton,
  MenuItem,
  Stack,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import CakeOutlinedIcon from "@mui/icons-material/CakeOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import SendOutlinedIcon from "@mui/icons-material/SendOutlined";
import FileDownloadOutlinedIcon from "@mui/icons-material/FileDownloadOutlined";
import {
  addBirthdayTemplate,
  deleteBirthdayTemplate,
  downloadBirthdaysExport,
  fetchBirthdayEnabled,
  fetchBirthdaySendTime,
  fetchBirthdayTemplates,
  sendBirthdayGreetingsNow,
  updateBirthdayEnabled,
  updateBirthdaySendTime,
} from "../api/hr";
import { fetchTodayBirthdays } from "../api/employees";
import DefaultPersonAvatar from "../components/DefaultPersonAvatar";
import SiteFilterSelect from "../components/SiteFilterSelect";

const HOURS = Array.from({ length: 24 }, (_, i) => i);  // گزینه‌های ساعت ۰ تا ۲۳
const MINUTES = [0, 15, 30, 45];  // گزینه‌های دقیقه با گام ۱۵ دقیقه
const JALALI_MONTHS = [
  "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
];

// ذخیره‌ی Blob دریافتی به‌صورت فایل در مرورگر
function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

// پیام خطای سرور از پاسخ Blob (در دانلود، بدنه‌ی خطا هم Blob است)
async function blobErrorMessage(err) {
  const data = err?.response?.data;
  try {
    if (data instanceof Blob) {
      const parsed = JSON.parse(await data.text());
      if (typeof parsed?.detail === "string") return parsed.detail;
    }
  } catch {
    /* پاسخ JSON نیست */
  }
  return "دریافت فایل Excel ناموفق بود.";
}

// کامپوننت صفحه؛ داده متن‌ها، تنظیمات ارسال و متولدین امروز را بارگذاری و مدیریت می‌کند
export default function BirthdayMessagesPage() {
  const [templates, setTemplates] = useState(null);  // فهرست متن‌های تبریک؛ null = در حال بارگذاری
  const [newText, setNewText] = useState("");
  const [isAdding, setIsAdding] = useState(false);
  const [templateError, setTemplateError] = useState("");

  const [sendTime, setSendTime] = useState(null); // { hour, minute }
  const [enabled, setEnabled] = useState(null);  // فعال بودن ارسال خودکار؛ null = در حال بارگذاری
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [settingsResult, setSettingsResult] = useState(null);  // { success, message } نتیجه ذخیره تنظیمات | null

  const [todayBirthdays, setTodayBirthdays] = useState(null);  // پرسنل متولد امروز؛ null = در حال بارگذاری

  const [isSendingNow, setIsSendingNow] = useState(false);
  const [sendNowResult, setSendNowResult] = useState(null);  // { success, message } نتیجه ارسال فوری | null

  const [exportMonth, setExportMonth] = useState("");  // "" = همه‌ی ماه‌ها
  const [exportSiteId, setExportSiteId] = useState(null);  // null = همه‌ی سایت‌های مجاز
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState("");

  // دانلود Excel متولدین ماه انتخابی (یا همه‌ی ماه‌ها با یک برگه برای هر ماه)
  async function handleExport() {
    setIsExporting(true);
    setExportError("");
    try {
      const blob = await downloadBirthdaysExport({ month: exportMonth || undefined, siteId: exportSiteId });
      const suffix = (exportSiteId ? `-site${exportSiteId}` : "") + (exportMonth ? `-${JALALI_MONTHS[exportMonth - 1]}` : "");
      saveBlob(blob, `birthdays${suffix}.xlsx`);
    } catch (err) {
      setExportError(await blobErrorMessage(err));
    } finally {
      setIsExporting(false);
    }
  }

  // فهرست متن‌های تبریک را از سرور می‌گیرد
  function loadTemplates() {
    fetchBirthdayTemplates().then(setTemplates);
  }

  // بارگذاری اولیه متن‌ها، ساعت ارسال، وضعیت فعال بودن و متولدین امروز
  useEffect(() => {
    loadTemplates();
    fetchBirthdaySendTime().then(setSendTime);
    fetchBirthdayEnabled().then(setEnabled);
    fetchTodayBirthdays().then(setTodayBirthdays);
  }, []);

  // متن جدید (غیرخالی، trim شده) را به فهرست اضافه و فهرست را تازه می‌کند
  async function handleAddTemplate() {
    setTemplateError("");
    if (!newText.trim()) {
      setTemplateError("متن پیام را وارد کنید.");
      return;
    }
    setIsAdding(true);
    try {
      await addBirthdayTemplate(newText.trim());
      setNewText("");
      loadTemplates();
    } catch (err) {
      setTemplateError(err.response?.data?.detail || "افزودن با خطا مواجه شد.");
    } finally {
      setIsAdding(false);
    }
  }

  // پس از تأیید کاربر، متن را حذف و فهرست را تازه می‌کند
  async function handleDeleteTemplate(id) {
    if (!window.confirm("این متن حذف شود؟")) return;
    await deleteBirthdayTemplate(id);
    loadTemplates();
  }

  // ساعت ارسال و وضعیت فعال بودن را هم‌زمان ذخیره و مقادیر برگشتی سرور را جایگزین می‌کند
  async function handleSaveSettings() {
    setSettingsResult(null);
    setIsSavingSettings(true);
    try {
      const [savedTime, savedEnabled] = await Promise.all([
        updateBirthdaySendTime(sendTime),
        updateBirthdayEnabled(enabled),
      ]);
      setSendTime(savedTime);
      setEnabled(savedEnabled);
      setSettingsResult({ success: true, message: "تنظیمات با موفقیت ذخیره شد." });
    } catch (err) {
      setSettingsResult({ success: false, message: err.response?.data?.detail || "ذخیره تنظیمات با خطا مواجه شد." });
    } finally {
      setIsSavingSettings(false);
    }
  }

  // ارسال فوری تبریک برای متولدین امروز؛ پیام نتیجه سرور نمایش داده می‌شود
  async function handleSendNow() {
    setSendNowResult(null);
    setIsSendingNow(true);
    try {
      const result = await sendBirthdayGreetingsNow();
      setSendNowResult({ success: true, message: result.message });
    } catch (err) {
      setSendNowResult({ success: false, message: err.response?.data?.detail || "ارسال با خطا مواجه شد." });
    } finally {
      setIsSendingNow(false);
    }
  }

  return (
    <Box sx={{ maxWidth: 720, mx: "auto" }}>
      <Typography variant="h5" fontWeight={700} sx={{ mb: 0.5 }}>
        پیام‌های تبریک تولد
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        هر روز، در ساعتی که پایین تنظیم می‌کنید، یک متن تصادفی از فهرست زیر برای هر پرسنلی که همان روز
        تولدش است فرستاده می‌شود. این تنظیمات بین ادمین و مدیر منابع انسانی مشترک است — هر دو می‌توانند
        تغییرش بدهند.
      </Typography>

      {/* ---------- متولدین امروز ---------- */}
      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }} flexWrap="wrap" rowGap={1}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <CakeOutlinedIcon color="secondary" />
            <Typography variant="subtitle2" fontWeight={700}>
              متولدین امروز
            </Typography>
          </Stack>
          <Button
            size="small"
            variant="outlined"
            startIcon={isSendingNow ? <CircularProgress size={16} /> : <SendOutlinedIcon />}
            onClick={handleSendNow}
            disabled={isSendingNow}
          >
            ارسال همین الان
          </Button>
        </Stack>
        {sendNowResult && (
          <Alert severity={sendNowResult.success ? "success" : "error"} sx={{ mt: 2, mb: 2 }}>
            {sendNowResult.message}
          </Alert>
        )}
        {todayBirthdays === null ? (
          <CircularProgress size={20} />
        ) : todayBirthdays.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            امروز تولد نداریم!
          </Typography>
        ) : (
          <Stack spacing={1.5}>
            {todayBirthdays.map((e) => (
              <Stack key={e.id} direction="row" alignItems="center" spacing={1.5}>
                <Avatar
                  sx={{
                    width: 32,
                    height: 32,
                    bgcolor: "secondary.main",
                    color: "secondary.contrastText",
                  }}
                >
                  <DefaultPersonAvatar />
                </Avatar>
                <Box>
                  <Typography variant="body2">
                    {e.first_name} {e.last_name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {[e.site_name, e.department_name].filter(Boolean).join(" — ")}
                  </Typography>
                </Box>
              </Stack>
            ))}
          </Stack>
        )}
      </Card>

      {/* ---------- خروجی Excel متولدین ---------- */}
      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 0.5 }}>
          خروجی Excel متولدین
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 2 }}>
          نام و نام خانوادگی، کد پرسنلی، واحد و تاریخ تولد پرسنل فعال. با «همه‌ی ماه‌ها» هر ماه در یک برگه‌ی جدا می‌آید.
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ sm: "center" }}>
          <SiteFilterSelect value={exportSiteId} onChange={setExportSiteId} permission="hr.birthday_messages" />
          <TextField
            select
            size="small"
            label="ماه تولد"
            value={exportMonth}
            onChange={(e) => setExportMonth(e.target.value)}
            sx={{ minWidth: 220 }}
          >
            <MenuItem value="">همه‌ی ماه‌ها (هر ماه یک برگه)</MenuItem>
            {JALALI_MONTHS.map((name, i) => (
              <MenuItem key={name} value={i + 1}>
                {name}
              </MenuItem>
            ))}
          </TextField>
          <Button
            variant="outlined"
            startIcon={isExporting ? <CircularProgress size={16} /> : <FileDownloadOutlinedIcon />}
            onClick={handleExport}
            disabled={isExporting}
          >
            دانلود Excel
          </Button>
        </Stack>
        {exportError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {exportError}
          </Alert>
        )}
      </Card>

      {/* ---------- تنظیمات ارسال ---------- */}
      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2 }}>
          تنظیمات ارسال خودکار
        </Typography>

        {sendTime === null || enabled === null ? (
          <CircularProgress size={20} />
        ) : (
          <Stack spacing={2.5}>
            {/* کلید فعال/غیرفعال ارسال خودکار */}
            <FormControlLabel
              control={<Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />}
              label={enabled ? "ارسال خودکار فعال است" : "ارسال خودکار غیرفعال است"}
            />
            {/* انتخاب ساعت و دقیقه ارسال روزانه */}
            <Stack direction="row" spacing={1.5} alignItems="center">
              <Typography variant="body2" color="text.secondary">
                ساعت ارسال روزانه:
              </Typography>
              <TextField
                select
                size="small"
                label="ساعت"
                value={sendTime.hour}
                onChange={(e) => setSendTime({ ...sendTime, hour: Number(e.target.value) })}
                sx={{ width: 90 }}
              >
                {HOURS.map((h) => (
                  <MenuItem key={h} value={h}>
                    {String(h).padStart(2, "0")}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                size="small"
                label="دقیقه"
                value={sendTime.minute}
                onChange={(e) => setSendTime({ ...sendTime, minute: Number(e.target.value) })}
                sx={{ width: 90 }}
              >
                {MINUTES.map((m) => (
                  <MenuItem key={m} value={m}>
                    {String(m).padStart(2, "0")}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>
            {settingsResult && (
              <Alert severity={settingsResult.success ? "success" : "error"}>{settingsResult.message}</Alert>
            )}
            <Box>
              <Button
                variant="contained"
                startIcon={isSavingSettings ? <CircularProgress size={18} color="inherit" /> : <SaveOutlinedIcon />}
                onClick={handleSaveSettings}
                disabled={isSavingSettings}
              >
                ذخیره تنظیمات
              </Button>
            </Box>
          </Stack>
        )}
      </Card>

      {/* ---------- فهرست متن‌های تبریک: افزودن متن جدید و حذف متن‌های موجود ---------- */}
      <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2 }}>
          فهرست متن‌های تبریک (هر بار یکی به‌صورت تصادفی انتخاب می‌شود)
        </Typography>

        <Stack spacing={2} sx={{ mb: 3 }}>
          <TextField
            label="متن پیام جدید"
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            multiline
            minRows={2}
            disabled={isAdding}
          />
          {templateError && <Alert severity="error">{templateError}</Alert>}
          <Box>
            <Button
              variant="outlined"
              startIcon={isAdding ? <CircularProgress size={18} /> : <AddOutlinedIcon />}
              onClick={handleAddTemplate}
              disabled={isAdding}
            >
              افزودن به فهرست
            </Button>
          </Box>
        </Stack>

        {/* فهرست متن‌ها؛ اگر خالی باشد هیچ پیامی ارسال نمی‌شود */}
        {templates === null ? (
          <CircularProgress size={20} />
        ) : templates.length === 0 ? (
          <Alert severity="warning">
            فهرست خالی است — تا حداقل یک متن اضافه نکنید، هیچ پیامی فرستاده نمی‌شود.
          </Alert>
        ) : (
          <Card variant="outlined">
            {templates.map((t, index) => (
              <Box key={t.id}>
                {index > 0 && <Divider />}
                <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ px: 2, py: 1.5 }}>
                  <Typography variant="body2" sx={{ flex: 1, pl: 2 }}>
                    {t.text}
                  </Typography>
                  <IconButton size="small" color="error" onClick={() => handleDeleteTemplate(t.id)}>
                    <DeleteOutlineIcon fontSize="small" />
                  </IconButton>
                </Stack>
              </Box>
            ))}
          </Card>
        )}
      </Card>
    </Box>
  );
}
