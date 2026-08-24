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
import {
  addBirthdayTemplate,
  deleteBirthdayTemplate,
  fetchBirthdayEnabled,
  fetchBirthdaySendTime,
  fetchBirthdayTemplates,
  sendBirthdayGreetingsNow,
  updateBirthdayEnabled,
  updateBirthdaySendTime,
} from "../api/hr";
import { fetchTodayBirthdays } from "../api/employees";
import DefaultPersonAvatar from "../components/DefaultPersonAvatar";

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const MINUTES = [0, 15, 30, 45];

export default function BirthdayMessagesPage() {
  const [templates, setTemplates] = useState(null);
  const [newText, setNewText] = useState("");
  const [isAdding, setIsAdding] = useState(false);
  const [templateError, setTemplateError] = useState("");

  const [sendTime, setSendTime] = useState(null); // { hour, minute }
  const [enabled, setEnabled] = useState(null);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [settingsResult, setSettingsResult] = useState(null);

  const [todayBirthdays, setTodayBirthdays] = useState(null);

  const [isSendingNow, setIsSendingNow] = useState(false);
  const [sendNowResult, setSendNowResult] = useState(null);

  function loadTemplates() {
    fetchBirthdayTemplates().then(setTemplates);
  }

  useEffect(() => {
    loadTemplates();
    fetchBirthdaySendTime().then(setSendTime);
    fetchBirthdayEnabled().then(setEnabled);
    fetchTodayBirthdays().then(setTodayBirthdays);
  }, []);

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
      setTemplateError(err.response?.data?.detail || "افزودن ناموفق بود.");
    } finally {
      setIsAdding(false);
    }
  }

  async function handleDeleteTemplate(id) {
    if (!window.confirm("این متن حذف شود؟")) return;
    await deleteBirthdayTemplate(id);
    loadTemplates();
  }

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
      setSettingsResult({ success: true, message: "ذخیره شد." });
    } catch (err) {
      setSettingsResult({ success: false, message: err.response?.data?.detail || "ذخیره ناموفق بود." });
    } finally {
      setIsSavingSettings(false);
    }
  }

  async function handleSendNow() {
    setSendNowResult(null);
    setIsSendingNow(true);
    try {
      const result = await sendBirthdayGreetingsNow();
      setSendNowResult({ success: true, message: result.message });
    } catch (err) {
      setSendNowResult({ success: false, message: err.response?.data?.detail || "ارسال ناموفق بود." });
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
          <Alert severity={sendNowResult.success ? "success" : "error"} sx={{ mb: 2 }}>
            {sendNowResult.message}
          </Alert>
        )}
        {todayBirthdays === null ? (
          <CircularProgress size={20} />
        ) : todayBirthdays.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            امروز کسی تولد ندارد.
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

      {/* ---------- تنظیمات ارسال ---------- */}
      <Card variant="outlined" sx={{ p: 3, borderRadius: 3, mb: 3 }}>
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2 }}>
          تنظیمات ارسال خودکار
        </Typography>

        {settingsResult && (
          <Alert severity={settingsResult.success ? "success" : "error"} sx={{ mb: 2 }}>
            {settingsResult.message}
          </Alert>
        )}

        {sendTime === null || enabled === null ? (
          <CircularProgress size={20} />
        ) : (
          <Stack spacing={2.5}>
            <FormControlLabel
              control={<Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />}
              label={enabled ? "ارسال خودکار فعال است" : "ارسال خودکار غیرفعال است"}
            />
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

      {/* ---------- پول متن‌ها ---------- */}
      <Card variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
        <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2 }}>
          فهرست متن‌های تبریک (هر بار یکی به‌صورت تصادفی انتخاب می‌شود)
        </Typography>

        {templateError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {templateError}
          </Alert>
        )}

        <Stack spacing={2} sx={{ mb: 3 }}>
          <TextField
            label="متن پیام جدید"
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            multiline
            minRows={2}
            disabled={isAdding}
          />
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
